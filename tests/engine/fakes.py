"""In-memory store with the same methods as engine.db.PgStore, so tests make no network or DB calls."""
import itertools
import json
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "cricketdata"

SETTINGS = {"form_window": 10, "form_recent_double": 5, "current_touch_matches": 5, "current_touch_days": 30,
            "thin_data_full_trust": 10, "cold_start_min_matches": 3, "pitch_type_min_matches": 5,
            "thin_data_trust_threshold": 0.5, "cricketdata_daily_limit": 95, "dot_rate_min_balls": 60}


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf8"))


class MemoryStore:
    def __init__(self):
        self.settings = dict(SETTINGS)
        self.rubric = []
        self.matches = {}
        self.hist = {}            # player_id -> [history row]
        self.fi = []              # (group, date, venue, total)
        self.teams = {}           # (team, gender) -> [(pid, name)]
        self.recent = {}          # (team, gender) -> [(pid, name)] in the last 12 months
        self.link = {}            # (source, name) -> [pid]
        self.points = {}          # (pid, match_id) -> row
        self.xi = {}              # (match_id, pid) -> team
        self.cd_ids = {}
        self.scaling = {}
        self.dots = {}            # (pid, group) -> (past balls, past dots)
        self.debut = {}
        self.cache, self.usage = {}, {}
        self.runs, self.preds = {}, []
        self._ids = itertools.count(1)

    def setting(self, k): return self.settings.get(k)
    def rubric_rows(self): return self.rubric
    def match(self, mid): return self.matches.get(mid)
    def history(self, pid, before):
        return sorted([r for r in self.hist.get(pid, []) if r["date"] < before], key=lambda r: r["date"])
    def dot_rate(self, pid, group, before, min_balls):
        b, d = self.dots.get((pid, group), (0, 0))
        return d / b if b >= min_balls else None
    def first_innings(self, group, before): return [(d, v, t) for g, d, v, t in self.fi if g == group and d < before]
    def team_players(self, team, gender, since=None):
        return self.recent.get((team, gender), []) if since else self.teams.get((team, gender), [])
    def links(self, source, name): return list(self.link.get((source, name), []))
    def add_link(self, pid, source, name, confirmed=False): self.link.setdefault((source, name), []).append(pid)
    def links_for_player(self, pid, source): return [n for (s, n), ps in self.link.items() if s == source and pid in ps]
    def player_team(self, mid, pid): return self.xi.get((mid, pid))
    def player_cricketdata_id(self, pid): return self.cd_ids.get(pid)
    def format_scaling(self, a, b): return self.scaling.get((a, b))
    def debutant_average(self, g): return self.debut.get(g)
    def match_has_cricsheet(self, mid, cd_id): return any(k[1] == mid and r["source"] == "cricsheet" for k, r in self.points.items())
    def ensure_cricketdata_match(self, sc, fmt, gender, group, base_team=None): self.matches.setdefault("cd:" + sc["id"], {"id": "cd:" + sc["id"]})
    def set_xi(self, mid, team, gender, pid, source): self.xi[(mid, pid)] = team

    def upsert_points(self, row):
        key = (row["player_id"], row["match_id"])
        old = self.points.get(key)
        if old and old["source"] == "cricsheet" and row["source"] == "scorecard":
            return False
        self.points[key] = dict(row)
        return True

    def cache_get(self, source, key): return self.cache.get((source, key))
    def cache_put(self, source, key, resp, fetched, expires):
        self.cache[(source, key)] = {"response": resp, "fetched_at": fetched, "expires_at": expires}
    def usage_get(self, source, date): return self.usage.get((source, date), 0)
    def usage_add(self, source, date, n): self.usage[(source, date)] = self.usage_get(source, date) + n

    def create_run(self, mid, run_type):
        rid = f"run{next(self._ids)}"
        self.runs[rid] = {"match_id": mid, "run_type": run_type, "status": "scoring"}
        return rid
    def finish_run(self, rid, status, step, err, version, stale):
        self.runs[rid].update(status=status, failed_step=step, error_message=err, rubric_version_id=version, data_stale=stale)
    def save_prediction(self, rid, p): self.preds.append({"run_id": rid, **p})


def hist_row(date, points, group="T20_men", venue="V", opponent="X", batted_first=True,
             bat_band="1-3", bowl_band="none", provisional=False):
    return {"date": date, "format_group": group, "venue": venue, "opponent": opponent, "batted_first": batted_first,
            "bat_band": bat_band, "bowl_band": bowl_band, "points": points, "is_provisional": provisional}


def weights(**w):
    from engine.factors import FACTORS
    return {k: w.get(k, 0.0) for k in FACTORS}
