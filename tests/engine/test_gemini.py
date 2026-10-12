"""Gemini jobs: code checks, retries and parsing, on recorded responses only (GEMINI_RULES.md)."""
import json
from pathlib import Path

import pytest

from engine.gemini import (Gemini, GeminiFailed, check_analyst, check_explainer, check_moderator, check_screenshot,
                           is_generic, response_text)
from engine.sources.openmeteo import forecast_at

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def load(*p):
    return json.loads((FIX.joinpath(*p)).read_text(encoding="utf8"))


def wrap(obj):
    """A generateContent response in the recorded shape (see fixtures/gemini/probe_json.json)."""
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}], "modelVersion": "test-model"}


def gem(*responses):
    it = iter(responses)
    return Gemini(store=None, transport=lambda body: next(it), model="m", key="k", sleep=lambda s: None)


def test_recorded_responses_parse():
    for name in ("probe_json", "probe_search_json", "probe_image"):
        text, _ = response_text(load("gemini", f"{name}.json"))
        assert "answer" in json.loads(text)
    real = load("gemini", "moderator_real.json")
    out, errors = gem(*real["responses"]).moderate(real["request_players"], {"id": "x"}, real["forecast"])
    assert out["adjustments"] == [] and out["pitch_note"] and errors == []


def test_moderator_checks():
    pool = {"a", "b", "c", "d"}
    d = {"adjustments": [
        {"player_id": "a", "change_percent": 35, "reason": "pitch greener than usual", "reason_type": "pitch_differs"},
        {"player_id": "zz", "change_percent": 5, "reason": "x", "reason_type": "injury", "source_url": "https://x"},
        {"player_id": "b", "change_percent": -10, "reason": "hamstring", "reason_type": "injury"},
        {"player_id": "c", "change_percent": -15, "reason": "ruled out", "reason_type": "injury",
         "source_url": "https://news.example/c"},
        {"player_id": "c", "change_percent": 10, "reason": "again", "reason_type": "pitch_differs"},
        {"player_id": "d", "change_percent": 5, "reason": "famous", "reason_type": "reputation"}],
        "pitch_note": "dry", "news_checked": True}
    out, errors, retry = check_moderator(d, pool, 20)
    got = {a["player_id"]: a for a in out["adjustments"]}
    assert set(got) == {"a", "c"} and not retry
    assert got["a"]["applied_pct"] == 20 and got["a"]["clipped"] and got["a"]["requested_pct"] == 35
    assert got["c"]["applied_pct"] == -15 and not got["c"]["clipped"]
    assert len(errors) == 4   # zz not in pool, b no source, c twice, d banned reason type


def _expl(cap="c1", generic=False):
    line = "good player" if generic else "Venue average 48 at this ground"
    return {"players": [{"player_id": p, "reason": line} for p in ("c1", "v1", "p3")],
            "captain": {"player_id": cap, "reason": "Top expected score 61.2; venue 55"},
            "vice_captain": {"player_id": "v1", "reason": "Second at 50.4; form 44"},
            "bench": [{"player_id": "b1", "reason": "Left out on credits: 2.5 over"}]}


def test_explainer_retries_wrong_captain_then_flags_generic():
    payload = {"team": [{"player_id": p} for p in ("c1", "v1", "p3")], "bench": [{"player_id": "b1"}],
               "captain_id": "c1", "vc_id": "v1"}
    rows, errors = gem(wrap(_expl(cap="p3")), wrap(_expl(generic=True)), wrap(_expl(generic=True))).explain(payload)
    assert {(r["kind"], r["player_id"]) for r in rows} >= {("captain", "c1"), ("vice_captain", "v1"), ("bench", "b1")}
    assert all(r["generic_flag"] for r in rows if r["kind"] == "player")
    assert any("generic" in e for e in errors)
    ok, errs, retry = check_explainer(_expl(), ["c1", "v1", "p3"], "c1", "v1", ["b1"])
    assert errs == [] and not retry and len(ok) == 6


def test_banned_phrases():
    assert is_generic("He is a match winner") and is_generic("in form") and is_generic("")
    assert not is_generic("Averages 52 at Rawalpindi over 6 matches")


def test_analyst_clips_and_allows_no_change():
    w = {"form": 0.1, "venue": 0.2, "opponent": 0.1, "current_touch": 0.1, "opportunity": 0.1, "career": 0.3,
         "bat_first_or_chase": 0.05, "pitch_type": 0.05}
    out, errors, _ = check_analyst({"pattern": "p", "evidence": "e", "why": "w",
                                    "proposal": {"factor": "venue", "current_weight": 0.9, "proposed_weight": 0.0}},
                                   w, 0.10)
    assert out["proposal"] == {"factor": "venue", "current_weight": 0.2, "proposed_weight": 0.1} and errors
    out, _, retry = check_analyst({"pattern": "p", "evidence": "e", "why": "chance",
                                   "proposal": {"factor": "none", "current_weight": 0, "proposed_weight": 0}}, w, 0.10)
    assert out["proposal"] is None and not retry


def test_screenshot_marks_unsure():
    d = {"kind": "player_list", "rows": [
        {"name_on_screen": "S Ayub", "team_code": "PAK", "role": "BAT", "credits": 8.5, "unsure": False},
        {"name_on_screen": "K Mendis", "team_code": "SL", "role": "WK", "credits": None, "unsure": True},
        {"name_on_screen": "X Y", "team_code": "SL", "role": "Bowler", "credits": 99, "unsure": False},
        {"name_on_screen": "", "role": "AR", "credits": 8, "unsure": False}], "rank": None}
    out, errors, retry = check_screenshot(d, "player_list", (3, 13), (-50, 500))
    assert [r["unsure"] for r in out["rows"]] == [False, True, True] and not retry
    assert out["rows"][2]["role"] is None and out["rows"][2]["credits"] is None and errors


def test_retries_then_fails_and_never_raises_on_bad_json():
    bad = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    with pytest.raises(GeminiFailed):
        gem(bad, bad, bad).moderate([{"player_id": "a"}], {"id": "m"})
    out, _ = gem(bad, wrap({"adjustments": [], "pitch_note": "no pitch report found", "news_checked": True})) \
        .moderate([{"player_id": "a"}], {"id": "m"})
    assert out["adjustments"] == []


class _Cache:
    def __init__(self):
        self.c, self.v = {}, {}

    def q(self, sql, args):
        if sql.startswith("SELECT"):
            return [self.v[args[0]]] if args[0] in self.v else []
        self.v[args[2]] = (args[0], args[1])
        return [(1,)]

    def cache_get(self, s, k):
        return self.c.get((s, k))

    def cache_put(self, s, k, resp, f, e):
        self.c[(s, k)] = {"response": resp}


def test_openmeteo_forecast_from_fixture():
    import datetime as dt
    geo, fc = load("openmeteo", "geocode.json"), load("openmeteo", "forecast.json")
    store = _Cache()
    http = lambda url: geo if "geocoding" in url else fc
    start = dt.datetime.fromisoformat(fc["hourly"]["time"][30] + ":00+00:00")
    got = forecast_at(store, "v1", "Rawalpindi Cricket Stadium", start, http=http)
    assert got["rain_chance_pct"] == fc["hourly"]["precipitation_probability"][30]
    assert store.v["v1"] == (geo["results"][0]["latitude"], geo["results"][0]["longitude"])
    assert forecast_at(store, "v1", "x", start + dt.timedelta(days=60), http=http) is None
