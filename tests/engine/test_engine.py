"""Scoring engine tests (spec section 13). Saved fixtures and an in-memory store only: no live calls."""
import datetime as dt

import pytest
import yaml

from engine.factors import PeekingError, Record, Target, compute_factors_with_trust, trust_from_n
from engine.fallback import fallback
from engine.fresh import fill_recent, scorecard_rows
from engine.matching import Matcher
from engine.points import from_scorecard, load_points_config
from engine.rubric import RubricError, active_weights
from engine.score import score_match
from engine.settings import MissingSetting, Settings
from engine.sources.cricketdata import CricketData
from engine.env import ROOT
from tests.engine.fakes import MemoryStore, fixture, hist_row, weights

POINTS = load_points_config(ROOT / "config" / "dream11_points.yaml")


def rubric_row(group, w, reliable=True, rid=1):
    return {"id": rid, "format_group": group, "weights": w, "is_active": True, "reliable": reliable,
            "points_values_final": False}


def base_store(w=None):
    s = MemoryStore()
    s.rubric = [rubric_row("T20-male", w or weights(career=1.0), rid=1),
                rubric_row("T20-female", weights(form=1.0), reliable=False, rid=2)]
    s.matches["M"] = {"id": "M", "date": "2026-10-13", "format_group": "T20_men", "venue": "V",
                      "team_a": "A", "team_b": "X", "batting_first": "A", "series_id": None}
    return s


# 1. no peeking ---------------------------------------------------------------
def test_factors_never_see_same_day_or_later():
    cfg = Settings(MemoryStore()).factor_cfg()
    t = Target("2026-10-13", "T20_men", "V", "X", True)
    with pytest.raises(PeekingError):
        compute_factors_with_trust(t, [Record("2026-10-13", "T20_men", "V", "X", True, "1-3", "none", 5)],
                                   [], lambda v: "unknown", cfg)


def test_store_history_is_strictly_before_the_match():
    s = base_store()
    s.hist["p"] = [hist_row(f"2026-09-{d:02d}", 10) for d in range(1, 11)] + [hist_row("2026-10-13", 999)]
    r = score_match(s, None, POINTS, "M", ["p"], "post_toss")
    assert r.players[0].base_score == 10.0   # the 999 on the match date is never used


# 2. determinism --------------------------------------------------------------
def test_same_match_twice_gives_identical_results():
    s = base_store(weights(form=0.5, career=0.5))
    s.hist["p"] = [hist_row(f"2026-09-{d:02d}", d * 3) for d in range(1, 20)]
    a = score_match(s, None, POINTS, "M", ["p"], "pre_toss")
    b = score_match(s, None, POINTS, "M", ["p"], "pre_toss")
    assert [(p.player_id, p.base_score, p.factors) for p in a.players] == \
           [(p.player_id, p.base_score, p.factors) for p in b.players]


# 3. worked example (spec section 11, made-up numbers) -------------------------
def test_worked_example():
    w = weights(form=0.10, venue=0.15, opponent=0.05, career=0.70)
    factors = {"form": 40, "career": 35, "venue": 0.2 * 90 + 0.8 * 40, "opponent": 30,
               "current_touch": 40, "opportunity": 40, "bat_first_or_chase": 40, "pitch_type": 40}
    trust = {"form": 1, "career": 1, "venue": trust_from_n(2, 10), "opponent": trust_from_n(12, 10),
             "current_touch": 1, "opportunity": 0, "bat_first_or_chase": 0, "pitch_type": 0}
    base = sum(w[k] * factors[k] for k in w)
    assert base == pytest.approx(37.5)
    assert sum(w[k] * trust[k] for k in w) == pytest.approx(0.88)
    assert not sum(w[k] * trust[k] for k in w) < 0.5


# 4. thin-data rule -----------------------------------------------------------
@pytest.mark.parametrize("n,t", [(0, 0), (5, 0.5), (10, 1), (15, 1)])
def test_trust(n, t):
    assert trust_from_n(n, 10) == t


# 5. pre-toss -----------------------------------------------------------------
def test_pre_toss_bat_first_or_chase_equals_form():
    cfg = Settings(MemoryStore()).factor_cfg()
    hist = [Record(f"2026-09-{d:02d}", "T20_men", "V", "X", d % 2 == 0, "1-3", "none", d * 2.0) for d in range(1, 15)]
    f, trust = compute_factors_with_trust(Target("2026-10-13", "T20_men", "V", "X", True), hist, [],
                                          lambda v: "unknown", cfg, pre_toss=True)
    assert f["bat_first_or_chase"] == f["form"] and trust["bat_first_or_chase"] == 0


# 6. fallback chain -----------------------------------------------------------
def test_fallback_step2_with_scaling():
    s = base_store()
    s.hist["p"] = [hist_row("2026-01-01", 20, group="ODI_men"), hist_row("2026-01-05", 40, group="ODI_men")]
    s.scaling[("ODI_men", "T20_men")] = 0.5
    r = fallback(s, None, POINTS, "p", "T20_men", "2026-10-13")
    assert (r.step, r.base_score) == (2, 15.0)


def test_fallback_missing_scaling_goes_to_step3_career_stats():
    s = base_store()
    s.hist["p"] = [hist_row("2026-01-01", 20, group="ODI_men")]
    s.cd_ids["p"] = "52a6be27-1c5d-4c2b-86ab-98710ec7e0ef"
    client = CricketData(s, "k", 95, http_get=lambda url: fixture("players_info"), mode="live")
    r = fallback(s, client, POINTS, "p", "T20_men", "2026-10-13")
    assert r.step == 3 and r.base_score is not None and "format scaling not available" in r.warnings


def test_fallback_nothing_gives_null_no_data():
    s = base_store()
    r = fallback(s, None, POINTS, "p", "T20_men", "2026-10-13")
    assert (r.step, r.base_score, r.note) == (4, None, "no data")
    res = score_match(s, None, POINTS, "M", ["p"], "pre_toss")
    assert res.players[0].base_score is None and res.players[0].thin_data


# 7. borrowing ----------------------------------------------------------------
def test_unreliable_group_borrows_other_gender():
    s = base_store()
    s.rubric = [rubric_row("Test-male", weights(career=1.0), rid=5), rubric_row("Test-female", weights(form=1.0), False, 6)]
    c = active_weights(s, "Test_women")
    assert c.borrowed_from == "Test_men" and c.weights["career"] == 1.0
    s.matches["W"] = {"id": "W", "date": "2026-10-13", "format_group": "Test_women", "venue": "V",
                      "team_a": "A", "team_b": "X", "batting_first": None, "series_id": None}
    s.hist["p"] = [hist_row(f"2026-09-{d:02d}", 10, group="Test_women") for d in range(1, 12)]
    assert score_match(s, None, POINTS, "W", ["p"], "pre_toss").players[0].thin_data


# 8. rubric validation --------------------------------------------------------
def test_weights_not_summing_to_one_raise():
    s = base_store(weights(career=0.7))
    with pytest.raises(RubricError):
        active_weights(s, "T20_men")


def test_missing_setting_message():
    s = MemoryStore(); del s.settings["form_window"]
    with pytest.raises(MissingSetting, match="Missing setting form_window"):
        Settings(s).factor_cfg()


# 9. matching -----------------------------------------------------------------
def test_matching_exact_initials_ambiguous_unknown():
    s = MemoryStore()
    m = Matcher(s)
    team = [("p1", "V Kohli"), ("p2", "RG Sharma"), ("p3", "A Sharma"), ("p4", "A Sharma Jr")]
    assert m.resolve("cricketdata", "Virat Kohli", team) == "p1"          # initials
    assert m.resolve("cricketdata", "Virat Kohli", team) == "p1"          # now via the saved link
    assert m.resolve("cricketdata", "rg sharma", team) == "p2"            # exact normalised
    assert m.resolve("cricketdata", "Ankit Sharma", team + [("p5", "A Sharma")]) is None   # ambiguous
    assert m.resolve("cricketdata", "Nobody Here", team) is None          # unknown
    assert m.unmatched == ["Ankit Sharma", "Nobody Here"]


# 10. provisional fill --------------------------------------------------------
def test_scorecard_row_created_once_then_replaced_by_cricsheet():
    s = MemoryStore()
    sc = fixture("match_scorecard")["data"]
    series = fixture("series_info")
    s.teams[("Pakistan", "male")] = [("farhan", "Sahibzada Farhan")]
    client = CricketData(s, "k", 95, now=lambda: dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc),
                         http_get=lambda url: series if "series_info" in url else fixture("match_scorecard"), mode="live")
    for _ in range(2):
        fill_recent(s, client, POINTS, ["farhan"], "2026-10-13", sc["series_id"])
    rows = [r for k, r in s.points.items() if k[0] == "farhan"]
    assert len(rows) == 2 and all(r["source"] == "scorecard" and r["is_provisional"] for r in rows)  # 1st + 2nd T20I
    mid = "cd:" + sc["id"]
    s.upsert_points({**s.points[("farhan", mid)], "source": "cricsheet", "is_provisional": False})
    assert s.upsert_points({**s.points[("farhan", mid)], "source": "scorecard"}) is False
    assert s.points[("farhan", mid)]["source"] == "cricsheet"


def test_from_scorecard_uses_config_values():
    sc = fixture("match_scorecard")["data"]
    row = next(r for (t, n, _), r in scorecard_rows(sc).items() if n == "Sahibzada Farhan")
    pts = from_scorecard(row, "T20", POINTS)
    # 73 runs, 4 fours, 5 sixes, 50 milestone, SR 165.9 (no band), playing XI
    assert pts["batting"] == 73 * 1 + 4 * 1 + 5 * 2 + 8 and pts["playing_xi"] == 4


# 11. budget ------------------------------------------------------------------
def test_budget_limit_makes_no_live_call_and_sets_stale():
    s = MemoryStore()
    now = dt.datetime(2026, 10, 12, 12, tzinfo=dt.timezone.utc)
    s.cache_put("cricketdata", CricketData.request_key("match_info", {"id": "x"}), {"data": {"id": "x"}},
                now - dt.timedelta(hours=2), now - dt.timedelta(hours=1))   # expired copy
    s.usage_add("cricketdata", now.date(), 95)
    calls = []
    c = CricketData(s, "k", 95, now=lambda: now, http_get=lambda url: calls.append(url), mode="live")
    assert c.match_info("x") == {"id": "x"} and calls == [] and c.data_stale


# fix-up 5: data modes and caps -----------------------------------------------
def _live(s, **kw):
    calls = []
    now = dt.datetime(2026, 10, 12, 12, tzinfo=dt.timezone.utc)
    resp = {"status": "success", "data": {"id": "x"}, "info": {"hitsUsed": 1}}
    c = CricketData(s, "k", kw.pop("daily", 95), now=lambda: now, mode="live",
                    http_get=lambda url: calls.append(url) or resp, **kw)
    return c, calls, now


def test_offline_mode_never_calls_and_uses_fixtures():
    s = MemoryStore()
    c = CricketData(s, "k", 95, http_get=lambda url: pytest.fail("offline mode made a call"))
    assert c.mode == "offline"
    assert c.match_scorecard("0cb2b44c-69b3-4c50-b1a5-9af598ffecaf")["id"] == "0cb2b44c-69b3-4c50-b1a5-9af598ffecaf"
    assert c.match_info("unknown-id") == {} and c.data_stale and c.calls_this_run == 0


def test_cache_only_uses_expired_cache_and_never_fixtures():
    s = MemoryStore()
    now = dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc)
    s.cache_put("cricketdata", CricketData.request_key("match_info", {"id": "x"}), {"data": {"id": "x"}},
                now - dt.timedelta(days=2), now - dt.timedelta(days=1))
    c = CricketData(s, "k", 95, now=lambda: now, mode="cache_only", http_get=lambda url: pytest.fail("call"))
    assert c.match_info("x") == {"id": "x"} and c.data_stale
    assert c.match_scorecard("0cb2b44c-69b3-4c50-b1a5-9af598ffecaf") == {}


def test_dev_limit_and_per_run_limit_stop_live_calls():
    s = MemoryStore()
    c, calls, now = _live(s, dev_limit=2, run_limit=10)
    for i in range(4):
        c.match_info(f"m{i}")
    assert len(calls) == 2 and s.usage_get("cricketdata_dev", now.date()) == 2 and c.data_stale
    s2 = MemoryStore()
    c2, calls2, _ = _live(s2, dev_limit=30, run_limit=3)
    for i in range(5):
        c2.match_info(f"m{i}")
    assert len(calls2) == 3 and c2.calls_this_run == 3


def test_dry_run_counts_misses_without_calling():
    s = MemoryStore()
    c, calls, _ = _live(s, dry_run=True)
    c.match_info("a"); c.match_scorecard("b")
    assert calls == [] and c.would_call == 11


def test_finished_scorecard_cached_permanently_and_fetched_once():
    s = MemoryStore()
    now = dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc)
    sc = fixture("match_scorecard")
    calls = []
    c = CricketData(s, "k", 95, now=lambda: now, mode="live", http_get=lambda url: calls.append(url) or dict(sc))
    c.match_scorecard(sc["data"]["id"])
    later = CricketData(s, "k", 95, now=lambda: now + dt.timedelta(days=400), mode="live",
                        http_get=lambda url: calls.append(url) or dict(sc))
    later.match_scorecard(sc["data"]["id"])
    assert len(calls) == 1


def test_tests_cannot_reach_the_network():
    import urllib.request
    from tests.conftest import NetworkBlocked
    with pytest.raises(NetworkBlocked):
        urllib.request.urlopen("https://api.cricapi.com/v1/matches")


# fix-up 1: name matching coverage ---------------------------------------------
from engine.matching import CoverageMatcher, Register, surname_initial_match

SL = [("shanaka", "MD Shanaka"), ("kusal", "BKG Mendis"), ("kamindu", "PHKD Mendis"), ("theek", "M Theekshana")]


def test_surname_plus_initial_dasun_shanaka():
    assert surname_initial_match("Dasun Shanaka", "MD Shanaka")
    assert not surname_initial_match("Dasun Shanaka", "MD Mendis")
    m = CoverageMatcher(MemoryStore())
    assert m.resolve("cricketdata", "Dasun Shanaka", SL, SL) == "shanaka"


def test_kusal_and_kamindu_mendis_ambiguous_without_register():
    m = CoverageMatcher(MemoryStore())
    assert m.resolve("cricketdata", "Kusal Mendis", SL, SL) is None      # BKG and PHKD both contain 'k'
    assert m.resolve("cricketdata", "Kamindu Mendis", SL, SL) is None
    assert m.unmatched == ["Kusal Mendis", "Kamindu Mendis"]


def test_register_resolves_kusal_then_rules_him_out_for_kamindu():
    reg = Register({"kusal mendis": {"kusal"}})          # names.csv: 5d1e7582 = "Kusal Mendis"
    m = CoverageMatcher(MemoryStore(), reg)
    got = m.resolve_all("cricketdata", [(1, "Kamindu Mendis", SL, SL), (2, "Kusal Mendis", SL, SL)])
    assert got == {1: "kamindu", 2: "kusal"} and m.unmatched == []


def test_register_hit_outside_the_team_is_not_used():
    reg = Register({"dasun shanaka": {"someone-else"}})
    m = CoverageMatcher(MemoryStore(), reg)
    assert m.resolve("cricketdata", "Dasun Shanaka", SL, SL) == "shanaka"    # falls through to step b


def test_coverage_warning_when_more_than_one_unmatched():
    s = base_store()
    s.hist["p"] = [hist_row(f"2026-09-{d:02d}", 10) for d in range(1, 12)]
    r = score_match(s, None, POINTS, "M", ["p"], "pre_toss", unmatched_names=["A", "B"], coverage=(20, 22))
    assert "20 of 22 players matched" in r.warnings and any("2 players unmatched" in w for w in r.warnings)


# fix-up 2: fallback never sees the match date or later --------------------------
def test_fallback_step2_ignores_matches_on_or_after_the_match_date():
    s = base_store()
    s.hist["p"] = [hist_row("2026-01-01", 20, group="ODI_men"), hist_row("2026-10-13", 500, group="ODI_men"),
                   hist_row("2026-11-01", 500, group="ODI_men")]
    s.scaling[("ODI_men", "T20_men")] = 0.5
    r = fallback(s, None, POINTS, "p", "T20_men", "2026-10-13")
    assert (r.step, r.base_score) == (2, 10.0)


# fix-up 3: placeholder photo means no photo --------------------------------------
def test_placeholder_image_is_stored_as_none():
    from engine.sources.cricketdata import PLACEHOLDER_IMG, clean_image_url
    squad_img = fixture("match_squad")["data"][0]["players"][0]["playerImg"]
    assert squad_img == PLACEHOLDER_IMG and clean_image_url(squad_img) is None
    assert clean_image_url("https://g.cricapi.com/iapi/66-637877075103236690.webp") is not None
    assert clean_image_url(None) is None
