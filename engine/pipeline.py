"""Run pipeline (CLAUDE.md section 10 C): checking -> scoring -> moderating -> optimizing -> explaining -> done.

Each step reads the previous step's saved output from Neon and writes its own, then moves runs.status on.
resume(run_id) restarts from the step in runs.status, so a timeout mid-run loses at most one step.
"""
import datetime as dt
import json
from pathlib import Path

from psycopg.types.json import Jsonb

from engine.gate import load_rules, validate
from engine.gemini import Gemini, GeminiFailed, fallback_lines
from engine.optimizer import NoValidTeam, best_team, bench as bench_of
from engine.points import load_points_config
from engine.score import ScoringFailed, score_match
from engine.settings import Settings
from engine.sources.news_rss import news_for_match
from engine.sources.openmeteo import forecast_at

ROOT = Path(__file__).resolve().parents[1]
STEPS = ("checking", "scoring", "moderating", "optimizing", "explaining", "done")
RAIN_WARN_PCT = 40   # TODO-CONFIRM: rain threshold for the "rain forecast" warning is not in RUBRIC.md section 10


class StepFailed(Exception):
    pass


def start(store, match_id, run_type):
    if run_type not in ("pre_toss", "post_toss"):
        raise ValueError("run_type must be pre_toss or post_toss")
    rid = store.one("""INSERT INTO runs (match_id, run_type, status, started_at, warnings)
                       VALUES (%s, %s, 'checking', now(), '[]') RETURNING id""", (match_id, run_type))
    log(store, "system", "run_started", match_id, {"run_id": str(rid), "run_type": run_type})
    return str(rid)


def log(store, actor, action, match_id, details):
    store.q("INSERT INTO activity_log (actor, action, match_id, details) VALUES (%s, %s, %s, %s) RETURNING id",
            (actor, action, match_id, Jsonb(details)))


def _run(store, rid):
    r = store.q("""SELECT r.match_id, r.run_type, r.status, r.pool_type, coalesce(r.warnings, '[]'), m.format_group,
                          m.start_time, m.venue_id, v.name, v.city, m.xi_announced
                     FROM runs r JOIN matches m ON m.id = r.match_id LEFT JOIN venues v ON v.id = m.venue_id
                    WHERE r.id = %s""", (rid,))
    if not r:
        raise ValueError(f"Run {rid} not found")
    k = ("match_id", "run_type", "status", "pool", "warnings", "group", "start_time", "venue_id", "venue", "city", "xi")
    return dict(zip(k, r[0]))


def _set(store, rid, status, **cols):
    sets = ", ".join(["status = %s"] + [f"{c} = %s" for c in cols])
    vals = [status] + [Jsonb(v) if isinstance(v, (dict, list)) else v for v in cols.values()]
    store.q(f"UPDATE runs SET {sets} WHERE id = %s RETURNING id", (*vals, rid))


def _warn(store, rid, text):
    store.q("""UPDATE runs SET warnings = coalesce(warnings, '[]'::jsonb) || %s WHERE id = %s
               AND NOT coalesce(warnings, '[]'::jsonb) @> %s RETURNING id""", (Jsonb([text]), rid, Jsonb([text])))


def aryan_list(store, mid):
    """Aryan's Dream11 list for the match: {pid: {name, side, role, credits}} (from the credits table).
    Side: the player's team in this match's squad/XI, else his most recent team."""
    rows = store.q("""SELECT c.player_id, p.full_name, c.dream11_role, c.credits, coalesce(
                        (SELECT t.name FROM match_xi x JOIN teams t ON t.id = x.team_id
                          WHERE x.match_id = c.match_id AND x.player_id = c.player_id LIMIT 1),
                        (SELECT t.name FROM match_xi x JOIN teams t ON t.id = x.team_id JOIN matches m ON m.id = x.match_id
                          WHERE x.player_id = c.player_id ORDER BY m.start_time DESC LIMIT 1))
                      FROM credits c JOIN players p ON p.id = c.player_id WHERE c.match_id = %s""", (mid,))
    return {pid: {"name": n, "side": side, "role": role, "credits": float(cr)} for pid, n, role, cr, side in rows}


def _many(store, sql, rows):
    with store.conn.cursor() as cur:
        cur.executemany(sql, rows)


# step 1
def step_checking(store, rid, run):
    mid, lst = run["match_id"], aryan_list(store, run["match_id"])
    if len(lst) < 11:
        raise StepFailed("Your Dream11 player list has fewer than 11 players: upload the player-list screenshot "
                         "and tap Looks right first.")
    days = Settings(store).int("probable_xi_days")
    pool, types = [], {}
    for side in sorted({p["side"] for p in lst.values() if p["side"]}):
        mine = {pid for pid, p in lst.items() if p["side"] == side}
        confirmed = {r[0] for r in store.q("""SELECT x.player_id FROM match_xi x JOIN teams t ON t.id = x.team_id
                     WHERE x.match_id = %s AND t.name = %s AND x.source = 'cricketdata'""", (mid, side))}
        if run["run_type"] == "post_toss" and run["xi"] and confirmed:
            types[side], ids = "confirmed", mine & confirmed
        else:
            last = store.one("""SELECT m.id FROM matches m JOIN match_xi x ON x.match_id = m.id
                                JOIN teams t ON t.id = x.team_id
                                WHERE t.name = %s AND m.format_group = %s AND m.id <> %s
                                  AND m.start_time < %s AND m.start_time >= %s
                                ORDER BY m.start_time DESC LIMIT 1""",
                             (side, run["group"], mid, run["start_time"], run["start_time"] - dt.timedelta(days=days)))
            xi = {r[0] for r in store.q("""SELECT x.player_id FROM match_xi x JOIN teams t ON t.id = x.team_id
                                          WHERE x.match_id = %s AND t.name = %s""", (last, side))} if last else set()
            if xi and len(mine & xi) >= 8:   # fewer means the list and the old XI barely overlap: use the full list
                types[side], ids = "probable", mine & xi
            else:
                types[side], ids = "full", mine
        pool += sorted(ids)
    if any(t != "confirmed" for t in types.values()):
        _warn(store, rid, "XI not confirmed: rebuild after the toss")
    unknown = [lst[p]["name"] for p in lst if not lst[p]["side"]]
    if unknown:
        _warn(store, rid, f"No team found for {', '.join(unknown)}: left out")
    _set(store, rid, "scoring", pool_type={"teams": types, "player_ids": pool})


# step 2
def step_scoring(store, rid, run, client):
    store.q("DELETE FROM predictions WHERE run_id = %s RETURNING id", (rid,))
    points = load_points_config(ROOT / "config" / "dream11_points.yaml")
    try:
        res = score_match(store, client, points, run["match_id"], run["pool"]["player_ids"], run["run_type"], run_id=rid)
    except ScoringFailed as e:
        raise StepFailed(f"Scoring failed at '{e.step}': {e}") from None
    for w in res.warnings:
        _warn(store, rid, w)
    store.q("UPDATE predictions SET adjusted_score = base_score, gemini_change_pct = 0 WHERE run_id = %s RETURNING id",
            (rid,))
    _set(store, rid, "moderating", finished_at=None, data_stale=res.data_stale)


def predictions(store, rid):
    cols = ("player_id", "factors", "trust", "thin_data", "base_score", "adjusted_score", "fallback_step")
    return {r[0]: dict(zip(cols, r)) for r in store.q(f"SELECT {', '.join(cols)} FROM predictions WHERE run_id = %s",
                                                       (rid,))}


# step 3
def step_moderating(store, rid, run, gemini, forecast_fn, news_fn=news_for_match):
    store.q("DELETE FROM gemini_adjustments WHERE run_id = %s RETURNING id", (rid,))
    store.q("DELETE FROM news_items WHERE run_id = %s RETURNING id", (rid,))
    store.q("DELETE FROM search_sources WHERE run_id = %s RETURNING id", (rid,))
    preds, lst = predictions(store, rid), aryan_list(store, run["match_id"])
    fc = forecast_fn(store, run["venue_id"], run["venue"], run["start_time"], run["city"])
    if fc and fc["rain_chance_pct"] is not None and fc["rain_chance_pct"] >= RAIN_WARN_PCT:
        _warn(store, rid, f"Rain forecast: {fc['rain_chance_pct']}% chance at the venue at the start")
    pitch = store.one("""SELECT pitch_type FROM venue_pitch_types vp JOIN matches m ON m.venue_id = vp.venue_id
                         WHERE m.id = %s AND vp.format_group = %s""", (run["match_id"], run["group"])) \
        if store.one("SELECT to_regclass('venue_pitch_types')") else None
    players = [{"player_id": pid, "name": lst[pid]["name"], "team": lst[pid]["side"], "dream11_role": lst[pid]["role"],
                "base_score": round(p["base_score"], 1),
                "factors": {k: round(v, 1) for k, v in (p["factors"] or {}).items()},
                "trust": {k: round(v, 2) for k, v in (p["trust"] or {}).items()}, "thin_data": p["thin_data"]}
               for pid, p in preds.items() if p["base_score"] is not None and pid in lst]
    teams = sorted({p["team"] for p in players})
    match = {"id": run["match_id"], "format_group": run["group"], "venue": run["venue"], "teams": teams,
             "start_time_utc": str(run["start_time"]), "venue_pitch_type_counted_by_rubric": pitch or "unknown",
             "run_type": run["run_type"]}
    cap = Settings(store).float("gemini_cap_percent")
    news = []
    if len(teams) == 2:
        try:
            news = news_fn(store, run["match_id"], rid, teams[0], teams[1], [p["name"] for p in players], run["venue"])
        except Exception:   # feed unavailable: Gemini's Google Search grounding is the backup
            news = []
    try:
        out, errors = gemini.moderate(players, match, fc, cap=cap, run_id=rid, news=news)
        if not out["news_checked"] and not out["adjustments"] and not news:
            _warn(store, rid, "News not checked: no team news was found or read")
    except GeminiFailed:
        _warn(store, rid, "News not checked: Gemini did not answer, scores are unadjusted")
        _set(store, rid, "optimizing")
        return
    names = {p["player_id"]: p["name"] for p in players}
    for pid in out.get("conflicts", []):
        _warn(store, rid, f"Check this yourself: news about {names.get(pid, pid)} conflicts (fit vs not fit)")
    if any(a["clipped"] for a in out["adjustments"]):
        _warn(store, rid, "Gemini wanted to go beyond ±20%")
    for a in out["adjustments"]:
        sid = store.one("""INSERT INTO search_sources (run_id, title, link, source_name) VALUES (%s, %s, %s, %s)
                           RETURNING id""", (rid, a["search_title"], a["source_url"], None)) if a["source_type"] == "search" else None
        store.q("""INSERT INTO gemini_adjustments (run_id, player_id, requested_pct, applied_pct, clipped, reason,
                   reason_type, source_url, news_item_id, source_type, search_source_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (rid, a["player_id"], a["requested_pct"], a["applied_pct"], a["clipped"], a["reason"], a["reason_type"],
                 a["source_url"], a.get("news_item_id"), a["source_type"], sid))
        store.q("""UPDATE predictions SET gemini_change_pct = %s, adjusted_score = base_score * (1 + %s / 100.0)
                   WHERE run_id = %s AND player_id = %s RETURNING id""", (a["applied_pct"], a["applied_pct"], rid,
                                                                         a["player_id"]))
    log(store, "gemini", "moderated", run["match_id"],
        {"run_id": rid, "adjustments": len(out["adjustments"]), "pitch_note": out["pitch_note"],
         "news_checked": out["news_checked"], "rejected": errors, "search_sources": len(out.get("sources", [])), "conflicts": out.get("conflicts", []),
         "news_items": len(news)})
    _set(store, rid, "optimizing")


def optimizer_players(store, rid, run, score_key="adjusted_score"):
    preds, lst = predictions(store, rid), aryan_list(store, run["match_id"])
    return {pid: {**lst[pid], "score": float(p[score_key]), "thin": bool(p["thin_data"]), "factors": p["factors"]}
            for pid, p in preds.items() if pid in lst and p[score_key] is not None}


def recent_average(store, pid, before, group, n=10):
    rows = store.q("""SELECT p.total_points FROM player_match_points p JOIN matches m ON m.id = p.match_id
                      WHERE p.player_id = %s AND m.format_group = %s AND m.start_time < %s
                      ORDER BY m.start_time DESC LIMIT %s""", (pid, group, before, n))
    return sum(float(r[0]) for r in rows) / len(rows) if rows else 0.0


def save_team(store, rid, kind, team, players, rules):
    g = validate(team.player_ids, team.captain_id, team.vc_id, players, rules)
    store.q("""INSERT INTO teams_picked (run_id, kind, player_ids, captain_id, vc_id, total_expected, credits_used,
               gate_passed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (rid, kind, Jsonb(team.player_ids), team.captain_id, team.vc_id, team.total_expected, team.credits_used,
             g.passed))
    return g.passed


# step 4
def step_optimizing(store, rid, run, rules):
    store.q("DELETE FROM teams_picked WHERE run_id = %s AND kind IN ('system', 'simple') RETURNING id", (rid,))
    store.q("DELETE FROM bench WHERE run_id = %s RETURNING id", (rid,))
    players = optimizer_players(store, rid, run)
    try:
        team = best_team(players, rules)
    except NoValidTeam as e:
        raise StepFailed(str(e)) from None
    save_team(store, rid, "system", team, players, rules)
    size = Settings(store).int("bench_size")
    for b in bench_of(players, rules, team, size=size):
        store.q("""INSERT INTO bench (run_id, player_id, rank, reason_code, reason_detail, points_cost)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (rid, b["player_id"], b["rank"], b["reason_code"], b["reason_detail"], b["points_cost"]))
    simple = {pid: {**p, "score": recent_average(store, pid, run["start_time"], run["group"]), "thin": False}
              for pid, p in players.items()}
    try:
        save_team(store, rid, "simple", best_team(simple, rules), simple, rules)
    except NoValidTeam:
        pass
    thin = sum(1 for pid in team.player_ids if players[pid]["thin"])
    if thin >= 3:
        _warn(store, rid, f"{thin} picked players rest on thin data")
    _set(store, rid, "explaining")


# step 5
def step_explaining(store, rid, run, gemini):
    store.q("DELETE FROM explanations WHERE run_id = %s RETURNING id", (rid,))
    players = optimizer_players(store, rid, run)
    base = optimizer_players(store, rid, run, "base_score")
    t = store.q("SELECT player_ids, captain_id, vc_id FROM teams_picked WHERE run_id = %s AND kind = 'system' "
                "ORDER BY id DESC LIMIT 1", (rid,))[0]
    team, cap, vc = t
    bench = [dict(zip(("player_id", "rank", "reason_code", "reason_detail"), r)) for r in
             store.q("SELECT player_id, rank, reason_code, reason_detail FROM bench WHERE run_id = %s ORDER BY rank",
                     (rid,))]
    adj = [dict(zip(("player_id", "applied_pct", "reason", "source_url"), r)) for r in
           store.q("SELECT player_id, applied_pct, reason, source_url FROM gemini_adjustments WHERE run_id = %s", (rid,))]

    def info(pid):
        p = players[pid]
        return {"player_id": pid, "name": p["name"], "team": p["side"], "dream11_role": p["role"],
                "credits": p["credits"], "base_score": round(base[pid]["score"], 1),
                "adjusted_score": round(p["score"], 1),
                "factors": {k: round(v, 1) for k, v in (p["factors"] or {}).items()}, "thin_data": p["thin"]}
    payload = {"venue": run["venue"], "format_group": run["group"], "team": [info(p) for p in team],
               "captain_id": cap, "vc_id": vc,
               "bench": [{**info(b["player_id"]), "left_out_because": b["reason_code"], "detail": b["reason_detail"]}
                         for b in bench], "adjustments": adj}
    try:
        rows, _ = gemini.explain(payload, run_id=rid)
    except GeminiFailed:
        rows = fallback_lines(team, bench, players, cap, vc)
        _warn(store, rid, "Reasons written automatically from the numbers (Gemini did not answer)")
    _many(store, "INSERT INTO explanations (run_id, player_id, kind, text, generic_flag) VALUES (%s, %s, %s, %s, %s)",
          [(rid, r["player_id"], r["kind"], r["text"], r["generic_flag"]) for r in rows])
    _set(store, rid, "done", finished_at=dt.datetime.now(dt.timezone.utc))
    log(store, "system", "run_done", run["match_id"], {"run_id": rid})


def resume(store, rid, client=None, gemini=None, forecast_fn=forecast_at, rules=None, max_steps=None):
    """Run from the step in runs.status to done (or max_steps steps). On failure: status failed + failed_step +
    plain-English message."""
    gemini = gemini or Gemini(store)
    done_steps = 0
    while True:
        run = _run(store, rid)
        step = run["status"]
        if step in ("done", "failed") or (max_steps is not None and done_steps >= max_steps):
            return step
        done_steps += 1
        try:
            if step == "checking":
                step_checking(store, rid, run)
            elif step == "scoring":
                step_scoring(store, rid, run, client)
            elif step == "moderating":
                step_moderating(store, rid, run, gemini, forecast_fn)
            elif step == "optimizing":
                step_optimizing(store, rid, run, rules or load_rules(ROOT / "config" / "dream11_rules.yaml",
                                                                      run["group"].split("_")[0]))
            elif step == "explaining":
                step_explaining(store, rid, run, gemini)
            else:
                raise StepFailed(f"Unknown step {step}")
        except Exception as e:   # every failure lands in runs with a readable message
            msg = str(e) if isinstance(e, StepFailed) else f"{type(e).__name__}: {e}"
            store.q("""UPDATE runs SET status = 'failed', failed_step = %s, error_message = %s, finished_at = now()
                       WHERE id = %s RETURNING id""", (step, msg, rid))
            log(store, "system", "run_failed", run["match_id"], {"run_id": rid, "step": step, "error": msg})
            return "failed"


def retry(store, rid, **kw):
    """Resume a failed run from its failed step."""
    store.q("UPDATE runs SET status = failed_step, failed_step = NULL, error_message = NULL WHERE id = %s "
            "AND status = 'failed' RETURNING id", (rid,))
    return resume(store, rid, **kw)
