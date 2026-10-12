"""Daily refresh (CLAUDE.md section 10 A, steps 1 and 4) and per-match squad loading for the app.
Uses the CricketData.org client with its cache, caps and modes; fields from tests/fixtures/cricketdata."""
import datetime as dt

from engine.cli import player_list
from engine.env import ROOT, env
from engine.fresh import base_team, gender_of, match_format
from engine.groups import spec_group
from engine.matching import CoverageMatcher, Register
from engine.settings import Settings
from engine.sources.cricketdata import CricketData, clean_image_url


def app_client(store):
    st = Settings(store)
    return CricketData(store, env("CRICKETDATA_API_KEY"), st.int("cricketdata_daily_limit"),
                       run_limit=st.int("cricketdata_max_calls_per_run"), dev=False, command="app")


def our_status(m):
    if m.get("matchEnded"):
        return "finished"
    return "live" if m.get("matchStarted") else "upcoming"


def start_gmt(m):
    """CricketData.org's dateTimeGMT can disagree with its own status text ("Match starts at Oct 13, 13:00 GMT");
    Dream11 confirmed the status text for the 3rd T20I PAK v SL (6:30 pm IST = 13:00 GMT), so it wins when present."""
    import re
    got = re.search(r"Match starts at (\w{3}) (\d{1,2}), (\d{2}:\d{2}) GMT", m.get("status") or "")
    if got and m.get("date"):
        t = dt.datetime.strptime(f"{m['date'][:4]} {got[1]} {got[2]} {got[3]}", "%Y %b %d %H:%M")
        return t.strftime("%Y-%m-%dT%H:%M:%S")
    return m["dateTimeGMT"]


def upsert_match(store, m):
    """Store one CricketData.org match (list or info shape). Returns our match id or None if format unsupported."""
    fmt = match_format(m.get("matchType"), m.get("name"))
    if fmt is None or not m.get("dateTimeGMT"):
        return None
    gender = gender_of(m.get("teams", []))
    for t in m.get("teamInfo") or []:
        store.ensure_team(base_team(t["name"]), gender, short_code=t.get("shortname"))
    mid = store.ensure_cricketdata_match({**m, "dateTimeGMT": start_gmt(m) + "+00:00"}, fmt, gender,
                                         spec_group(fmt, gender), base_team=base_team)
    store.q("UPDATE matches SET status = %s, start_time = %s, updated_at = now() WHERE id = %s RETURNING id",
            (our_status(m), start_gmt(m) + "+00:00", mid))
    return mid


def refresh_fixtures(store, client, days=7):
    now = dt.datetime.now(dt.timezone.utc)
    end = now + dt.timedelta(days=days)
    seen, saved = set(), []
    for m in client.current_matches() + client.matches(0):
        if m["id"] in seen or not m.get("dateTimeGMT"):
            continue
        seen.add(m["id"])
        t = dt.datetime.fromisoformat(m["dateTimeGMT"]).replace(tzinfo=dt.timezone.utc)
        known = store.one("SELECT 1 FROM matches WHERE cricketdata_id = %s", (m["id"],))
        if (now - dt.timedelta(days=2) <= t <= end) or known:
            mid = upsert_match(store, m)
            if mid:
                saved.append(mid)
    return saved


def load_squad(store, client, mid):
    """Squad (or previous-match players) for the match into match_xi + players, matched to our player ids.
    Returns (matched [(pid, name, team)], unmatched names, source)."""
    cd = store.one("SELECT cricketdata_id FROM matches WHERE id = %s", (mid,))
    info = client.match_info(cd) if cd else None
    if not info:
        return [], [], "none"
    gender = gender_of(info.get("teams", []))
    plist, source = player_list(store, client, info, gender, "pre_toss")
    matcher = CoverageMatcher(store, Register.from_dir(ROOT / "data" / "register"))
    since = (dt.date.fromisoformat(info["date"]) - dt.timedelta(days=365)).isoformat()
    hints, items = {}, []
    for i, (team, name, cd_id, img) in enumerate(plist):
        t = base_team(team)
        if t not in hints:
            hints[t] = (store.team_players(t, gender), store.team_players(t, gender, since=since))
        items.append((i, name, hints[t][0], hints[t][1]))
    resolved = matcher.resolve_all("cricketdata", items)
    matched, unmatched = [], []
    for i, (team, name, cd_id, img) in enumerate(plist):
        pid = resolved.get(i)
        if pid:
            store.set_xi(mid, base_team(team), gender, pid, "squad" if source == "squad" else "previous_match")
            if cd_id:
                store.set_cricketdata_id(pid, cd_id, clean_image_url(img))
            matched.append((pid, name, base_team(team)))
        else:
            unmatched.append(name)
    return matched, unmatched, source
