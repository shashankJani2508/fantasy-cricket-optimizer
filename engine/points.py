"""Dream11 fantasy points from per-player match stats (shared with the live app).

Point values come only from config/dream11_points.yaml; nothing here is hardcoded.
Stats come from backtest/parse.py (or the live app's equivalent):

  stats = {
    "bat":  [{"runs", "balls", "fours", "sixes", "out"}],     # one entry per innings batted
    "bowl": [{"balls", "runs", "dots", "maidens", "wickets", "lbw_bowled"}],  # per innings bowled
    "catches", "stumpings", "ro_direct", "ro_indirect", "in_xi",
  }
"""
from pathlib import Path

import yaml

FORMATS = ("T20", "ODI", "Test")
MODES = ("highest", "cumulative")


class PointsConfigError(Exception):
    pass


def find_nulls(node, path=""):
    """Every dotted path in the config whose value is null."""
    if node is None:
        return [path]
    if isinstance(node, dict):
        out = []
        for k, v in node.items():
            out += find_nulls(v, f"{path}.{k}" if path else str(k))
        return out
    if isinstance(node, list):
        out = []
        for i, v in enumerate(node):
            out += find_nulls(v, f"{path}[{i}]")
        return out
    return []


def load_points_config(path):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf8"))
    missing = [f for f in FORMATS if f not in (cfg or {})]
    if missing:
        raise PointsConfigError(f"{path}: missing format sections: {', '.join(missing)}")
    nulls = find_nulls({f: cfg[f] for f in FORMATS})
    if nulls:
        raise PointsConfigError(
            f"{path} still has {len(nulls)} null value(s); fill them in from the Dream11 app:\n  "
            + "\n  ".join(nulls))
    for f in FORMATS:
        for section, key in (("batting", "milestone_mode"), ("bowling", "haul_mode")):
            if cfg[f][section][key] not in MODES:
                raise PointsConfigError(f"{f}.{section}.{key} must be one of {MODES}")
    return cfg


def _threshold_bonus(value, rows, key, mode):
    hit = [r for r in rows if value >= r[key]]
    if not hit:
        return 0.0
    if mode == "cumulative":
        return float(sum(r["value"] for r in hit))
    return float(max(hit, key=lambda r: r[key])["value"])


def _band(x, bands):
    for b in bands:
        if b["min"] <= x < b["max"]:
            return float(b["value"])
    return 0.0


def batting_points(innings, c):
    pts = 0.0
    for inn in innings:
        pts += inn["runs"] * c["run"] + inn["fours"] * c["boundary_bonus"] + inn["sixes"] * c["six_bonus"]
        pts += _threshold_bonus(inn["runs"], c["milestones"], "runs", c["milestone_mode"])
        if inn["out"] and inn["runs"] == 0:
            pts += c["duck"]
        sr = c["strike_rate"]
        if inn["balls"] > 0 and inn["balls"] >= sr["min_balls"] and sr["bands"]:
            pts += _band(100.0 * inn["runs"] / inn["balls"], sr["bands"])
    return pts


def bowling_points(innings, c):
    pts = 0.0
    for inn in innings:
        pts += inn["wickets"] * c["wicket"] + inn["lbw_bowled"] * c["lbw_bowled_bonus"]
        pts += inn["dots"] * c["dot_ball"] + inn["maidens"] * c["maiden"]
        pts += _threshold_bonus(inn["wickets"], c["hauls"], "wickets", c["haul_mode"])
        eco = c["economy"]
        overs = inn["balls"] / 6.0
        if overs > 0 and overs >= eco["min_overs"] and eco["bands"]:
            pts += _band(inn["runs"] / overs, eco["bands"])
    return pts


def fielding_points(s, c):
    pts = s["catches"] * c["catch"] + s["stumpings"] * c["stumping"]
    pts += s["ro_direct"] * c["run_out_direct"] + s["ro_indirect"] * c["run_out_indirect"]
    if s["catches"] >= c["catch_haul"]["catches"]:
        pts += c["catch_haul"]["value"]
    return float(pts)


def player_points(stats, fmt, cfg):
    """Returns batting, bowling, fielding (incl. playing-XI) and total points for one match."""
    c = cfg[fmt]
    bat = batting_points(stats["bat"], c["batting"])
    bowl = bowling_points(stats["bowl"], c["bowling"])
    field = fielding_points(stats, c["fielding"])
    xi = float(c["other"]["playing_xi"]) if stats["in_xi"] else 0.0
    return {"batting": bat, "bowling": bowl, "fielding": field, "playing_xi": xi,
            "total": bat + bowl + field + xi}
