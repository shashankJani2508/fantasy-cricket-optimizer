"""Provisional points from CricketData.org scorecards for recent matches not yet on Cricsheet (spec 9.4).

TODO-CONFIRM: the spec says "CricketData.org match lists". To protect the 100-calls-a-day budget this
uses the match list of the target match's own series (series_info, cached 6 h) rather than paging the
all-matches list. Each scorecard costs 10 calls and is cached 7 days.
"""
import datetime as dt

from engine.groups import spec_group
from engine.matching import Matcher
from engine.points import from_scorecard


def match_format(match_type, name):
    """CricketData.org matchType -> our format. None = not supported (e.g. The Hundred)."""
    if "hundred" in (name or "").lower():
        return None
    # the match name wins when it is explicit: CricketData.org's series list tagged
    # "India vs West Indies, 4th T20I" as matchType "odi" (seen 13 Oct 2026)
    import re
    n = name or ""
    if re.search(r"\bT20I?\b", n):
        return "T20"
    if re.search(r"\bODI\b", n):
        return "ODI"
    if re.search(r"\bTest\b", n):
        return "Test"
    return {"t20": "T20", "odi": "ODI", "test": "Test"}.get((match_type or "").lower())


def gender_of(team_names):
    return "female" if any(t.lower().endswith(" women") for t in team_names) else "male"


def base_team(name):
    return name[:-6] if name.lower().endswith(" women") else name


def scorecard_rows(scorecard):
    """Per-player rows from a match_scorecard `data` object -> {(team, name, cricketdata_id): row}."""
    teams = scorecard.get("teams", [])
    rows = {}

    def row(team, p):
        k = (team, p["name"], p.get("id"))
        return rows.setdefault(k, {"bat": [], "bowl": [], "lbw_bowled": 0,
                                   "catching": {"catch": 0, "cb": 0, "stumped": 0, "runout": 0}})

    prev_bat = None
    for inn in scorecard.get("scorecard", []):
        # Real labels vary: "Pakistan Inning 1", "sri lanka Inning 1", even "Pakistan,Sri Lanka Inning 1".
        label = inn["inning"].lower()
        hits = [t for t in teams if label.startswith(t.lower() + " ")]
        if len(hits) == 1:
            bat_team = hits[0]
        else:   # ambiguous label: innings alternate, so it's the side that didn't bat last
            bat_team = next((t for t in teams if t != prev_bat), None) if prev_bat else None
        if bat_team is None:
            continue
        prev_bat = bat_team
        field_team = next((t for t in teams if t != bat_team), None)
        for pos, b in enumerate(inn.get("batting", []), start=1):
            row(bat_team, b["batsman"])["bat"].append({**b, "position": pos})
            if b.get("dismissal") in ("lbw", "bowled") and b.get("bowler"):   # TODO-CONFIRM names
                row(field_team, b["bowler"])["lbw_bowled"] += 1
        for w in inn.get("bowling", []):
            row(field_team, w["bowler"])["bowl"].append(w)
        for c in inn.get("catching", []):
            r = row(field_team, c["catcher"])["catching"]
            for f in ("catch", "cb", "stumped", "runout"):
                r[f] += c.get(f, 0)
    return rows


def fill_recent(store, client, points_cfg, player_ids, match_date, series_id, days=30, dot_min_balls=60):
    """Upsert provisional (source='scorecard') points for finished matches of this series in the last
    `days` days before match_date. Never overwrites a cricsheet row. Returns a list of notes."""
    notes = []
    if not series_id:
        return notes
    start = (dt.date.fromisoformat(match_date) - dt.timedelta(days=days)).isoformat()
    wanted = set(player_ids)
    for m in client.series_info(series_id).get("matchList", []):
        if not m.get("matchEnded") or not (start <= m.get("date", "") < match_date):
            continue
        fmt = match_format(m.get("matchType"), m.get("name"))
        if fmt is None:
            continue
        mid = "cd:" + m["id"]
        if store.match_has_cricsheet(mid, m["id"]):
            continue
        sc = client.match_scorecard(m["id"])
        if not sc:
            continue
        gender = gender_of(m.get("teams", []))
        group = spec_group(fmt, gender)
        store.ensure_cricketdata_match(sc, fmt, gender, group, base_team=base_team)
        matcher = Matcher(store)
        added = 0
        for (team, name, cd_pid), row in scorecard_rows(sc).items():
            pid = matcher.resolve("cricketdata", name, store.team_players(base_team(team), gender))
            if pid is None or pid not in wanted:
                continue
            balls = sum(int(b["o"]) * 6 + int(round((b["o"] - int(b["o"])) * 10)) for b in row["bowl"])
            rate = store.dot_rate(pid, group, m.get("date", match_date), dot_min_balls) if balls else None
            pts = from_scorecard(row, fmt, points_cfg, dot_rate=rate)
            dots = int(round(balls * rate)) if rate is not None else None
            overs = sum(int(b["o"]) + (b["o"] - int(b["o"])) * 10 / 6 for b in row["bowl"])
            pos = row["bat"][0]["position"] if row["bat"] else None
            store.set_xi(mid, base_team(team), gender, pid, "scorecard")
            if store.upsert_points({"player_id": pid, "match_id": mid, "format_group": group,
                                    "batting_points": pts["batting"], "bowling_points": pts["bowling"],
                                    "fielding_points": pts["fielding"], "total_points": pts["total"],
                                    "batting_position": pos, "overs_bowled": round(overs, 2),
                                    "bowling_band": None, "retired_hurt": False,
                                    "balls_bowled": balls, "dot_balls": dots, "dot_balls_estimated": dots is not None,
                                    "source": "scorecard", "is_provisional": True}):
                added += 1
        notes.append(f"{m['name']}: {added} provisional scorecard rows")
    return notes
