"""refresh-cricsheet: load Cricsheet matches into Neon with points from engine/points.py (spec 8.2).

Reuses the run 1 parser (backtest/parse.py). Default: download Cricsheet's "recently added (7 days)"
zip and load only those matches. --full: load the whole cached 3-year window (first-time enrichment of
the rows copied from bt_player_match_points). source = 'cricsheet' replaces any 'scorecard' row for the
same player and match. Retired-hurt rows are skipped, as in run 1.
"""
import datetime as dt
import shutil
import urllib.request
import zipfile

import yaml

from backtest.download import ensure_data
from backtest.parse import load_matches
from engine.db import team_id, venue_id
from engine.env import ROOT
from engine.groups import spec_group
from engine.points import player_points

RECENT_URL = "https://cricsheet.org/downloads/recently_added_7_json.zip"


def _copy_upsert(conn, table, cols, rows, conflict, update_cols, where=None):
    if not rows:
        return 0
    tmp = f"tmp_{table}"
    conn.execute(f"CREATE TEMP TABLE IF NOT EXISTS {tmp} (LIKE {table} INCLUDING DEFAULTS)")
    conn.execute(f"TRUNCATE {tmp}")
    with conn.cursor() as cur, cur.copy(f"COPY {tmp} ({', '.join(cols)}) FROM STDIN") as cp:
        for r in rows:
            cp.write_row(r)
    upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    action = f"DO UPDATE SET {upd}" + (f" WHERE {where}" if where else "") if update_cols else "DO NOTHING"
    conn.execute(f"""INSERT INTO {table} ({', '.join(cols)})
                     SELECT DISTINCT ON ({conflict}) {', '.join(cols)} FROM {tmp}
                     ON CONFLICT ({conflict}) {action}""")
    return len(rows)


def refresh(store, points_cfg, full=False):
    bcfg = yaml.safe_load((ROOT / "config" / "backtest.yaml").read_text(encoding="utf8"))
    today = dt.date.today()
    start = today.replace(year=today.year - bcfg["window_years"])
    if full:
        raw = ensure_data(ROOT / "data")
    else:
        recent = ROOT / "data" / "recent"
        if recent.exists():
            shutil.rmtree(recent)
        recent.mkdir(parents=True)
        zpath = ROOT / "data" / "recently_added_7_json.zip"
        urllib.request.urlretrieve(RECENT_URL, zpath)
        with zipfile.ZipFile(zpath) as z:
            for n in z.namelist():
                if n.endswith(".json") and "/" not in n and "\\" not in n:
                    z.extract(n, recent)
        raw = recent
    matches, excluded, _ = load_matches(raw, bcfg, start.isoformat(), today.isoformat())
    teams, venues, mrows, prows, xrows, pts = {}, {}, [], {}, [], []
    for m in matches:
        g = m.gender
        group = spec_group(m.fmt, g)
        for t in m.teams:
            teams[team_id(t, g)] = (team_id(t, g), t, g, t)
        venues[venue_id(m.venue)] = (venue_id(m.venue), m.venue, m.venue)
        mrows.append((m.match_id, m.match_id, m.fmt, g, group, venue_id(m.venue), team_id(m.teams[0], g),
                      team_id(m.teams[1], g), m.date, "finished", team_id(m.batted_first, g), m.first_innings_total))
        for pid, pm in m.players.items():
            if pm.retired_hurt:
                continue
            prows[pid] = (pid, pm.name, g, pid)
            xrows.append((m.match_id, team_id(pm.team, g), pid, "cricsheet"))
            p = player_points(pm.stats, m.fmt, points_cfg)
            balls = sum(i["balls"] for i in pm.stats["bowl"])
            dots = sum(i["dots"] for i in pm.stats["bowl"])
            pts.append((pid, m.match_id, group, p["batting"], p["bowling"], p["fielding"], p["total"],
                        pm.bat_position, round(balls / 6, 2), pm.bowl_band, False, "cricsheet", False,
                        balls, dots, False))
    c = store.conn
    with c.transaction():
        _copy_upsert(c, "teams", ["id", "name", "gender", "cricsheet_name"], list(teams.values()), "id", [])
        _copy_upsert(c, "venues", ["id", "name", "cricsheet_name"], list(venues.values()), "id", [])
        _copy_upsert(c, "players", ["id", "full_name", "gender", "cricsheet_id"], list(prows.values()), "id", ["full_name"])
        _copy_upsert(c, "matches", ["id", "cricsheet_id", "format", "gender", "format_group", "venue_id", "team_a_id",
                                    "team_b_id", "start_time", "status", "batting_first_team_id", "first_innings_total"],
                     mrows, "id", ["venue_id", "team_a_id", "team_b_id", "start_time", "batting_first_team_id",
                                   "first_innings_total", "status"])
        _copy_upsert(c, "match_xi", ["match_id", "team_id", "player_id", "source"], xrows, "match_id, player_id",
                     ["team_id", "source"])
        _copy_upsert(c, "player_match_points",
                     ["player_id", "match_id", "format_group", "batting_points", "bowling_points", "fielding_points",
                      "total_points", "batting_position", "overs_bowled", "bowling_band", "retired_hurt", "source",
                      "is_provisional", "balls_bowled", "dot_balls", "dot_balls_estimated"], pts, "player_id, match_id",
                     ["format_group", "batting_points", "bowling_points", "fielding_points", "total_points",
                      "batting_position", "overs_bowled", "bowling_band", "source", "is_provisional",
                      "balls_bowled", "dot_balls", "dot_balls_estimated"])
    return {"matches": len(mrows), "points_rows": len(pts), "excluded": dict(excluded)}
