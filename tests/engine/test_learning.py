"""Learning loop (LEARNING_LOOP.md section 6). Pure rules always; the flag -> suggestion -> approve -> new version
-> rollback / Gemini-cap journey on the Neon dev schema with seeded test rows (skipped without DATABASE_URL)."""
import datetime as dt
import json

import pytest

from engine.env import env
from engine.factors import FACTORS
from engine.learning import bat_band, evaluate, renormalise, team_total

W = {"form": 0.1, "venue": 0.2, "opponent": 0.1, "current_touch": 0.1, "opportunity": 0.1, "career": 0.3,
     "bat_first_or_chase": 0.05, "pitch_type": 0.05}


def test_flag_rule():
    assert not evaluate([40] * 9, 30, 10, 0.7)["flagged"]                  # fewer than 10 real misses
    assert not evaluate([40] * 6 + [-40] * 4, 30, 10, 0.7)["flagged"]      # 60% same direction
    ev = evaluate([40] * 8 + [-40] * 2 + [5] * 20, 30, 10, 0.7)
    assert ev["flagged"] and ev["direction"] == "over" and ev["real_misses"] == 10


def test_renormalise_sums_to_one():
    w = renormalise(W, "venue", 0.1)
    assert abs(sum(w.values()) - 1) < 1e-5 and w["venue"] == 0.1
    assert w["career"] > W["career"]


def test_team_total_and_bands():
    assert team_total(["a", "b"], "a", "b", {"a": 10, "b": 4}, 2, 1.5) == 10 + 4 + 10 + 2
    assert [bat_band(p) for p in (1, 5, 9, None)] == ["top", "middle", "lower", "did_not_bat"]


MIDS = [f"test:L{i:02d}" for i in range(10)]


@pytest.fixture
def store():
    if not env("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    from engine.db import PgStore
    s = PgStore(schema="dev")
    _clean(s)
    keep = s.q("SELECT id FROM rubric_versions WHERE is_active AND format_group = 'T20-male'")[0][0]
    yield s
    _clean(s)
    s.q("DELETE FROM rubric_versions WHERE format_group = 'T20-male' AND id <> %s RETURNING id", (keep,))
    s.q("UPDATE rubric_versions SET is_active = true WHERE id = %s RETURNING id", (keep,))
    s.q("UPDATE settings SET value = '20' WHERE key = 'gemini_cap_percent' RETURNING key")
    s.q("UPDATE settings SET value = '20' WHERE key = 'gemini_trust_window_matches' RETURNING key")
    s.conn.execute("SET search_path TO public")
    s.conn.close()


def _clean(s):
    s.q("DELETE FROM weight_suggestions WHERE format_group IN ('T20-male', 'T20_men') OR kind = 'gemini_cap' RETURNING id")
    s.q("DELETE FROM patterns WHERE format_group = 'T20_men' RETURNING id")
    for t in ("gemini_adjustments", "predictions", "teams_picked"):
        s.q(f"DELETE FROM {t} WHERE run_id IN (SELECT id FROM runs WHERE match_id LIKE 'test:L%%') RETURNING id")
    for t in ("metrics", "player_match_points", "credits", "runs", "match_xi", "matches"):
        col = "id" if t == "matches" else "match_id"
        s.q(f"DELETE FROM {t} WHERE {col} LIKE 'test:L%%' RETURNING 1")


def _seed(s, start):
    s.q("INSERT INTO players (id, full_name) VALUES ('test:LP', 'Test Opener') ON CONFLICT DO NOTHING RETURNING id")
    with s.conn.cursor() as c:
        c.executemany("""INSERT INTO matches (id, format, gender, format_group, start_time, status)
                         VALUES (%s, 'T20', 'male', 'T20_men', %s, 'finished')""",
                      [(m, start + dt.timedelta(days=i)) for i, m in enumerate(MIDS)])
        c.executemany("INSERT INTO credits (match_id, player_id, credits, dream11_role) VALUES (%s, 'test:LP', 9, 'BAT')",
                      [(m,) for m in MIDS])
        c.executemany("""INSERT INTO player_match_points (player_id, match_id, format_group, total_points, batting_position,
                         source, is_provisional) VALUES ('test:LP', %s, 'T20_men', 10, 1, 'cricsheet', false)""",
                      [(m,) for m in MIDS])
        c.executemany("INSERT INTO metrics (match_id, format_group) VALUES (%s, 'T20_men')", [(m,) for m in MIDS])
        rids = []
        for m in MIDS:
            c.execute("""INSERT INTO runs (match_id, run_type, status, started_at) VALUES (%s, 'pre_toss', 'done', now())
                         RETURNING id""", (m,))
            rids.append(c.fetchone()[0])
        # stored factors: form equals the actual (10), career is far off (200): predictions are 100+ points too high
        c.executemany("""INSERT INTO predictions (run_id, player_id, factors, base_score, adjusted_score)
                         VALUES (%s, 'test:LP', %s, 110, 120)""",
                      [(r, json.dumps({**{f: 0 for f in FACTORS}, "form": 10, "career": 200})) for r in rids])
        c.executemany("""INSERT INTO gemini_adjustments (run_id, player_id, requested_pct, applied_pct, reason, reason_type, helped)
                         VALUES (%s, 'test:LP', 9, 9, 'test', 'pitch_differs', false)""", [(r,) for r in rids])


class FakeGemini:
    def analyse(self, group, weights, max_change):
        return {"pattern": "We overrate top-order batters", "evidence": "10 matches", "why": "career too heavy",
                "proposal": {"factor": "career", "current_weight": weights["career"],
                             "proposed_weight": weights["career"] - 0.10}}, []


def test_flag_suggest_approve_rollback_and_cap(store):
    from engine import learning
    _seed(store, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
    new = learning.update_patterns(store, "T20_men")
    flagged = dict(store.q("SELECT group_type || ':' || group_value, status FROM patterns WHERE id = ANY(%s)", (new,)))
    assert flagged.get("role:BAT") == "flagged" and flagged.get("batting_band:top") == "flagged"
    pid = store.one("SELECT id FROM patterns WHERE format_group = 'T20_men' AND group_type = 'role' AND group_value = 'BAT'")
    sid = learning.suggest(store, FakeGemini(), pid)
    sug = store.q("SELECT proposal, history_check, history_mae_before, history_mae_after FROM weight_suggestions WHERE id = %s",
                  (sid,))[0]
    assert abs(sum(sug[0]["weights_after"].values()) - 1) < 1e-4 and sug[1] in ("supported", "not_supported")
    assert (sug[3] < sug[2]) == (sug[1] == "supported")
    with pytest.raises(learning.DecisionError):
        learning.decide(store, sid, "edit", {"form": 1})
    vid = learning.decide(store, sid, "approve")
    act = store.q("SELECT id, source, weights FROM rubric_versions WHERE is_active AND format_group = 'T20-male'")
    assert act[0][0] == vid and act[0][1] == "approved_change"
    assert store.one("SELECT status FROM patterns WHERE id = %s", (pid,)) == "resolved"

    # rollback: a worse version (all weight on career) whose parent (all on form) fits the 10 new matches exactly
    store.q("UPDATE rubric_versions SET weights = %s, approved_at = '2025-12-01' WHERE id = %s RETURNING id",
            (json.dumps({**{f: 0 for f in FACTORS}, "career": 1}), vid))
    parent = store.one("SELECT parent_version_id FROM rubric_versions WHERE id = %s", (vid,))
    old_w = store.one("SELECT weights FROM rubric_versions WHERE id = %s", (parent,))
    store.q("UPDATE rubric_versions SET weights = %s WHERE id = %s RETURNING id",
            (json.dumps({**{f: 0 for f in FACTORS}, "form": 1}), parent))
    rb = learning.check_rollback(store, "T20_men")
    store.q("UPDATE rubric_versions SET weights = %s WHERE id = %s RETURNING id", (json.dumps(old_w), parent))
    assert rb and store.one("SELECT history_mae_after FROM weight_suggestions WHERE id = %s", (rb,)) == 0

    store.q("UPDATE settings SET value = '10' WHERE key = 'gemini_trust_window_matches' RETURNING key")
    cap = learning.check_gemini_cap(store)
    assert cap and learning.decide(store, cap, "approve") is None
    assert float(store.one("SELECT value FROM settings WHERE key = 'gemini_cap_percent'")) == 10
