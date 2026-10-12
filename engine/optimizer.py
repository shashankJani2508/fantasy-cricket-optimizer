"""Optimizer: best valid 11 + captain + vice-captain, and the bench 4 (OPTIMIZER.md sections 3 and 4).

Integer programme solved exactly with SciPy's milp (HiGHS). Per player three yes/no variables:
picked, captain, vice-captain. Objective = sum(score x picked) + (C - 1) x captain's score
+ (VC - 1) x vice-captain's score. Tie-break: fewer thin-data players (a tiny penalty that can
never outweigh a real points difference).
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from engine.gate import ROLE_NAMES, ROLES, validate

THIN_PENALTY = 1e-6


class NoValidTeam(Exception):
    pass


@dataclass
class Team:
    player_ids: list
    captain_id: str
    vc_id: str
    total_expected: float      # incl. captain and VC multipliers
    credits_used: float


def _solve(pids, players, rules, force=(), drop=()):
    """Return Team or None if infeasible. drop: constraint names to leave out (for diagnosis)."""
    n = len(pids)
    cm, vm = rules["captain_multiplier"], rules["vc_multiplier"]
    s = np.array([players[p]["score"] for p in pids], dtype=float)
    thin = np.array([1.0 if players[p].get("thin") else 0.0 for p in pids])
    # variable order: x[0:n], c[n:2n], v[2n:3n]; milp minimises
    c_obj = -np.concatenate([s - THIN_PENALTY * thin, (cm - 1) * s, (vm - 1) * s])
    rows, lo, hi = [], [], []

    def add(coef_x=None, coef_c=None, coef_v=None, l=-np.inf, h=np.inf):
        row = np.zeros(3 * n)
        if coef_x is not None:
            row[:n] = coef_x
        if coef_c is not None:
            row[n:2 * n] = coef_c
        if coef_v is not None:
            row[2 * n:] = coef_v
        rows.append(row); lo.append(l); hi.append(h)

    ones = np.ones(n)
    add(ones, l=rules["players"], h=rules["players"])
    if "credits" not in drop:
        add(np.array([players[p]["credits"] for p in pids], dtype=float), h=rules["credit_budget"])
    for role in ROLES:
        mask = np.array([1.0 if players[p]["role"] == role else 0.0 for p in pids])
        lim = rules["role_limits"][role]
        add(mask, l=lim["min"] if f"min:{role}" not in drop else -np.inf,
            h=lim["max"] if f"max:{role}" not in drop else np.inf)
    if "side_cap" not in drop:
        for side in sorted({players[p]["side"] for p in pids}):
            add(np.array([1.0 if players[p]["side"] == side else 0.0 for p in pids]), h=rules["max_per_side"])
    add(coef_c=ones, l=1, h=1)
    add(coef_v=ones, l=1, h=1)
    for i in range(n):
        e = np.zeros(n); e[i] = 1
        add(coef_x=-e, coef_c=e, h=0)          # captain must be picked
        add(coef_x=-e, coef_v=e, h=0)          # vice-captain must be picked
        add(coef_c=e, coef_v=e, h=1)           # not the same player
    lb = np.zeros(3 * n)
    for p in force:
        lb[pids.index(p)] = 1
    res = milp(c_obj, constraints=LinearConstraint(np.array(rows), lo, hi), integrality=np.ones(3 * n),
               bounds=Bounds(lb, np.ones(3 * n)))
    if res.status != 0 or res.x is None:
        return None
    x = np.round(res.x).astype(int)
    team = [pids[i] for i in range(n) if x[i]]
    cap = next(pids[i] for i in range(n) if x[n + i])
    vc = next(pids[i] for i in range(n) if x[2 * n + i])
    total = sum(players[p]["score"] for p in team) + (cm - 1) * players[cap]["score"] + (vm - 1) * players[vc]["score"]
    return Team(sorted(team, key=lambda p: (-players[p]["score"], p)), cap, vc, round(total, 4),
                round(sum(players[p]["credits"] for p in team), 2))


def _diagnose(pids, players, rules, force=()):
    """Name the rule that makes a team impossible (first one whose removal makes it feasible)."""
    for name in ["credits", "side_cap"] + [f"{k}:{r}" for r in ROLES for k in ("max", "min")]:
        t = _solve(pids, players, rules, force, drop=(name,))
        if t is None:
            continue
        if name == "credits":
            return "credits", f"would exceed credits by {round(t.credits_used - rules['credit_budget'], 2):g}"
        if name == "side_cap":
            return "side_cap", f"would break the per-side cap of {rules['max_per_side']}"
        kind, role = name.split(":")
        word = "maximum" if kind == "max" else "minimum"
        return "role_limit", f"would break the {ROLE_NAMES[role][:-1]} {word} ({rules['role_limits'][role][kind]})"
    return "role_limit", "no valid team with this player under the current rules"


def best_team(players, rules, pool_ids=None):
    """players: {id: {"name", "side", "role", "credits", "score", "thin"}}. Raises NoValidTeam with the rule."""
    pids = sorted(p for p in players if pool_ids is None or p in pool_ids)
    if len(pids) < rules["players"]:
        raise NoValidTeam(f"Only {len(pids)} players in the pool: need {rules['players']}.")
    team = _solve(pids, players, rules)
    if team is None:
        _, why = _diagnose(pids, players, rules)
        raise NoValidTeam(f"No valid team: {why}. Check the credits and roles you entered.")
    gate = validate(team.player_ids, team.captain_id, team.vc_id, players, rules, set(pids))
    if not gate.passed:   # should never happen; the gate is the final word
        raise NoValidTeam(f"Optimizer team failed the gate: {gate.first_fix}")
    return team


def bench(players, rules, team, size=4, pool_ids=None):
    """The `size` best unpicked players, each with the solver's real reason (forced re-solve)."""
    pids = sorted(p for p in players if pool_ids is None or p in pool_ids)
    out = []
    left = sorted((p for p in pids if p not in team.player_ids), key=lambda p: (-players[p]["score"], p))
    for rank, p in enumerate(left[:size], start=1):
        forced = _solve(pids, players, rules, force=(p,))
        if forced is None:
            code, detail = _diagnose(pids, players, rules, force=(p,))
            out.append({"player_id": p, "rank": rank, "reason_code": code, "reason_detail": detail, "points_cost": None})
        else:
            cost = round(team.total_expected - forced.total_expected, 2)
            out.append({"player_id": p, "rank": rank, "reason_code": "lower_score",
                        "reason_detail": f"fits, but the team scores {cost:g} points less", "points_cost": cost})
    return out
