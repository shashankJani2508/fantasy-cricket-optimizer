"""Dream11 team rules loader and the validity gate (OPTIMIZER.md sections 3 and 5).

Every team (the optimizer's and every edit Aryan makes) goes through validate(); an invalid team
cannot be saved. Rules come from config/dream11_rules.yaml (seeded into Neon dream11_rules later),
never from code.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from engine.points import find_nulls

ROLES = ("WK", "BAT", "AR", "BOWL")
ROLE_NAMES = {"WK": "wicket-keepers", "BAT": "batters", "AR": "all-rounders", "BOWL": "bowlers"}


class RulesError(Exception):
    pass


def load_rules(path, fmt):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf8"))
    if fmt not in (cfg or {}):
        raise RulesError(f"{path}: no rules for format {fmt}")
    nulls = find_nulls(cfg[fmt], fmt)
    if nulls:
        raise RulesError("Fill the Dream11 team rules in Settings. Missing: " + ", ".join(nulls))
    r = cfg[fmt]
    if set(r["role_limits"]) != set(ROLES):
        raise RulesError(f"role_limits must cover exactly {ROLES}")
    return r


@dataclass
class GateResult:
    passed: bool
    failures: list = field(default_factory=list)   # [(rule, message)], first one is the fix to show

    @property
    def first_fix(self):
        return self.failures[0][1] if self.failures else None


def _fmt(x):
    return f"{x:g}"


def validate(team_ids, captain_id, vc_id, players, rules, pool_ids=None):
    """players: {player_id: {"name", "side", "role", "credits"}}; pool_ids: who may be picked (None = all)."""
    fails = []
    ids = list(team_ids)
    n = rules["players"]
    if len(set(ids)) != len(ids):
        fails.append(("duplicates", "The same player is in the team twice: remove the duplicate."))
    uniq = list(dict.fromkeys(ids))
    if len(uniq) < n:
        fails.append(("size", f"You have {len(uniq)} players: add {n - len(uniq)} more."))
    elif len(uniq) > n:
        fails.append(("size", f"You have {len(uniq)} players: remove {len(uniq) - n}."))
    unknown = [p for p in uniq if p not in players]
    for p in unknown:
        fails.append(("pool", f"Player {p} has no credits or role entered."))
    known = [p for p in uniq if p in players]
    if pool_ids is not None:
        for p in known:
            if p not in pool_ids:
                fails.append(("pool", f"{players[p]['name']} is not in the pool for this run (e.g. not in the confirmed XI)."))
    used = sum(players[p]["credits"] for p in known)
    if used > rules["credit_budget"] + 1e-9:
        fails.append(("credits", f"{_fmt(round(used - rules['credit_budget'], 2))} credits over: "
                                 "swap a player for a cheaper one."))
    for role in ROLES:
        cnt = sum(1 for p in known if players[p]["role"] == role)
        lim = rules["role_limits"][role]
        if cnt < lim["min"]:
            fails.append(("role_limit", f"Only {cnt} {ROLE_NAMES[role]}: the minimum is {lim['min']}."))
        elif cnt > lim["max"]:
            fails.append(("role_limit", f"{cnt} {ROLE_NAMES[role]}: the maximum is {lim['max']}."))
    sides = {}
    for p in known:
        sides[players[p]["side"]] = sides.get(players[p]["side"], 0) + 1
    for side, cnt in sorted(sides.items()):
        if cnt > rules["max_per_side"]:
            fails.append(("side_cap", f"{cnt} players from {side}: the maximum is {rules['max_per_side']}."))
    if captain_id not in uniq:
        fails.append(("captaincy", "Choose a captain from your 11."))
    if vc_id not in uniq:
        fails.append(("captaincy", "Choose a vice-captain from your 11."))
    if captain_id is not None and captain_id == vc_id:
        fails.append(("captaincy", "Choose a different vice-captain."))
    return GateResult(not fails, fails)
