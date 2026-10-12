"""Parse Cricsheet JSON into matches with per-player stats, applying match-level exclusions.

Cricsheet fields used (verified against the downloaded data):
  info.match_type, info.gender, info.dates[0], info.venue, info.teams, info.players,
  info.registry.people, info.balls_per_over, info.overs, info.outcome.{result,method}
  innings[].team, innings[].super_over, innings[].target.overs,
  innings[].overs[].deliveries[].{batter, non_striker, bowler, runs.{batter,total,non_boundary},
                                  extras.{wides,noballs}, wickets[].{kind,player_out,fielders[].{name,substitute}}}
"""
import collections
import glob
import json
import os
from dataclasses import dataclass, field

BOWLER_WICKETS = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}
NOT_DISMISSED = {"retired hurt", "retired not out"}


@dataclass
class PlayerMatch:
    player_id: str
    name: str
    team: str
    opponent: str
    bat_position: int | None          # None = did not bat
    bat_band: str
    bowl_band: str
    retired_hurt: bool
    stats: dict


@dataclass
class Match:
    match_id: str
    date: str
    fmt: str                 # T20 / ODI / Test
    gender: str              # male / female
    match_type: str          # raw Cricsheet value
    venue: str
    teams: list
    batted_first: str        # team that batted in the first innings
    first_innings_total: int
    players: dict = field(default_factory=dict)   # player_id -> PlayerMatch

    @property
    def group(self):
        return f"{self.fmt}-{self.gender}"


def normalise_venue(v):
    # Cricsheet sometimes appends the city ("Eden Gardens, Kolkata"); keep the ground name.
    return v.split(",")[0].strip()


def bat_band(pos):
    if pos is None or pos >= 8:
        return "8+"
    if pos <= 3:
        return "1-3"
    if pos <= 5:
        return "4-5"
    return "6-7"


def bowl_band(fmt, bowl_innings, cfg):
    if not bowl_innings or sum(i["balls"] for i in bowl_innings) == 0:
        return "none"
    if fmt == "Test":
        overs = max(i["balls"] for i in bowl_innings) / 6
        return "half_plus" if overs >= cfg["test_bowling_split"] else "under_half"
    overs = sum(i["balls"] for i in bowl_innings) / 6
    return "half_plus" if overs >= cfg["bowling_quota"][fmt] / 2 else "under_half"


def exclusion_reason(info, innings, fmt, cfg):
    """Match-level exclusion rule (documented in the report). None = keep."""
    if info.get("balls_per_over", 6) != 6:
        return "non-6-ball overs (e.g. The Hundred)"
    outcome = info.get("outcome", {}) or {}
    if outcome.get("result") == "no result":
        return "no result"
    if "method" in outcome:
        return f"result by method ({outcome['method']})"
    std = cfg["standard_overs"].get(fmt)
    if std is not None:
        if info.get("overs") is not None and info["overs"] < std:
            return "reduced overs (info.overs below standard)"
        for inn in innings:
            if inn.get("super_over"):
                continue
            t = inn.get("target", {}) or {}
            if t.get("overs") is not None and t["overs"] < std:
                return "reduced overs (revised target)"
    if not [i for i in innings if not i.get("super_over") and i.get("overs")]:
        return "no ball-by-ball data"
    return None


def parse_match(match_id, d, cfg):
    """Returns (Match, None) or (None, exclusion reason)."""
    info = d["info"]
    fmt = cfg["match_type_map"].get(info.get("match_type"))
    if fmt is None:
        return None, f"unmapped match type {info.get('match_type')}"
    innings = [i for i in d.get("innings", []) if not i.get("super_over")]
    reason = exclusion_reason(info, d.get("innings", []), fmt, cfg)
    if reason:
        return None, reason

    registry = info.get("registry", {}).get("people", {})
    teams = info["teams"]
    team_of = {}
    for team, names in info.get("players", {}).items():
        for n in names:
            team_of[n] = team

    def blank():
        return {"bat": [], "bowl": [], "catches": 0, "stumpings": 0,
                "ro_direct": 0, "ro_indirect": 0, "in_xi": True}

    stats = {n: blank() for n in team_of}
    position = {}
    retired_hurt = set()

    for inn in innings:
        order = []
        bat = collections.defaultdict(lambda: {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False})
        bowl = collections.defaultdict(lambda: {"balls": 0, "runs": 0, "dots": 0, "maidens": 0,
                                                "wickets": 0, "lbw_bowled": 0})
        for ov in inn.get("overs", []):
            over_bowlers, over_legal, over_runs = set(), 0, 0
            for dl in ov["deliveries"]:
                for p in (dl["batter"], dl["non_striker"]):
                    if p not in order:
                        order.append(p)
                        bat[p]  # create an innings entry for anyone who came to the crease
                ex = dl.get("extras", {})
                r = dl["runs"]
                legal_for_batter = "wides" not in ex
                legal_for_bowler = "wides" not in ex and "noballs" not in ex
                b = bat[dl["batter"]]
                b["runs"] += r["batter"]
                if legal_for_batter:
                    b["balls"] += 1
                if not r.get("non_boundary"):
                    if r["batter"] == 4:
                        b["fours"] += 1
                    elif r["batter"] == 6:
                        b["sixes"] += 1
                bw = bowl[dl["bowler"]]
                conceded = r["batter"] + ex.get("wides", 0) + ex.get("noballs", 0)
                bw["runs"] += conceded
                if legal_for_bowler:
                    bw["balls"] += 1
                    over_legal += 1
                    if r["total"] == 0:
                        bw["dots"] += 1
                over_bowlers.add(dl["bowler"])
                over_runs += conceded
                for w in dl.get("wickets", []):
                    kind, out = w["kind"], w["player_out"]
                    if kind == "retired hurt":
                        retired_hurt.add(out)
                    if kind not in NOT_DISMISSED:
                        bat[out]["out"] = True
                    if kind in BOWLER_WICKETS:
                        bw["wickets"] += 1
                        if kind in ("bowled", "lbw"):
                            bw["lbw_bowled"] += 1
                    fielders = [f["name"] for f in w.get("fielders", [])
                                if not f.get("substitute") and f.get("name") in stats]
                    if kind == "caught":
                        for f in fielders[:1]:
                            stats[f]["catches"] += 1
                    elif kind == "caught and bowled" and dl["bowler"] in stats:
                        stats[dl["bowler"]]["catches"] += 1
                    elif kind == "stumped":
                        for f in fielders[:1]:
                            stats[f]["stumpings"] += 1
                    elif kind == "run out":
                        if len(fielders) == 1:
                            stats[fielders[0]]["ro_direct"] += 1
                        else:
                            for f in fielders:
                                stats[f]["ro_indirect"] += 1
            if len(over_bowlers) == 1 and over_legal == 6 and over_runs == 0:
                bowl[next(iter(over_bowlers))]["maidens"] += 1
        for i, p in enumerate(order, start=1):
            position.setdefault(p, i)   # first innings batted sets the position
        for p, s in bat.items():
            if p in stats:
                stats[p]["bat"].append(s)
        for p, s in bowl.items():
            if p in stats:
                stats[p]["bowl"].append(s)

    first = innings[0]
    m = Match(
        match_id=match_id, date=info["dates"][0], fmt=fmt, gender=info["gender"],
        match_type=info["match_type"], venue=normalise_venue(info["venue"]), teams=teams,
        batted_first=first["team"],
        first_innings_total=sum(dl["runs"]["total"] for ov in first.get("overs", []) for dl in ov["deliveries"]),
    )
    for name, team in team_of.items():
        pid = registry.get(name, name)
        pos = position.get(name)
        m.players[pid] = PlayerMatch(
            player_id=pid, name=name, team=team,
            opponent=next((t for t in teams if t != team), ""),
            bat_position=pos, bat_band=bat_band(pos),
            bowl_band=bowl_band(fmt, stats[name]["bowl"], cfg),
            retired_hurt=name in retired_hurt, stats=stats[name])
    return m, None


def load_matches(raw_dir, cfg, start_date, end_date):
    """All kept matches with start_date <= date <= end_date, plus counters for the report."""
    matches = []
    excluded = collections.Counter()
    type_counts = collections.Counter()
    files = sorted(glob.glob(os.path.join(str(raw_dir), "*.json")))
    for idx, path in enumerate(files):
        if idx % 5000 == 0:
            print(f"[parse] {idx}/{len(files)} files", flush=True)
        with open(path, encoding="utf8") as fh:
            d = json.load(fh)
        info = d["info"]
        date = info["dates"][0]
        if not (start_date <= date <= end_date):
            continue
        type_counts[(info.get("match_type"), info.get("gender"))] += 1
        m, reason = parse_match(os.path.splitext(os.path.basename(path))[0], d, cfg)
        if m is None:
            excluded[reason] += 1
        else:
            matches.append(m)
    matches.sort(key=lambda m: (m.date, m.match_id))
    return matches, excluded, type_counts
