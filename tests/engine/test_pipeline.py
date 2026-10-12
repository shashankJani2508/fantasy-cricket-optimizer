"""Run pipeline end to end on the Neon *dev* schema (test rows only, prefixed test:), Gemini replayed from
recorded-shape responses; scoring is stubbed (the scorer has its own tests). Skipped without DATABASE_URL."""
import datetime as dt
import json

import pytest

from engine.env import env

pytestmark = pytest.mark.skipif(not env("DATABASE_URL"), reason="DATABASE_URL not set")
MID = "test:m1"
ROLES = ["WK"] + ["BAT"] * 4 + ["AR"] * 2 + ["BOWL"] * 4
CLEAN = ["explanations", "bench", "teams_picked", "gemini_adjustments", "gemini_calls", "predictions", "overrides"]


@pytest.fixture
def store():
    from engine.db import PgStore
    s = PgStore(schema="dev")
    runs = "(SELECT id FROM runs WHERE match_id = %s)"
    for t in CLEAN:
        s.conn.execute(f"DELETE FROM {t} WHERE run_id IN {runs}", (MID,))
    for sql in ["DELETE FROM metrics WHERE match_id = %s", "DELETE FROM player_match_points WHERE match_id = %s",
                "DELETE FROM runs WHERE match_id = %s", "DELETE FROM credits WHERE match_id = %s",
                "DELETE FROM match_xi WHERE match_id = %s", "DELETE FROM activity_log WHERE match_id = %s",
                "DELETE FROM matches WHERE id = %s"]:
        s.conn.execute(sql, (MID,))
    s.conn.execute("""INSERT INTO teams (id, name, gender) VALUES ('test:A', 'Test A', 'male'), ('test:B', 'Test B', 'male')
                      ON CONFLICT DO NOTHING""")
    s.conn.execute("INSERT INTO venues (id, name) VALUES ('test:v', 'Test Ground') ON CONFLICT DO NOTHING")
    s.conn.execute("""INSERT INTO matches (id, format, gender, format_group, venue_id, team_a_id, team_b_id, start_time,
                      status) VALUES (%s, 'T20', 'male', 'T20_men', 'test:v', 'test:A', 'test:B', %s, 'upcoming')""",
                   (MID, dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)))
    ps, xi, cr = [], [], []
    for side, team in (("A", "test:A"), ("B", "test:B")):
        for i, role in enumerate(ROLES):
            pid = f"test:{side}{i:02d}"
            ps.append((pid, f"Test {side}{i:02d}"))
            xi.append((MID, team, pid))
            cr.append((MID, pid, 8 + (i % 5) * 0.5, role))
    with s.conn.cursor() as c:
        c.executemany("INSERT INTO players (id, full_name) VALUES (%s, %s) ON CONFLICT DO NOTHING", ps)
        c.executemany("INSERT INTO match_xi (match_id, team_id, player_id, source) VALUES (%s, %s, %s, 'squad')", xi)
        c.executemany("""INSERT INTO credits (match_id, player_id, credits, dream11_role, entered_via)
                         VALUES (%s, %s, %s, %s, 'typed')""", cr)
    yield s
    s.conn.execute("SET search_path TO public")
    s.conn.close()


def fake_score(store, client, points, mid, pids, run_type, run_id=None, **k):
    from engine.score import ScoreResult
    for i, pid in enumerate(sorted(pids)):
        store.save_prediction(run_id, {"player_id": pid, "factors": {"venue": 30 + i, "form": 20 + i}, "trust": {},
                                       "fallback_step": 1, "fallback_note": None, "thin_data": i % 7 == 0,
                                       "provisional_inputs": False, "provisional_weights": True,
                                       "borrowed_from_group": None, "base_score": 20.0 + i})
    return ScoreResult(run_id, mid, "T20_men", run_type, None, True, None, False, warnings=["Rubric weights are provisional"])


def wrap(obj):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]}


class Replay:
    """Answers each job from the request it gets, like the real model would, but deterministically."""
    def __init__(self, fail_moderator=False):
        self.fail = fail_moderator

    def __call__(self, body):
        data = json.loads(body["contents"][0]["parts"][0]["text"])
        if "tools" in body:
            if self.fail:
                raise OSError("timeout")
            pid = data["players"][0]["player_id"]
            return wrap({"adjustments": [{"player_id": pid, "change_percent": 30, "reason": "pitch drier than usual",
                                          "reason_type": "pitch_differs"}], "pitch_note": "dry", "news_checked": True})
        line = lambda p: {"player_id": p["player_id"], "reason": f"Expected {p['adjusted_score']} at this venue"}
        cap = next(p for p in data["team"] if p["player_id"] == data["captain_id"])
        vc = next(p for p in data["team"] if p["player_id"] == data["vc_id"])
        return wrap({"players": [line(p) for p in data["team"]], "captain": line(cap), "vice_captain": line(vc),
                     "bench": [line(p) for p in data["bench"]]})


def run(store, monkeypatch, gem_transport):
    from engine import pipeline
    from engine.gemini import Gemini
    monkeypatch.setattr(pipeline, "score_match", fake_score)
    rid = pipeline.start(store, MID, "pre_toss")
    g = Gemini(store, transport=gem_transport, model="m", key="k", sleep=lambda s: None)
    return pipeline, rid, pipeline.resume(store, rid, gemini=g, forecast_fn=lambda *a: None), g


def test_full_run_to_done(store, monkeypatch):
    pipeline, rid, status, _ = run(store, monkeypatch, Replay())
    assert status == "done", store.q("SELECT failed_step, error_message FROM runs WHERE id = %s", (rid,))
    team = store.q("SELECT player_ids, captain_id, vc_id, gate_passed FROM teams_picked WHERE run_id = %s AND kind = 'system'",
                   (rid,))[0]
    assert len(team[0]) == 11 and team[3]
    adj = store.q("SELECT applied_pct, clipped FROM gemini_adjustments WHERE run_id = %s", (rid,))
    assert adj == [(20.0, True)]
    scores = dict(store.q("SELECT player_id, adjusted_score FROM predictions WHERE run_id = %s", (rid,)))
    assert team[1] == max(team[0], key=lambda p: scores[p])
    assert store.one("SELECT count(*) FROM bench WHERE run_id = %s", (rid,)) == 4
    assert store.one("SELECT count(*) FROM explanations WHERE run_id = %s", (rid,)) == 11 + 2 + 4
    warnings = store.one("SELECT warnings FROM runs WHERE id = %s", (rid,))
    assert "Gemini wanted to go beyond ±20%" in warnings and any("XI not confirmed" in w for w in warnings)
    assert store.one("SELECT count(*) FROM gemini_calls WHERE run_id = %s", (rid,)) == 2

    from engine.learning import compute_metrics
    with store.conn.cursor() as c:
        c.executemany("""INSERT INTO player_match_points (player_id, match_id, format_group, total_points, source,
                         is_provisional) VALUES (%s, %s, 'T20_men', %s, 'scorecard', true)""",
                      [(p, MID, (i * 7) % 60) for i, p in enumerate(sorted(scores))])
    m = compute_metrics(store, MID)
    assert m["perfect_points"] >= m["system_points"] and not m["points_final"] and m["captain_hit"] is not None
    assert 0 < m["efficiency"] <= 1 and m["mae"] is not None


def test_gemini_down_still_builds_a_team(store, monkeypatch):
    class Down(Replay):
        def __call__(self, body):
            raise OSError("down")
    pipeline, rid, status, _ = run(store, monkeypatch, Down())
    assert status == "done"
    warnings = store.one("SELECT warnings FROM runs WHERE id = %s", (rid,))
    assert any(w.startswith("News not checked") for w in warnings)
    assert any(w.startswith("Reasons written automatically") for w in warnings)
    assert store.one("SELECT count(*) FROM explanations WHERE run_id = %s", (rid,)) == 17


def test_failure_records_step_and_resume_continues(store, monkeypatch):
    from engine import pipeline
    monkeypatch.setattr(pipeline, "step_optimizing", lambda *a: (_ for _ in ()).throw(pipeline.StepFailed("boom")))
    _, rid, status, g = run(store, monkeypatch, Replay())
    assert status == "failed"
    assert store.q("SELECT failed_step, error_message FROM runs WHERE id = %s", (rid,))[0] == ("optimizing", "boom")
    monkeypatch.undo()
    monkeypatch.setattr(pipeline, "score_match", fake_score)
    assert pipeline.retry(store, rid, gemini=g, forecast_fn=lambda *a: None) == "done"
    assert store.one("SELECT count(*) FROM predictions WHERE run_id = %s", (rid,)) == 22
