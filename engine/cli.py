"""Command-line runner (spec 9.8).

    python -m engine.cli upcoming
    python -m engine.cli score --match <cricketdata match id> --run-type pre_toss|post_toss
    python -m engine.cli refresh-cricsheet [--full]
    python -m engine.cli budget
    python -m engine.cli seed-cache      # load the saved real responses (tests/fixtures) into api_cache
"""
import argparse
import datetime as dt
import json
import sys

from engine.cricsheet_refresh import refresh
from engine.db import PgStore
from engine.env import ROOT, env
from engine.factors import FACTORS
from engine.fresh import base_team, gender_of, match_format
from engine.groups import spec_group
from engine.matching import Matcher
from engine.points import load_points_config
from engine.score import ScoringFailed, score_match
from engine.settings import Settings
from engine.sources.cricketdata import SOURCE, TTL, CricketData

FIX = ROOT / "tests" / "fixtures" / "cricketdata"
# Saved real responses and the request that produced each (from tools/discover_cricketdata.py).
SEED = {"match_scorecard.json": ("match_scorecard", {"id": "0cb2b44c-69b3-4c50-b1a5-9af598ffecaf"}),
        "match_info.json": ("match_info", {"id": "0cb2b44c-69b3-4c50-b1a5-9af598ffecaf"}),
        "series_info.json": ("series_info", {"id": "a67cb0af-300c-4449-8e80-e006301e5706"}),
        "players_info.json": ("players_info", {"id": "52a6be27-1c5d-4c2b-86ab-98710ec7e0ef"}),
        "currentMatches.json": ("currentMatches", {"offset": 0}),
        "matches.json": ("matches", {"offset": 0})}


def client_for(store):
    return CricketData(store, env("CRICKETDATA_API_KEY"), Settings(store).int("cricketdata_daily_limit"))


def cmd_seed(store):
    hits = 0
    for f, (endpoint, params) in SEED.items():
        p = FIX / f
        resp = json.loads(p.read_text(encoding="utf8"))
        resp.pop("apikey", None)
        fetched = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc)
        store.cache_put(SOURCE, CricketData.request_key(endpoint, params), resp, fetched, fetched + TTL[endpoint])
        hits = max(hits, (resp.get("info") or {}).get("hitsToday", 0))
        print(f"cached {endpoint} {params}")
    store.usage_set_at_least(SOURCE, dt.datetime.now(dt.timezone.utc).date(), hits)
    print(f"api_usage today set to at least {hits} (from the saved responses)")


def cmd_budget(store):
    c = client_for(store)
    print(f"CricketData.org calls today: {c.calls_today()} / {c.daily_limit} (stop limit)")


def cmd_upcoming(store):
    c = client_for(store)
    now = dt.datetime.now(dt.timezone.utc)
    end = now + dt.timedelta(days=7)
    seen = set()
    for m in c.current_matches() + c.matches(0):
        if m["id"] in seen or m.get("matchStarted"):
            continue
        seen.add(m["id"])
        t = dt.datetime.fromisoformat(m["dateTimeGMT"]).replace(tzinfo=dt.timezone.utc)
        if now <= t <= end:
            print(f"{m['dateTimeGMT']}  {m['id']}  {m.get('matchType')}  {m['name']}")
    for w in c.warnings:
        print("warning:", w)


def player_list(store, c, info, gender, run_type):
    """Squad if CricketData.org has one; else (rule approved for this phase) both teams' players from the
    previous finished match of the same series. TODO-CONFIRM: no confirmed-XI endpoint has been verified,
    so post-toss also uses this list."""
    if info.get("hasSquad"):
        squad = c.match_squad(info["id"])
        if squad:
            return [(t["teamName"], p["name"], p["id"]) for t in squad for p in t["players"]], "squad"
    prev = [m for m in c.series_info(info["series_id"]).get("matchList", [])
            if m.get("matchEnded") and m.get("date", "") < info["date"] and set(m.get("teams", [])) == set(info["teams"])]
    if not prev:
        return [], "none"
    last = max(prev, key=lambda m: m["dateTimeGMT"])
    sc = c.match_scorecard(last["id"])
    from engine.fresh import scorecard_rows
    return [(t, n, cid) for (t, n, cid) in scorecard_rows(sc)], f"players from previous match ({last['name']})"


def cmd_score(store, match, run_type):
    points = load_points_config(ROOT / "config" / "dream11_points.yaml")
    c = client_for(store)
    info = c.match_info(match)
    if not info:
        sys.exit(f"Match {match} not found on CricketData.org")
    fmt = match_format(info.get("matchType"), info.get("name"))
    if fmt is None:
        sys.exit("Format not supported")
    gender = gender_of(info.get("teams", []))
    group = spec_group(fmt, gender)
    mid = store.ensure_cricketdata_match(info, fmt, gender, group, base_team=base_team)
    plist, source = player_list(store, c, info, gender, run_type)
    matcher = Matcher(store)
    pids = []
    for team, name, cd_id in plist:
        pid = matcher.resolve("cricketdata", name, store.team_players(base_team(team), gender))
        if pid:
            store.set_xi(mid, base_team(team), gender, pid, "squad" if source == "squad" else "previous_match")
            if cd_id:
                store.set_cricketdata_id(pid, cd_id)
            pids.append(pid)
    try:
        r = score_match(store, c, points, mid, sorted(set(pids)), run_type, unmatched_names=matcher.unmatched)
    except ScoringFailed as e:
        sys.exit(f"Scoring failed at step '{e.step}': {e} (run {e.run_id})")
    print(f"{info['name']}  [{group}, {run_type}]  player list: {source}")
    print(f"run {r.run_id}  rubric version {r.rubric_version_id}  provisional weights: {r.provisional_weights}"
          f"  borrowed from: {r.borrowed_from_group}  data stale: {r.data_stale}")
    hdr = f"{'player':24} {'team':12} {'base':>6} " + " ".join(f"{k[:7]:>7}" for k in FACTORS) + "  fb thin"
    print(hdr)
    print("-" * len(hdr))
    for p in r.players:
        name = store.full_name(p.player_id)
        team = store.player_team(mid, p.player_id) or ""
        base = "  null" if p.base_score is None else f"{p.base_score:6.1f}"
        fac = " ".join(f"{p.factors[k]:7.1f}" if p.factors else f"{'-':>7}" for k in FACTORS)
        print(f"{name[:24]:24} {team[:12]:12} {base} {fac}  {p.fallback_step:>2} {'yes' if p.thin_data else 'no'}")
    if r.unmatched_names:
        print(f"unmatched names (not scored): {', '.join(r.unmatched_names)}")
    for w in r.warnings:
        print("warning:", w)
    print(f"CricketData.org calls today: {c.calls_today()}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("upcoming")
    s = sub.add_parser("score")
    s.add_argument("--match", required=True)
    s.add_argument("--run-type", required=True, choices=["pre_toss", "post_toss"])
    r = sub.add_parser("refresh-cricsheet")
    r.add_argument("--full", action="store_true")
    sub.add_parser("budget")
    sub.add_parser("seed-cache")
    a = ap.parse_args(argv)
    store = PgStore()
    if a.cmd == "upcoming":
        cmd_upcoming(store)
    elif a.cmd == "score":
        cmd_score(store, a.match, a.run_type)
    elif a.cmd == "refresh-cricsheet":
        print(refresh(store, load_points_config(ROOT / "config" / "dream11_points.yaml"), full=a.full))
    elif a.cmd == "budget":
        cmd_budget(store)
    elif a.cmd == "seed-cache":
        cmd_seed(store)


if __name__ == "__main__":
    main()
