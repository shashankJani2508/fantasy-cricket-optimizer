"""Optimizer, bench and validity gate tests (OPTIMIZER.md section 7).
TEST_RULES are made-up values for testing only; real rules come from config/dream11_rules.yaml."""
import copy
import itertools

import pytest

from engine.gate import RulesError, load_rules, validate
from engine.optimizer import NoValidTeam, _solve, bench, best_team
from engine.env import ROOT

TEST_RULES = {"players": 11, "credit_budget": 100, "max_per_side": 7, "captain_multiplier": 2, "vc_multiplier": 1.5,
              "role_limits": {"WK": {"min": 1, "max": 4}, "BAT": {"min": 3, "max": 6},
                              "AR": {"min": 1, "max": 4}, "BOWL": {"min": 3, "max": 6}}}


def pool():
    roles = ["WK", "WK", "BAT", "BAT", "BAT", "BAT", "AR", "AR", "BOWL", "BOWL", "BOWL"]
    players = {}
    for side, base in (("A", 0), ("B", 100)):
        for i, role in enumerate(roles):
            pid = f"{side}{i}"
            players[pid] = {"name": pid, "side": side, "role": role, "credits": 8.0 + (i % 4) * 0.5,
                            "score": 30 + ((i * 7 + base) % 23), "thin": False}
    return players


def brute_force_best(players, rules):
    best = None
    ids = sorted(players)
    for team in itertools.combinations(ids, 11):
        top = sorted((players[p]["score"] for p in team), reverse=True)
        total = sum(top) + top[0] * (rules["captain_multiplier"] - 1) + top[1] * (rules["vc_multiplier"] - 1)
        cap = max(team, key=lambda p: players[p]["score"])
        vc = max((p for p in team if p != cap), key=lambda p: players[p]["score"])
        if validate(team, cap, vc, players, rules).passed and (best is None or total > best + 1e-9):
            best = total
    return best


def test_team_passes_gate_and_captain_is_top_scorer():
    p = pool()
    t = best_team(p, TEST_RULES)
    assert validate(t.player_ids, t.captain_id, t.vc_id, p, TEST_RULES).passed
    scores = sorted((p[x]["score"] for x in t.player_ids), reverse=True)
    assert p[t.captain_id]["score"] == scores[0] and p[t.vc_id]["score"] == scores[1]


def test_optimizer_is_exact_on_a_small_pool():
    p = {k: v for k, v in pool().items() if k not in ("A5", "B5", "A1", "B3", "A8")}   # 17 players
    assert best_team(p, TEST_RULES).total_expected == pytest.approx(brute_force_best(p, TEST_RULES))


def test_changing_a_setting_changes_the_result():
    p = pool()
    for pid in p:
        p[pid]["score"] = 100 if p[pid]["side"] == "A" else 10
    t7 = best_team(p, TEST_RULES)
    rules6 = copy.deepcopy(TEST_RULES); rules6["max_per_side"] = 6
    t6 = best_team(p, rules6)
    assert sum(p[x]["side"] == "A" for x in t7.player_ids) == 7
    assert sum(p[x]["side"] == "A" for x in t6.player_ids) == 6


def test_bench_reasons_match_forced_resolves():
    p = pool()
    t = best_team(p, TEST_RULES)
    for b in bench(p, TEST_RULES, t):
        forced = _solve(sorted(p), p, TEST_RULES, force=(b["player_id"],))
        if b["reason_code"] == "lower_score":
            assert forced is not None and round(t.total_expected - forced.total_expected, 2) == b["points_cost"]
        else:
            assert forced is None


def test_bench_names_the_credit_rule():
    p = pool()
    p["B0"].update(credits=40.0, score=200)      # too expensive to fit with 10 others
    t = best_team(p, TEST_RULES)
    reason = next(b for b in bench(p, TEST_RULES, t) if b["player_id"] == "B0")
    assert reason["reason_code"] == "credits" and "exceed credits" in reason["reason_detail"]


def test_tie_break_prefers_fewer_thin_players():
    p = pool()
    clone = dict(p["A2"], name="A2x", thin=True)
    p["A2"]["thin"] = False
    p["A2x"] = clone
    t = best_team(p, TEST_RULES)
    assert "A2" in t.player_ids or "A2x" not in t.player_ids


def test_no_valid_team_names_the_rule():
    p = {k: v for k, v in pool().items() if v["role"] != "WK"}
    with pytest.raises(NoValidTeam, match="wicket-keeper minimum"):
        best_team(p, TEST_RULES)


@pytest.mark.parametrize("edit,expected", [
    ("drop_one", "You have 10 players: add 1 more."),
    ("over_budget", "credits over: swap a player for a cheaper one."),
    ("too_few_bowlers", "bowlers: the minimum is 3."),
    ("side_cap", "players from A: the maximum is 7."),
    ("same_vc", "Choose a different vice-captain."),
    ("not_in_pool", "is not in the pool for this run"),
])
def test_gate_rejects_each_kind_of_invalid_edit(edit, expected):
    p = pool()
    t = best_team(p, TEST_RULES)
    team, cap, vc, pool_ids = list(t.player_ids), t.captain_id, t.vc_id, set(p)
    if edit == "drop_one":
        team = [x for x in team if x not in (cap, vc)][:8] + [cap, vc]
    elif edit == "over_budget":
        p[team[0]]["credits"] = 60
    elif edit == "too_few_bowlers":
        for x in team:
            if p[x]["role"] == "BOWL":
                p[x]["role"] = "BAT"
    elif edit == "side_cap":
        for x in team:
            p[x]["side"] = "A"
    elif edit == "same_vc":
        vc = cap
    elif edit == "not_in_pool":
        pool_ids = set(p) - {team[0]}
    g = validate(team, cap, vc, p, TEST_RULES, pool_ids)
    assert not g.passed and any(expected in msg for _, msg in g.failures)


def test_rules_loader_refuses_nulls(tmp_path):
    bad = tmp_path / "rules.yaml"
    bad.write_text((ROOT / "config" / "dream11_rules.yaml").read_text(encoding="utf8").replace("max_per_side: 7", "max_per_side: null", 1),
                   encoding="utf8")
    with pytest.raises(RulesError, match="Fill the Dream11 team rules"):
        load_rules(bad, "T20")
    assert load_rules(ROOT / "config" / "dream11_rules.yaml", "T20")["role_limits"]["BOWL"] == {"min": 1, "max": 7}
