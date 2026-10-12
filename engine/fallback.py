"""Fallback chain for players with fewer than cold_start_min_matches earlier matches (spec 9.5).
Every step sets thin_data = true. Nothing is ever substituted that isn't in the data."""
from dataclasses import dataclass

from engine.groups import fmt_of

# CricketData.org players_info stats[].matchtype values seen in the saved fixture: ipl, odi, t20, t20i, test.
# TODO-CONFIRM: whether "t20" already includes T20Is (we assume it is the all-T20 figure).
MATCHTYPE = {"T20": "t20", "ODI": "odi", "Test": "test"}


@dataclass
class FallbackResult:
    base_score: float | None
    step: int
    note: str
    warnings: list


def _stat(stats, fn, matchtype, name):
    for s in stats:
        if s.get("fn") == fn and s.get("matchtype") == matchtype and str(s.get("stat", "")).strip() == name:
            try:
                return float(str(s.get("value")).strip())
            except ValueError:   # "-" means no data
                return None
    return None


def career_stats_estimate(stats, fmt, points_cfg):
    """Per-match estimate from career stats, using only point types the stats support.
    Catches are skipped: the saved players_info fixture has no catches stat."""
    mt = MATCHTYPE[fmt]
    c = points_cfg[fmt]
    parts, used = 0.0, []
    runs, inn = _stat(stats, "batting", mt, "runs"), _stat(stats, "batting", mt, "inn")
    if runs is not None and inn:
        parts += runs / inn * c["batting"]["run"]
        used.append("runs")
    wk, binn = _stat(stats, "bowling", mt, "wkts"), _stat(stats, "bowling", mt, "inn")
    if wk is not None and binn:
        parts += wk / binn * c["bowling"]["wicket"]
        used.append("wickets")
    return (parts, used) if used else (None, used)


def fallback(store, client, points_cfg, player_id, format_group):
    warnings = []
    # step 2: other formats x format_scaling
    by_group = {}
    for r in store.history(player_id, "9999-12-31"):
        if r["format_group"] != format_group:
            by_group.setdefault(r["format_group"], []).append(r["points"])
    usable = [(g, pts) for g, pts in by_group.items() if store.format_scaling(g, format_group) is not None]
    if usable:
        g, pts = max(usable, key=lambda gp: len(gp[1]))
        return FallbackResult(sum(pts) / len(pts) * store.format_scaling(g, format_group), 2,
                              "other formats x scaling", warnings)
    if by_group:
        warnings.append("format scaling not available")
    # step 3: CricketData.org career stats
    cd_id = store.player_cricketdata_id(player_id)
    if cd_id and client is not None:
        info = client.player_info(cd_id)
        est, used = career_stats_estimate(info.get("stats") or [], fmt_of(format_group), points_cfg)
        if est is not None:
            return FallbackResult(est, 3, f"career stats estimate ({', '.join(used)}; catches not in stats)", warnings)
    # step 4: debutant average, else no data
    avg = store.debutant_average(format_group)
    if avg is not None:
        return FallbackResult(avg, 4, "debutant average", warnings)
    return FallbackResult(None, 4, "no data", warnings)
