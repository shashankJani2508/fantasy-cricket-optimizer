"""Neon/Postgres store used by the scoring engine (same methods as tests/engine/fakes.MemoryStore)."""
import json

import psycopg
import psycopg.sql
from psycopg.types.json import Jsonb

from backtest.parse import bat_band, normalise_venue
from engine.env import env

QUOTA = {"T20": 4, "ODI": 10}
TEST_SPLIT = 20   # config/backtest.yaml test_bowling_split (run 1)


def team_id(name, gender):
    return f"{gender}:{name}"


def venue_id(name):
    return "v:" + name


def derive_bowl_band(fmt, overs):
    if not overs:
        return "none"
    if fmt == "Test":   # scorecard rows only give match totals; TODO-CONFIRM (Cricsheet rows store the exact band)
        return "half_plus" if overs >= TEST_SPLIT else "under_half"
    return "half_plus" if overs >= QUOTA[fmt] / 2 else "under_half"


class PgStore:
    def __init__(self, url=None, schema="public"):
        self.conn = psycopg.connect(url or env("DATABASE_URL"), autocommit=True)
        self.conn.execute("SET TIME ZONE 'UTC'")
        # always explicit: Neon's pooled connections can carry a previous client's search_path
        self.conn.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))

    def q(self, sql, args=()):
        return self.conn.execute(sql, args).fetchall()

    def one(self, sql, args=()):
        r = self.conn.execute(sql, args).fetchone()
        return r[0] if r else None

    # settings / rubric
    def setting(self, key):
        return self.one("SELECT value FROM settings WHERE key = %s", (key,))

    def rubric_rows(self):
        cols = ["id", "format_group", "weights", "is_active", "reliable", "points_values_final"]
        return [dict(zip(cols, r)) for r in self.q(f"SELECT {', '.join(cols)} FROM rubric_versions")]

    # matches and history
    def match(self, mid):
        r = self.q("""SELECT m.id, m.start_time::date::text, m.format_group, v.name, ta.name, tb.name, bf.name,
                             m.cricketdata_id
                        FROM matches m LEFT JOIN venues v ON v.id = m.venue_id
                        LEFT JOIN teams ta ON ta.id = m.team_a_id LEFT JOIN teams tb ON tb.id = m.team_b_id
                        LEFT JOIN teams bf ON bf.id = m.batting_first_team_id WHERE m.id = %s""", (mid,))
        if not r:
            return None
        i, date, group, venue, a, b, bf, cd = r[0]
        series = None
        if cd:
            resp = self.one("SELECT response FROM api_cache WHERE source = 'cricketdata' AND request_key = %s",
                            ("match_info?id=" + cd,))
            series = ((resp or {}).get("data") or {}).get("series_id")
        return {"id": i, "date": date, "format_group": group, "venue": venue, "team_a": a, "team_b": b,
                "batting_first": bf, "series_id": series}

    def history(self, pid, before):
        rows = self.q("""
            SELECT m.start_time::date::text, p.format_group, v.name,
                   (SELECT t.name FROM teams t WHERE t.id = CASE WHEN x.team_id = m.team_a_id
                                                                 THEN m.team_b_id ELSE m.team_a_id END),
                   (m.batting_first_team_id IS NOT NULL AND m.batting_first_team_id = x.team_id),
                   p.batting_position, p.overs_bowled, p.bowling_band, p.total_points, p.is_provisional
              FROM player_match_points p JOIN matches m ON m.id = p.match_id
              LEFT JOIN match_xi x ON x.match_id = p.match_id AND x.player_id = p.player_id
              LEFT JOIN venues v ON v.id = m.venue_id
             WHERE p.player_id = %s AND m.start_time::date < %s::date AND NOT p.retired_hurt
             ORDER BY 1, m.id""", (pid, before))
        out = []
        for date, group, venue, opp, bf, pos, overs, band, pts, prov in rows:
            out.append({"date": date, "format_group": group, "venue": venue, "opponent": opp, "batted_first": bf,
                        "bat_band": bat_band(pos), "bowl_band": band or derive_bowl_band(group.split("_")[0], overs),
                        "points": pts, "is_provisional": prov})
        return out

    def dot_rate(self, pid, group, before, min_balls):
        """The player's exact dot-ball share from Cricsheet rows before `before`, or None if he has bowled
        fewer than min_balls legal balls in this format group."""
        balls, dots = self.q("""SELECT COALESCE(sum(p.balls_bowled), 0), COALESCE(sum(p.dot_balls), 0)
                                FROM player_match_points p JOIN matches m ON m.id = p.match_id
                                WHERE p.player_id = %s AND p.format_group = %s AND p.source = 'cricsheet'
                                  AND p.balls_bowled IS NOT NULL AND m.start_time::date < %s::date""",
                             (pid, group, before))[0]
        return dots / balls if balls >= min_balls else None

    def first_innings(self, group, before):
        return self.q("""SELECT m.start_time::date::text, v.name, m.first_innings_total FROM matches m
                         JOIN venues v ON v.id = m.venue_id
                         WHERE m.format_group = %s AND m.first_innings_total IS NOT NULL
                           AND m.start_time::date < %s::date ORDER BY 1""", (group, before))

    def team_players(self, team, gender, since=None):
        """Players who appeared for this team; with `since` (YYYY-MM-DD) only matches on or after it."""
        if since is None:
            return self.q("""SELECT DISTINCT p.id, p.full_name FROM match_xi x JOIN players p ON p.id = x.player_id
                             WHERE x.team_id = %s ORDER BY 1""", (team_id(team, gender),))
        return self.q("""SELECT DISTINCT p.id, p.full_name FROM match_xi x JOIN players p ON p.id = x.player_id
                         JOIN matches m ON m.id = x.match_id
                         WHERE x.team_id = %s AND m.start_time::date >= %s::date ORDER BY 1""",
                      (team_id(team, gender), since))

    def player_team_any(self, pid):
        return self.one("""SELECT t.name FROM match_xi x JOIN teams t ON t.id = x.team_id JOIN matches m ON m.id = x.match_id
                           WHERE x.player_id = %s ORDER BY m.start_time DESC LIMIT 1""", (pid,))

    def player_team(self, mid, pid):
        return self.one("""SELECT t.name FROM match_xi x JOIN teams t ON t.id = x.team_id
                           WHERE x.match_id = %s AND x.player_id = %s""", (mid, pid))

    # name links / players
    def links(self, source, name):
        return [r[0] for r in self.q("SELECT player_id FROM player_name_links WHERE source = %s AND source_name = %s",
                                     (source, name))]

    def add_link(self, pid, source, name, confirmed=False):
        self.conn.execute("""INSERT INTO player_name_links (player_id, source, source_name, confirmed_by_aryan, confirmed_at)
                             VALUES (%s, %s, %s, %s, CASE WHEN %s THEN now() END)
                             ON CONFLICT (source, source_name, player_id) DO UPDATE
                             SET confirmed_by_aryan = player_name_links.confirmed_by_aryan OR EXCLUDED.confirmed_by_aryan,
                                 confirmed_at = COALESCE(player_name_links.confirmed_at, EXCLUDED.confirmed_at)""",
                          (pid, source, name, confirmed, confirmed))

    def links_for_player(self, pid, source):
        return [r[0] for r in self.q("SELECT source_name FROM player_name_links WHERE player_id = %s AND source = %s",
                                     (pid, source))]

    def player_exists(self, pid):
        return self.one("SELECT 1 FROM players WHERE id = %s", (pid,)) is not None

    def player_cricketdata_id(self, pid):
        return self.one("SELECT cricketdata_id FROM players WHERE id = %s", (pid,))

    def set_cricketdata_id(self, pid, cd_id, image_url=None):
        from engine.sources.cricketdata import clean_image_url
        image_url = clean_image_url(image_url)   # CricketData.org's generic placeholder means no photo
        self.conn.execute("""UPDATE players SET cricketdata_id = COALESCE(cricketdata_id, %s::text),
                             image_url = COALESCE(image_url, %s::text),
                             image_source = CASE WHEN image_url IS NULL AND %s::text IS NOT NULL THEN 'cricketdata' ELSE image_source END,
                             updated_at = now() WHERE id = %s""", (cd_id, image_url, image_url, pid))

    def full_name(self, pid):
        return self.one("SELECT full_name FROM players WHERE id = %s", (pid,))

    # tables produced later (backtest run 2)
    def _optional(self, table, sql, args):
        if not self.one("SELECT to_regclass(%s)", (table,)):
            return None
        try:   # TODO-CONFIRM: column names of format_scaling / debutant_averages once run 2 creates them
            return self.one(sql, args)
        except psycopg.Error:
            return None

    def format_scaling(self, from_group, to_group):
        return self._optional("format_scaling", "SELECT ratio FROM format_scaling WHERE from_group = %s AND to_group = %s",
                              (from_group, to_group))

    def debutant_average(self, group):
        return self._optional("debutant_averages", "SELECT avg_points FROM debutant_averages WHERE format_group = %s", (group,))

    # writes
    def ensure_team(self, name, gender, cricketdata_id=None, short_code=None):
        tid = team_id(name, gender)
        self.conn.execute("""INSERT INTO teams (id, name, gender, cricsheet_name, cricketdata_id, short_code)
                             VALUES (%s, %s, %s, %s, %s, %s)
                             ON CONFLICT (id) DO UPDATE SET cricketdata_id = COALESCE(teams.cricketdata_id, EXCLUDED.cricketdata_id),
                               short_code = COALESCE(teams.short_code, EXCLUDED.short_code)""",
                          (tid, name, gender, name, cricketdata_id, short_code))
        return tid

    def ensure_venue(self, raw):
        name = normalise_venue(raw)
        city = raw.split(",", 1)[1].strip() if "," in raw else None
        self.conn.execute("""INSERT INTO venues (id, name, city) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                          (venue_id(name), name, city))
        return venue_id(name)

    def ensure_cricketdata_match(self, info, fmt, gender, group, base_team=lambda t: t):
        teams = [base_team(t) for t in info.get("teams", [])]
        tids = [self.ensure_team(t, gender) for t in teams]
        vid = self.ensure_venue(info["venue"]) if info.get("venue") else None
        toss = next((t for t in teams if t.lower() == str(info.get("tossWinner", "")).lower()
                     or base_team(t).lower() == str(info.get("tossWinner", "")).lower()), None)
        bf = None
        if toss and info.get("tossChoice") in ("bat", "bowl"):
            bf = toss if info["tossChoice"] == "bat" else next(t for t in teams if t != toss)
        self.conn.execute("""
            INSERT INTO matches (id, cricketdata_id, format, gender, format_group, series_name, venue_id,
                                 team_a_id, team_b_id, start_time, status, toss_winner_team_id, toss_decision,
                                 batting_first_team_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, toss_winner_team_id = EXCLUDED.toss_winner_team_id,
              toss_decision = EXCLUDED.toss_decision, batting_first_team_id = EXCLUDED.batting_first_team_id,
              updated_at = now()""",
            ("cd:" + info["id"], info["id"], fmt, gender, group, info.get("name"), vid,
             tids[0] if tids else None, tids[1] if len(tids) > 1 else None, info.get("dateTimeGMT"),
             info.get("status"), team_id(toss, gender) if toss else None, info.get("tossChoice"),
             team_id(bf, gender) if bf else None))
        return "cd:" + info["id"]

    def match_has_cricsheet(self, mid, cd_id):
        return bool(self.one("""SELECT 1 FROM player_match_points p JOIN matches m ON m.id = p.match_id
                                WHERE (m.id = %s OR m.cricketdata_id = %s) AND p.source = 'cricsheet' LIMIT 1""",
                             (mid, cd_id)))

    def set_xi(self, mid, team, gender, pid, source):
        tid = self.ensure_team(team, gender)
        self.conn.execute("""INSERT INTO match_xi (match_id, team_id, player_id, source) VALUES (%s, %s, %s, %s)
                             ON CONFLICT (match_id, player_id) DO UPDATE SET team_id = EXCLUDED.team_id,
                             source = EXCLUDED.source, fetched_at = now()""", (mid, tid, pid, source))

    def upsert_points(self, r):
        cols = ["player_id", "match_id", "format_group", "batting_points", "bowling_points", "fielding_points",
                "total_points", "batting_position", "overs_bowled", "bowling_band", "retired_hurt", "source",
                "is_provisional", "balls_bowled", "dot_balls", "dot_balls_estimated"]
        r = {"balls_bowled": None, "dot_balls": None, "dot_balls_estimated": False, **r}
        upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols[2:])
        got = self.conn.execute(f"""
            INSERT INTO player_match_points ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})
            ON CONFLICT (player_id, match_id) DO UPDATE SET {upd}, updated_at = now()
            WHERE player_match_points.source <> 'cricsheet' OR EXCLUDED.source = 'cricsheet'
            RETURNING id""", [r[c] for c in cols]).fetchone()
        return got is not None

    # cache / budget
    def cache_get(self, source, key):
        r = self.q("SELECT response, fetched_at, expires_at FROM api_cache WHERE source = %s AND request_key = %s",
                   (source, key))
        return {"response": r[0][0], "fetched_at": r[0][1], "expires_at": r[0][2]} if r else None

    def cache_put(self, source, key, resp, fetched, expires):
        self.conn.execute("""INSERT INTO api_cache (source, request_key, response, fetched_at, expires_at)
                             VALUES (%s, %s, %s, %s, %s) ON CONFLICT (source, request_key) DO UPDATE
                             SET response = EXCLUDED.response, fetched_at = EXCLUDED.fetched_at,
                                 expires_at = EXCLUDED.expires_at""", (source, key, Jsonb(resp), fetched, expires))

    def usage_get(self, source, date):
        return self.one("SELECT calls FROM api_usage WHERE source = %s AND date = %s", (source, date)) or 0

    def usage_add(self, source, date, n):
        self.conn.execute("""INSERT INTO api_usage (source, date, calls) VALUES (%s, %s, %s)
                             ON CONFLICT (source, date) DO UPDATE SET calls = api_usage.calls + EXCLUDED.calls""",
                          (source, date, n))

    def usage_by_prefix(self, prefix, date):
        return self.q("SELECT source, calls FROM api_usage WHERE source LIKE %s AND date = %s ORDER BY source",
                      (prefix + "%", date))

    def usage_set_at_least(self, source, date, n):
        self.conn.execute("""INSERT INTO api_usage (source, date, calls) VALUES (%s, %s, %s)
                             ON CONFLICT (source, date) DO UPDATE SET calls = GREATEST(api_usage.calls, EXCLUDED.calls)""",
                          (source, date, n))

    # runs / predictions
    def create_run(self, mid, run_type):
        return str(self.one("""INSERT INTO runs (match_id, run_type, status, started_at)
                               VALUES (%s, %s, 'scoring', now()) RETURNING id""", (mid, run_type)))

    def finish_run(self, rid, status, step, err, version, stale):
        self.conn.execute("""UPDATE runs SET status = %s, failed_step = %s, error_message = %s, rubric_version_id = %s,
                             data_stale = %s, finished_at = now() WHERE id = %s""",
                          (status, step, err, version, stale, rid))

    def save_prediction(self, rid, p):
        self.conn.execute("""INSERT INTO predictions (run_id, player_id, factors, trust, fallback_step, fallback_note,
                             thin_data, provisional_inputs, provisional_weights, borrowed_from_group, base_score)
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                          (rid, p["player_id"], Jsonb(p["factors"]), Jsonb(p["trust"]), p["fallback_step"],
                           p["fallback_note"], p["thin_data"], p["provisional_inputs"], p["provisional_weights"],
                           p["borrowed_from_group"], p["base_score"]))
