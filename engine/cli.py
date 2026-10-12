"""Command-line runner (spec 9.8).

    python -m engine.cli upcoming
    python -m engine.cli score --match <cricketdata match id> --run-type pre_toss|post_toss
    python -m engine.cli refresh-cricsheet [--full]
    python -m engine.cli budget
    python -m engine.cli seed-cache      # load the saved real responses (tests/fixtures) into api_cache
"""
import argparse
import urllib.request
import datetime as dt
import json
import sys

from engine.cricsheet_refresh import refresh
from engine.db import PgStore
from engine.env import ROOT, env
from engine.factors import FACTORS
from engine.fresh import base_team, gender_of, match_format
from engine.groups import spec_group
from engine.matching import CoverageMatcher, Register
from engine.points import load_points_config
from engine.score import ScoringFailed, score_match
from engine.settings import Settings
from engine.sources.cricketdata import (CMD_PREFIX, FIXTURE_INDEX, FIXTURES, FOREVER, SOURCE, TTL,
                                       CricketData, clean_image_url)

def client_for(store, command=None, dry_run=False):
    st = Settings(store)
    return CricketData(store, env("CRICKETDATA_API_KEY"), st.int("cricketdata_daily_limit"),
                       dev_limit=st.int("cricketdata_dev_daily_limit"),
                       run_limit=st.int("cricketdata_max_calls_per_run"),
                       dev=True, command=command, dry_run=dry_run)


def cmd_seed(store):
    """Load the saved real responses into api_cache so they are never fetched again."""
    hits = 0
    for (endpoint, items), f in FIXTURE_INDEX.items():
        params = dict(items)
        p = FIXTURES / f
        resp = json.loads(p.read_text(encoding="utf8"))
        resp.pop("apikey", None)
        fetched = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc)
        finished = isinstance(resp.get("data"), dict) and resp["data"].get("matchEnded")
        expires = FOREVER if endpoint == "match_scorecard" and finished else fetched + TTL[endpoint]
        if not store.cache_get(SOURCE, CricketData.request_key(endpoint, params)):
            store.cache_put(SOURCE, CricketData.request_key(endpoint, params), resp, fetched, expires)
        hits = max(hits, (resp.get("info") or {}).get("hitsToday", 0))
        print(f"cached {endpoint} {params}")
    store.usage_set_at_least(SOURCE, dt.datetime.now(dt.timezone.utc).date(), hits)
    print(f"api_usage today set to at least {hits} (from the saved responses)")


def cmd_budget(store, c):
    print(f"CricketData.org calls today: {c.calls_today()} of {c.daily_limit} "
          f"(development {c.dev_calls_today()} of {c.dev_limit}; per run max {c.run_limit}; mode {c.mode})")
    for source, calls in store.usage_by_prefix(CMD_PREFIX, c.now().date()):
        print(f"  {source[len(CMD_PREFIX):]:20} {calls}")


def cmd_upcoming(store, c):
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


def player_list(store, c, info, gender, run_type):
    """Squad if CricketData.org has one; else (rule approved for this phase) both teams' players from the
    previous finished match of the same series. TODO-CONFIRM: no confirmed-XI endpoint has been verified,
    so post-toss also uses this list."""
    if info.get("hasSquad"):
        squad = c.match_squad(info["id"], match_finished=bool(info.get("matchEnded")))
        if squad:
            return [(t["teamName"], p["name"], p["id"], p.get("playerImg")) for t in squad for p in t["players"]], "squad"
    if not info.get("series_id"):
        return [], "none"
    prev = [m for m in c.series_info(info["series_id"]).get("matchList", [])
            if m.get("matchEnded") and m.get("date", "") < info["date"] and set(m.get("teams", [])) == set(info["teams"])]
    if not prev:
        return [], "none"
    last = max(prev, key=lambda m: m["dateTimeGMT"])
    sc = c.match_scorecard(last["id"])
    from engine.fresh import scorecard_rows
    return [(t, n, cid, None) for (t, n, cid) in scorecard_rows(sc)], f"players from previous match ({last['name']})"


def cmd_score(store, c, match, run_type):
    points = load_points_config(ROOT / "config" / "dream11_points.yaml")
    info = c.match_info(match)
    if not info:
        if c.dry_run:
            print("Dry run: match info not cached; a live run would fetch it first.")
            return
        sys.exit(f"Match {match} not found (mode {c.mode}): {'; '.join(c.warnings)}")
    fmt = match_format(info.get("matchType"), info.get("name"))
    if fmt is None:
        sys.exit("Format not supported")
    gender = gender_of(info.get("teams", []))
    group = spec_group(fmt, gender)
    plist, source = player_list(store, c, info, gender, run_type)
    if c.dry_run:
        print(f"Dry run: player list from {source} ({len(plist)} players); scoring skipped. "
              "Recent scorecards fetched during scoring are not counted here.")
        return
    mid = store.ensure_cricketdata_match(info, fmt, gender, group, base_team=base_team)
    register = Register.from_dir(ROOT / "data" / "register")
    if register is None:
        print("note: Cricsheet register not downloaded (python -m engine.cli refresh-register); register step skipped")
    matcher = CoverageMatcher(store, register)
    since = (dt.date.fromisoformat(info["date"]) - dt.timedelta(days=365)).isoformat()
    hints = {}
    items = []
    for i, (team, name, cd_id, img) in enumerate(plist):
        t = base_team(team)
        if t not in hints:
            hints[t] = (store.team_players(t, gender), store.team_players(t, gender, since=since))
        items.append((i, name, hints[t][0], hints[t][1]))
    resolved = matcher.resolve_all("cricketdata", items)
    pids = []
    for i, (team, name, cd_id, img) in enumerate(plist):
        pid = resolved.get(i)
        if pid:
            store.set_xi(mid, base_team(team), gender, pid, "squad" if source == "squad" else "previous_match")
            if cd_id:
                store.set_cricketdata_id(pid, cd_id, clean_image_url(img))
            pids.append(pid)
    try:
        r = score_match(store, c, points, mid, sorted(set(pids)), run_type, unmatched_names=matcher.unmatched,
                        coverage=(len(pids), len(plist)))
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


def cmd_photos(store, a, dry):
    """Makes no CricketData.org calls; Wikimedia only."""
    from engine.photos import refresh_player, squad_players
    rows = squad_players(store) if a.squads else [(a.player, store.full_name(a.player), store.player_team_any(a.player))]
    if dry:
        print(f"Dry run: would check {len(rows)} players on Wikidata/Commons (no CricketData.org calls).")
        return
    tally = {}
    for pid, name, team in rows:
        src, why = refresh_player(store, pid, team, force=a.force)
        tally[src] = tally.get(src, 0) + 1
        print(f"{name:28} {team:12} {src:12} {why or ''}")
    real = tally.get("wikimedia", 0) + tally.get("cricketdata", 0)
    print(f"{real} of {len(rows)} players have a real photo ({tally.get('wikimedia', 0)} from Wikimedia, "
          f"{tally.get('cricketdata', 0)} from CricketData.org)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine.cli")
    ap.add_argument("--dry-run", action="store_true", help="print how many live calls would be made; make none")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("upcoming")
    s = sub.add_parser("score")
    s.add_argument("--match", required=True)
    s.add_argument("--run-type", required=True, choices=["pre_toss", "post_toss"])
    r = sub.add_parser("refresh-cricsheet")
    r.add_argument("--full", action="store_true")
    sub.add_parser("budget")
    lk = sub.add_parser("link", help="confirm a player name match once")
    lk.add_argument("--source", required=True, choices=["dream11", "cricketdata", "cricsheet"])
    lk.add_argument("--name", required=True)
    lk.add_argument("--player", required=True, help="players.id (Cricsheet register identifier)")
    sub.add_parser("refresh-register", help="download the Cricsheet people register (names.csv, people.csv)")
    sub.add_parser("seed-cache")
    ph = sub.add_parser("photos", help="player photos: CricketData.org, else Wikimedia Commons via Wikidata")
    ph.add_argument("--squads", action="store_true", help="every player in the next 7 days' squads")
    ph.add_argument("--player", help="one players.id")
    ph.add_argument("--force", action="store_true", help="re-check players checked in the last 30 days")
    for p in sub.choices.values():   # accept --dry-run after the command name too
        p.add_argument("--dry-run", action="store_true", dest="dry_run_cmd", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    dry = a.dry_run or getattr(a, "dry_run_cmd", False)
    store = PgStore()
    c = client_for(store, command=a.cmd, dry_run=dry)
    if a.cmd == "upcoming":
        cmd_upcoming(store, c)
    elif a.cmd == "score":
        cmd_score(store, c, a.match, a.run_type)
    elif a.cmd == "refresh-cricsheet":
        if dry:
            print("Dry run: refresh-cricsheet makes no CricketData.org calls (Cricsheet downloads only).")
        else:
            print(refresh(store, load_points_config(ROOT / "config" / "dream11_points.yaml"), full=a.full))
    elif a.cmd == "budget":
        cmd_budget(store, c)
    elif a.cmd == "link":
        if not store.player_exists(a.player):
            sys.exit(f"No player with id {a.player}")
        if not dry:
            store.add_link(a.player, a.source, a.name, confirmed=True)
            print(f"Linked {a.source} name '{a.name}' to {store.full_name(a.player)} ({a.player})")
    elif a.cmd == "refresh-register":
        if dry:
            print("Dry run: refresh-register downloads 2 files from cricsheet.org (no CricketData.org calls).")
        else:
            folder = ROOT / "data" / "register"
            folder.mkdir(parents=True, exist_ok=True)
            for f in ("people.csv", "names.csv"):
                urllib.request.urlretrieve(f"https://cricsheet.org/register/{f}", folder / f)
                print(f"downloaded {f}")
    elif a.cmd == "seed-cache":
        if not dry:
            cmd_seed(store)
    elif a.cmd == "photos":
        cmd_photos(store, a, dry)
    if a.cmd != "score":
        for w in c.warnings:
            print("warning:", w)
    if dry:
        print(f"Dry run: would make {c.would_call} live CricketData.org calls (cache misses, mode {c.mode}).")
    print(c.summary())


if __name__ == "__main__":
    main()
