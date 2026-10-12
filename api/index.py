"""HTTP API for the app (CLAUDE.md section 11): thin wrappers around /engine. One ASGI app; vercel.json routes
/api/* here. Visitors can read; anything that changes data needs the passcode session cookie."""
import datetime as dt
import hashlib
import hmac
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from psycopg.types.json import Jsonb

from engine import learning, pipeline
from engine.db import PgStore
from engine.env import ROOT, env
from engine.factors import FACTORS
from engine.gate import ROLES, load_rules, validate
from engine.gemini import Gemini, GeminiFailed
from engine.groups import from_any
from engine.matching import Matcher
from engine.settings import Settings
from engine.sources.openmeteo import forecast_at

app = FastAPI(title="Fantasy Cricket Match Day Optimizer API")
_local = threading.local()
COOKIE = "fc_session"
MAX_IMAGES, MAX_IMAGE_BYTES = 6, 6 * 1024 * 1024
RUN_LABELS = {"checking": "Checking who can play", "scoring": "Scoring players",
              "moderating": "Reading today's news and pitch report", "optimizing": "Building the best valid team",
              "explaining": "Writing the reasons"}


def db():
    s = getattr(_local, "store", None)
    try:
        if s is None or s.conn.closed:
            raise RuntimeError
        s.one("SELECT 1")
    except Exception:
        s = _local.store = PgStore()
    return s


# ---- auth ------------------------------------------------------------------------------------------------------
def _token():
    code = env("APP_PASSCODE")
    return hmac.new(code.encode(), b"aryan-session", hashlib.sha256).hexdigest() if code else None


def is_aryan(request: Request):
    """No APP_PASSCODE set = no passcode: the link is private to Aryan, so everyone who has it can use everything."""
    tok = _token()
    if tok is None:
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE, ""), tok)


def need_passcode(request: Request):
    if not is_aryan(request):
        raise HTTPException(401, "Enter the passcode to change anything.")


class Passcode(BaseModel):
    passcode: str


@app.post("/api/auth/passcode")
def passcode(body: Passcode, response: Response, request: Request):
    s = db()
    ip = request.client.host if request.client else "?"
    fails = s.one("""SELECT count(*) FROM activity_log WHERE action = 'passcode_failed' AND details->>'ip' = %s
                     AND at > now() - interval '15 minutes'""", (ip,))
    if fails >= 5:
        raise HTTPException(429, "Too many wrong tries. Wait 15 minutes and try again.")
    code = env("APP_PASSCODE")
    if not code or not hmac.compare_digest(body.passcode.encode(), code.encode()):
        pipeline.log(s, "system", "passcode_failed", None, {"ip": ip})
        raise HTTPException(401, "That passcode is not right.")
    response.set_cookie(COOKIE, _token(), max_age=30 * 86400, httponly=True, samesite="lax",
                        secure=env("VERCEL") is not None)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    return {"aryan": is_aryan(request)}


# ---- helpers ---------------------------------------------------------------------------------------------------
def _iso(t):
    return t.isoformat() if t else None


def team_view(s, tid):
    r = s.q("SELECT name, short_code, colour_hex FROM teams WHERE id = %s", (tid,))
    if not r:
        return None
    return {"id": tid, "name": r[0][0], "code": r[0][1] or r[0][0], "colour": r[0][2]}


def match_view(s, mid):
    r = s.q("""SELECT m.id, m.format, m.format_group, m.series_name, m.start_time, m.status, m.xi_announced,
                      m.team_a_id, m.team_b_id, v.id, v.name, v.city
                 FROM matches m LEFT JOIN venues v ON v.id = m.venue_id WHERE m.id = %s""", (mid,))
    if not r:
        raise HTTPException(404, "Match not found.")
    (i, fmt, group, series, start, status, xi, ta, tb, vid, vname, city) = r[0]
    return {"id": i, "format": fmt, "format_group": group, "series": series, "start_time": _iso(start),
            "status": status, "xi_announced": xi, "team_a": team_view(s, ta), "team_b": team_view(s, tb),
            "venue": vname, "venue_id": vid, "city": city, "_start": start}


def rules_for(group):
    return load_rules(ROOT / "config" / "dream11_rules.yaml", from_any(group).split("_")[0])


def stale_since(s):
    return s.one("""SELECT max(fetched_at) FROM api_cache WHERE source = 'cricketdata'""")


def _client(s):
    from engine.refresh import app_client
    return app_client(s)


# ---- upcoming --------------------------------------------------------------------------------------------------
@app.get("/api/matches/upcoming")
def upcoming(request: Request):
    s = db()
    now = dt.datetime.now(dt.timezone.utc)
    rows = s.q("""SELECT m.id FROM matches m WHERE m.status = 'upcoming' AND m.start_time BETWEEN %s AND %s
                  ORDER BY m.start_time""", (now, now + dt.timedelta(days=7)))
    out = []
    for (mid,) in rows:
        m = match_view(s, mid)
        fc = None
        try:
            fc = forecast_at(s, m["venue_id"], m["venue"], m.pop("_start"), m["city"]) if m["venue_id"] else None
        except Exception:
            fc = None
        ch = s.q("""SELECT choice, chosen_at FROM match_choices WHERE match_id = %s AND NOT undone
                    ORDER BY chosen_at DESC LIMIT 1""", (mid,))
        out.append({**m, "rain_chance": fc["rain_chance_pct"] if fc else None, "choice": ch[0][0] if ch else None})
    nxt = s.q("SELECT id FROM matches WHERE status = 'upcoming' AND start_time > %s ORDER BY start_time LIMIT 1",
              (now + dt.timedelta(days=7),))
    nm = match_view(s, nxt[0][0]) if nxt else None
    if nm:
        nm.pop("_start")
    fetched = stale_since(s)
    stale = fetched is not None and fetched < now - dt.timedelta(hours=26)
    return {"matches": out, "next_match": nm, "stale_since": _iso(fetched) if stale else None,
            "aryan": is_aryan(request)}


class Choice(BaseModel):
    choice: str


@app.post("/api/matches/{mid}/choice", dependencies=[Depends(need_passcode)])
def choose(mid: str, body: Choice):
    if body.choice not in ("play", "skip"):
        raise HTTPException(422, "Choice must be play or skip.")
    s = db()
    match_view(s, mid)
    s.q("INSERT INTO match_choices (match_id, choice) VALUES (%s, %s) RETURNING id", (mid, body.choice))
    pipeline.log(s, "aryan", f"match_{body.choice}", mid, {})
    return {"ok": True}


@app.delete("/api/matches/{mid}/choice", dependencies=[Depends(need_passcode)])
def undo_choice(mid: str):
    s = db()
    s.q("""UPDATE match_choices SET undone = true WHERE id = (SELECT id FROM match_choices WHERE match_id = %s
           AND NOT undone ORDER BY chosen_at DESC LIMIT 1) RETURNING id""", (mid,))
    return {"ok": True}


# ---- setup: players, screenshot, links, credits -----------------------------------------------------------------
def match_players(s, mid):
    rows = s.q("""SELECT DISTINCT ON (p.id) p.id, p.full_name, p.image_url, t.name, t.short_code, t.colour_hex
                    FROM match_xi x JOIN players p ON p.id = x.player_id JOIN teams t ON t.id = x.team_id
                   WHERE x.match_id = %s ORDER BY p.id""", (mid,))
    return [{"player_id": a, "name": b, "image_url": c, "team": d, "team_code": e or d, "colour": f}
            for a, b, c, d, e, f in rows]


@app.post("/api/matches/{mid}/prepare", dependencies=[Depends(need_passcode)])
def prepare(mid: str):
    """Load the squad (cache first) so screenshot names can be matched, and pre-fill from the last match."""
    s = db()
    m = match_view(s, mid)
    note = None
    if not match_players(s, mid):
        from engine.refresh import load_squad
        c = _client(s)
        _, unmatched, source = load_squad(s, c, mid)
        note = f"Players from {source}" + (f"; {len(unmatched)} names not matched" if unmatched else "")
        if c.data_stale:
            note = (note or "") + " (saved data)"
    players = match_players(s, mid)
    cur = {p: (cr, r, via) for p, cr, r, via in s.q(
        "SELECT player_id, credits, dream11_role, entered_via FROM credits WHERE match_id = %s", (mid,))}
    teams = (m["team_a"] or {}).get("id"), (m["team_b"] or {}).get("id")
    prev = s.q("""SELECT DISTINCT ON (c.player_id) c.player_id, c.credits, c.dream11_role FROM credits c
                  JOIN matches m ON m.id = c.match_id WHERE c.match_id <> %s AND
                  ((m.team_a_id = %s AND m.team_b_id = %s) OR (m.team_a_id = %s AND m.team_b_id = %s))
                  ORDER BY c.player_id, m.start_time DESC""", (mid, *teams, *teams[::-1]))
    prev = {p: (cr, r) for p, cr, r in prev}
    for p in players:
        if p["player_id"] in cur:
            cr, r, via = cur[p["player_id"]]
            p.update(credits=cr, role=r, from_last_match=False, saved=True)
        elif p["player_id"] in prev:
            cr, r = prev[p["player_id"]]
            p.update(credits=cr, role=r, from_last_match=True, saved=False)
        else:
            p.update(credits=None, role=None, from_last_match=False, saved=False)
    rules = rules_for(m["format_group"])
    return {"match": {k: v for k, v in m.items() if k != "_start"}, "players": players, "note": note,
            "budget": rules["credit_budget"], "players_needed": rules["players"]}


def _images(files):
    if not files or len(files) > MAX_IMAGES:
        raise HTTPException(422, f"Add 1 to {MAX_IMAGES} screenshots.")
    out = []
    for f in files:
        b = f.file.read(MAX_IMAGE_BYTES + 1)
        if len(b) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Each screenshot must be under 6 MB.")
        if f.content_type not in ("image/png", "image/jpeg", "image/webp"):
            raise HTTPException(415, "Screenshots must be PNG, JPEG or WebP.")
        out.append((f.content_type, b))
    return out


def _read(s, mid, kind, files):
    m = match_view(s, mid)
    players = match_players(s, mid)
    st = Settings(s)
    try:
        out, _ = Gemini(s).read_screenshot(kind, _images(files),
                                           [t["name"] for t in (m["team_a"], m["team_b"]) if t],
                                           [p["name"] for p in players], st.get("screenshot_credits_range"),
                                           st.get("screenshot_points_range"))
    except GeminiFailed:
        raise HTTPException(502, "Couldn't read the screenshot. Try a clearer one, or type the values instead.")
    # the same player can appear on several screenshots (e.g. list without credits + preview with credits): merge
    merged = {}
    for r in out["rows"]:
        k = (r["name_on_screen"].lower(), r.get("team_code"), r.get("role"))   # two "K Mendis" differ by role
        if k in merged:
            m0 = merged[k]
            for f in ("role", "credits", "points"):
                if m0.get(f) is None and r.get(f) is not None:
                    m0[f] = r[f]
            m0["unsure"] = (m0["role"] is None or (kind == "player_list" and m0["credits"] is None)
                            or (kind == "points" and m0["points"] is None))
        else:
            merged[k] = r
    out["rows"] = list(merged.values())
    matcher = Matcher(s)
    by_team = {}
    for p in players:
        by_team.setdefault(p["team_code"], []).append((p["player_id"], p["name"]))
    hint_all = [(p["player_id"], p["name"]) for p in players]
    names = [(r["name_on_screen"].lower(), r.get("team_code")) for r in out["rows"]]
    for r in out["rows"]:
        hint = by_team.get(r.get("team_code")) or hint_all
        # identical names in one team (e.g. two "K Mendis") are remembered with their Dream11 role
        twin = names.count((r["name_on_screen"].lower(), r.get("team_code"))) > 1
        r["link_name"] = f"{r['name_on_screen']} ({r.get('role')})" if twin else r["name_on_screen"]
        r["player_id"] = (matcher.resolve("dream11", r["link_name"], [(p, n) for p, n in hint if s.links("dream11", r["link_name"])])
                          if twin else matcher.resolve("dream11", r["name_on_screen"], hint))
        if r["player_id"] is None:
            cut = [pid for pid, n in hint if truncated_match(r["name_on_screen"], n)]
            if len(cut) == 1:   # Dream11 cuts long names ("C Wickramas..."); accept only a unique prefix match
                r["player_id"] = cut[0]
                s.add_link(cut[0], "dream11", r["name_on_screen"])
        if r["player_id"] is None:
            from engine.matching import initials_match, surname_initial_match
            r["suggestions"] = [pid for pid, n in hint if initials_match(r["name_on_screen"], n)
                                or surname_initial_match(r["name_on_screen"], n)][:3]
    return out


def truncated_match(shown, full):
    """'C Wickramas...' vs 'C Wickramasinghe' / 'SSD Arachchige' / 'Sineth Jayawardena': same given-name initial and
    the visible surname is the start of the real one."""
    name = shown.strip()
    core = name.rstrip(".… ").strip()
    if core == name or len(core.split()) < 2:
        return False
    ini, pre = core.split()[0][0].upper(), core.split()[-1].lower()
    parts = full.split()
    if len(parts) < 2 or not parts[-1].lower().startswith(pre):
        return False
    first = parts[0]
    given = set(first.upper()) if first.isupper() and len(first) <= 4 else {w[0].upper() for w in parts[:-1]}
    return ini in given


@app.post("/api/matches/{mid}/screenshots/player-list", dependencies=[Depends(need_passcode)])
def read_player_list(mid: str, files: list[UploadFile] = File(...)):
    return _read(db(), mid, "player_list", files)


@app.post("/api/matches/{mid}/screenshots/points", dependencies=[Depends(need_passcode)])
def read_points(mid: str, files: list[UploadFile] = File(...)):
    return _read(db(), mid, "points", files)


class Link(BaseModel):
    player_id: str
    name_on_screen: str


@app.post("/api/players/link", dependencies=[Depends(need_passcode)])
def link(body: Link):
    s = db()
    if not s.player_exists(body.player_id):
        raise HTTPException(404, "Player not found.")
    s.add_link(body.player_id, "dream11", body.name_on_screen.strip(), confirmed=True)
    return {"ok": True}


class CreditRow(BaseModel):
    player_id: str
    credits: float
    role: str
    entered_via: str = "typed"


class Credits(BaseModel):
    rows: list[CreditRow]


@app.put("/api/matches/{mid}/credits", dependencies=[Depends(need_passcode)])
def save_credits(mid: str, body: Credits):
    s = db()
    known = {p["player_id"] for p in match_players(s, mid)}
    for r in body.rows:
        if r.role not in ROLES or not 0 < r.credits <= 20 or r.player_id not in known:
            raise HTTPException(422, f"Check {r.player_id}: role must be WK, BAT, AR or BOWL and credits a number.")
        if r.entered_via not in ("screenshot", "typed", "prefill"):
            raise HTTPException(422, "entered_via must be screenshot, typed or prefill.")
    s.q("DELETE FROM credits WHERE match_id = %s RETURNING id", (mid,))
    with s.conn.cursor() as c:
        c.executemany("""INSERT INTO credits (match_id, player_id, credits, dream11_role, entered_via, confirmed_at)
                         VALUES (%s, %s, %s, %s, %s, now())""",
                      [(mid, r.player_id, r.credits, r.role, r.entered_via) for r in body.rows])
    pipeline.log(s, "aryan", "credits_saved", mid, {"players": len(body.rows)})
    return {"ok": True, "players": len(body.rows)}


# ---- runs ------------------------------------------------------------------------------------------------------
class RunReq(BaseModel):
    run_type: str = "pre_toss"


@app.post("/api/matches/{mid}/runs", dependencies=[Depends(need_passcode)])
def new_run(mid: str, body: RunReq):
    s = db()
    m = match_view(s, mid)
    try:
        rules_for(m["format_group"])
    except Exception as e:
        raise HTTPException(409, str(e))
    return {"run_id": pipeline.start(s, mid, body.run_type)}


@app.post("/api/runs/{rid}/advance", dependencies=[Depends(need_passcode)])
def advance(rid: str):
    """Run exactly one pipeline step (keeps every request well inside the function time limit)."""
    s = db()
    run = pipeline._run(s, rid)
    step = run["status"]
    if step not in ("done", "failed"):
        pipeline.resume(s, rid, client=_client(s) if step == "scoring" else None, max_steps=1)
    return run_status(s, rid)


def run_status(s, rid):
    r = s.q("""SELECT status, failed_step, error_message, coalesce(warnings, '[]'), run_type, data_stale, match_id
                 FROM runs WHERE id = %s""", (rid,))
    if not r:
        raise HTTPException(404, "Run not found.")
    st, fs, err, warns, rt, stale, mid = r[0]
    return {"run_id": rid, "match_id": mid, "status": st, "failed_step": fs, "error_message": err, "warnings": warns,
            "run_type": rt, "data_stale": stale, "steps": [{"key": k, "label": v} for k, v in RUN_LABELS.items()]}


@app.get("/api/runs/{rid}")
def get_run(rid: str):
    s = db()
    out = run_status(s, rid)
    if out["status"] != "done":
        return out
    m = match_view(s, out["match_id"])
    m.pop("_start")
    lst = pipeline.aryan_list(s, out["match_id"])
    photos = dict(s.q("SELECT id, image_url FROM players WHERE id = ANY(%s)", (list(lst),)))
    codes = {t["name"]: t for t in (m["team_a"], m["team_b"]) if t}
    preds = {r[0]: r for r in s.q("""SELECT player_id, base_score, adjusted_score, gemini_change_pct, factors, trust,
                                       thin_data, fallback_step, fallback_note FROM predictions WHERE run_id = %s""",
                                  (rid,))}
    adj = {r[0]: {"applied_pct": r[1], "requested_pct": r[2], "clipped": r[3], "reason": r[4], "source_url": r[5]}
           for r in s.q("""SELECT player_id, applied_pct, requested_pct, clipped, reason, source_url FROM gemini_adjustments
                           WHERE run_id = %s""", (rid,))}
    expl = {}
    for pid, kind, text, gen in s.q("SELECT player_id, kind, text, generic_flag FROM explanations WHERE run_id = %s", (rid,)):
        expl.setdefault(pid, {})[kind] = {"text": text, "generic": gen, "automatic": False}
    players = {}
    for pid, p in lst.items():
        pr = preds.get(pid)
        t = codes.get(p["side"]) or {}
        players[pid] = {"player_id": pid, "name": p["name"], "team": p["side"], "team_code": t.get("code", p["side"]),
                        "colour": t.get("colour"), "role": p["role"], "credits": p["credits"],
                        "image_url": photos.get(pid),
                        "base": pr[1] if pr else None, "expected": pr[2] if pr else None,
                        "change_pct": pr[3] if pr else None, "factors": pr[4] if pr else None,
                        "trust": pr[5] if pr else None, "thin": pr[6] if pr else None,
                        "fallback_step": pr[7] if pr else None, "fallback_note": pr[8] if pr else None,
                        "adjustment": adj.get(pid), "explanations": expl.get(pid, {})}
    teams = {k: {"player_ids": ids, "captain_id": c, "vc_id": v, "total_expected": te, "total_actual": ta,
                 "credits_used": cu} for k, ids, c, v, te, ta, cu in s.q(
        """SELECT DISTINCT ON (kind) kind, player_ids, captain_id, vc_id, total_expected, total_actual, credits_used
             FROM teams_picked WHERE run_id = %s OR (kind = 'aryan_final' AND run_id IN
                  (SELECT id FROM runs WHERE match_id = %s)) ORDER BY kind, id DESC""", (rid, out["match_id"]))}
    bench = [dict(zip(("player_id", "rank", "reason_code", "reason_detail", "points_cost"), r)) for r in s.q(
        "SELECT player_id, rank, reason_code, reason_detail, points_cost FROM bench WHERE run_id = %s ORDER BY rank", (rid,))]
    pool = (s.one("SELECT pool_type FROM runs WHERE id = %s", (rid,)) or {})
    rules = rules_for(m["format_group"])
    return {**out, "match": m, "players": players, "teams": teams, "bench": bench, "factors": list(FACTORS),
            "pool": pool.get("player_ids", []), "pool_type": pool.get("teams", {}),
            "rules": {"players": rules["players"], "credit_budget": rules["credit_budget"],
                      "max_per_side": rules["max_per_side"], "role_limits": rules["role_limits"],
                      "captain_multiplier": rules["captain_multiplier"], "vc_multiplier": rules["vc_multiplier"]}}


class Proposed(BaseModel):
    player_ids: list[str]
    captain_id: str | None = None
    vc_id: str | None = None
    reason: str | None = None


def _gate(s, rid, body):
    run = pipeline._run(s, rid)
    players = pipeline.aryan_list(s, run["match_id"])
    pool = set((run["pool"] or {}).get("player_ids") or players)
    g = validate(body.player_ids, body.captain_id, body.vc_id, players, rules_for(run["group"]), pool)
    return run, players, g


@app.post("/api/runs/{rid}/gate")
def gate(rid: str, body: Proposed):
    _, _, g = _gate(db(), rid, body)
    return {"passed": g.passed, "failures": [{"rule": r, "message": m} for r, m in g.failures], "first_fix": g.first_fix}


@app.put("/api/runs/{rid}/final-team", dependencies=[Depends(need_passcode)])
def final_team(rid: str, body: Proposed):
    s = db()
    run, players, g = _gate(s, rid, body)
    if not g.passed:
        raise HTTPException(422, g.first_fix)
    if body.reason and len(body.reason) > 200:
        raise HTTPException(422, "Keep the reason to one line (200 characters).")
    sysr = s.q("SELECT player_ids, captain_id, vc_id FROM teams_picked WHERE run_id = %s AND kind = 'system'", (rid,))[0]
    preds = dict(s.q("SELECT player_id, adjusted_score FROM predictions WHERE run_id = %s", (rid,)))
    rules = rules_for(run["group"])
    total = sum(preds.get(p, 0) for p in body.player_ids) + (rules["captain_multiplier"] - 1) * preds.get(body.captain_id, 0) \
        + (rules["vc_multiplier"] - 1) * preds.get(body.vc_id, 0)
    used = sum(players[p]["credits"] for p in body.player_ids)
    s.q("""INSERT INTO teams_picked (run_id, kind, player_ids, captain_id, vc_id, total_expected, credits_used, gate_passed)
           VALUES (%s, 'aryan_final', %s, %s, %s, %s, %s, true) RETURNING id""",
        (rid, Jsonb(body.player_ids), body.captain_id, body.vc_id, total, used))
    s.q("DELETE FROM overrides WHERE run_id = %s RETURNING id", (rid,))
    outs = [p for p in sysr[0] if p not in body.player_ids]
    ins = [p for p in body.player_ids if p not in sysr[0]]
    cap = None
    if (body.captain_id, body.vc_id) != (sysr[1], sysr[2]):
        cap = {"from": {"captain": sysr[1], "vc": sysr[2]}, "to": {"captain": body.captain_id, "vc": body.vc_id}}
    pairs = list(zip(outs, ins)) or ([(None, None)] if cap else [])
    for i, (o, n) in enumerate(pairs):
        s.q("""INSERT INTO overrides (run_id, match_id, out_player_id, in_player_id, captaincy_change, reason, gate_passed)
               VALUES (%s, %s, %s, %s, %s, %s, true) RETURNING id""",
            (rid, run["match_id"], o, n, Jsonb(cap) if i == 0 and cap else None, body.reason))
    pipeline.log(s, "aryan", "final_team_saved", run["match_id"], {"run_id": rid, "swaps": len(outs)})
    return {"ok": True}


# ---- results tab -----------------------------------------------------------------------------------------------
@app.get("/api/results/matches")
def results_list():
    s = db()
    rows = s.q("""SELECT DISTINCT ON (r.match_id) r.match_id, r.id, r.run_type, r.status, m.status, m.start_time,
                         m.xi_announced, (SELECT count(*) FROM results x WHERE x.match_id = r.match_id) > 0,
                         (SELECT count(*) FROM metrics x WHERE x.match_id = r.match_id) > 0
                    FROM runs r JOIN matches m ON m.id = r.match_id
                   WHERE r.warnings IS NOT NULL
                   ORDER BY r.match_id, (r.status = 'done') DESC, (r.run_type = 'post_toss') DESC, r.started_at DESC""")
    out = []
    for mid, rid, rt, rst, mst, start, xi, has_res, has_met in rows:
        m = match_view(s, mid)
        m.pop("_start")
        if has_met:
            state = "Scored"
        elif mst == "finished":
            state = "Enter results"
        elif xi and rt == "pre_toss":
            state = "Toss done: refresh"
        else:
            state = "Final" if rt == "post_toss" else "Provisional"
        out.append({**m, "run_id": str(rid), "run_status": rst, "state": state,
                    "finished": mst in ("finished", "abandoned")})
    out.sort(key=lambda x: x["start_time"] or "", reverse=True)
    return {"matches": out}


@app.get("/api/matches/{mid}/latest-run")
def latest_run(mid: str):
    s = db()
    rid = learning.match_run(s, mid) or s.one("SELECT id::text FROM runs WHERE match_id = %s ORDER BY started_at DESC LIMIT 1",
                                              (mid,))
    if not rid:
        raise HTTPException(404, "No team built for this match yet.")
    return {"run_id": rid}


class ResultRow(BaseModel):
    player_id: str
    points: float


class Results(BaseModel):
    rows: list[ResultRow]
    rank: int | None = None
    entered_via: str = "screenshot"


@app.put("/api/matches/{mid}/results", dependencies=[Depends(need_passcode)])
def save_results(mid: str, body: Results):
    s = db()
    m = match_view(s, mid)
    if any(not -100 <= r.points <= 1000 for r in body.rows) or (body.rank is not None and body.rank < 1):
        raise HTTPException(422, "Points must be between -100 and 1000 and the rank a positive number.")
    # all 22 players' provisional points from the CricketData.org scorecard (cached; never fetched twice when finished)
    try:
        from engine.fresh import fill_recent
        from engine.points import load_points_config
        pts = load_points_config(ROOT / "config" / "dream11_points.yaml")
        start = m["_start"]
        series = (s.match(mid) or {}).get("series_id")
        ids = [p["player_id"] for p in match_players(s, mid)]
        if series and ids:
            fill_recent(s, _client(s), pts, ids, (start + dt.timedelta(days=1)).date().isoformat(), series, days=1)
    except Exception as e:   # scorecard missing or API down: Aryan's points still save
        pipeline.log(s, "system", "scorecard_points_failed", mid, {"error": str(e)[:300]})
    mism = learning.save_results(s, mid, [r.model_dump() for r in body.rows], body.rank, body.entered_via)
    s.q("UPDATE matches SET status = 'finished' WHERE id = %s AND status <> 'abandoned' RETURNING id", (mid,))
    res = learning.after_results(s, mid, Gemini(s))
    return {"ok": True, "mismatches": mism, "suggestions": len(res["suggestions"])}


@app.get("/api/matches/{mid}/scorecard")
def scorecard(mid: str):
    s = db()
    r = s.q("""SELECT system_points, aryan_points, simple_points, perfect_points, points_roi, efficiency, captain_hit,
                      override_hit_rate, gemini_value, mae, points_final FROM metrics WHERE match_id = %s""", (mid,))
    if not r:
        raise HTTPException(404, "No scorecard yet: enter results first.")
    keys = ("system_points", "aryan_points", "simple_points", "perfect_points", "points_roi", "efficiency", "captain_hit",
            "override_hit_rate", "gemini_value", "mae", "points_final")
    met = dict(zip(keys, r[0]))
    rid = learning.match_run(s, mid)
    pts = learning.actual_points(s, mid)
    order = sorted(pts, key=lambda p: -pts[p])
    sysr = s.q("SELECT player_ids, captain_id FROM teams_picked WHERE run_id = %s AND kind = 'system'", (rid,))[0]
    preds = dict(s.q("SELECT player_id, adjusted_score FROM predictions WHERE run_id = %s", (rid,)))
    names = dict(s.q("SELECT id, full_name FROM players WHERE id = ANY(%s)", (list(set(pts) | set(preds)),)))
    group = s.one("SELECT format_group FROM matches WHERE id = %s", (mid,))
    row = learning._active_row(s, group)
    thr = Settings(s).float("real_miss_mae_multiplier") * float(row["test_mae"]) if row and row["test_mae"] else None
    pva = [{"player_id": p, "name": names.get(p, p), "predicted": preds.get(p), "actual": pts.get(p),
            "real_miss": thr is not None and p in pts and preds.get(p) is not None and abs(preds[p] - pts[p]) > thr}
           for p in sysr[0]]
    swaps = [{"out": names.get(o, o), "in": names.get(i, i), "out_points": pts.get(o), "in_points": pts.get(i)}
             for o, i in s.q("SELECT out_player_id, in_player_id FROM overrides WHERE match_id = %s AND out_player_id IS NOT NULL",
                             (mid,))]
    mism = s.one("SELECT count(*) FROM results WHERE match_id = %s AND mismatch", (mid,))
    cap = sysr[1]
    return {**met, "captain_rank": (order.index(cap) + 1) if cap in order else None,
            "captain_name": names.get(cap), "predicted_vs_actual": pva, "swaps": swaps, "mismatches": mism}


# ---- learnings -------------------------------------------------------------------------------------------------
@app.get("/api/learnings")
def learnings():
    s = db()
    series = [{"match_id": a, "date": _iso(b), "format_group": c, "mae": d} for a, b, c, d in s.q(
        """SELECT mt.match_id, m.start_time, mt.format_group, mt.mae FROM metrics mt JOIN matches m ON m.id = mt.match_id
           WHERE mt.mae IS NOT NULL ORDER BY m.start_time""")]
    summ = s.q("""SELECT count(*), sum(points_roi), avg(captain_hit::int) FROM metrics""")[0]
    backtest = [{"format_group": from_any(g), "mae": t} for g, t in s.q(
        "SELECT format_group, test_mae FROM rubric_versions WHERE is_active ORDER BY format_group")]
    inbox = []
    for r in s.q("""SELECT w.id, w.kind, w.format_group, w.proposal, w.gemini_text, w.history_check, w.history_mae_before,
                           w.history_mae_after, w.created_at, p.group_type, p.group_value, p.window_matches
                      FROM weight_suggestions w LEFT JOIN patterns p ON p.id = w.pattern_id
                     WHERE w.aryan_decision = 'pending' ORDER BY w.created_at DESC"""):
        inbox.append(dict(zip(("id", "kind", "format_group", "proposal", "gemini_text", "history_check", "mae_before",
                               "mae_after", "created_at", "group_type", "group_value", "matches"), r)))
    for x in inbox:
        x["created_at"] = _iso(x["created_at"])
    groups = [dict(zip(("format_group", "group_type", "group_value", "window_matches", "real_misses", "status",
                        "direction", "avg_error"), r)) for r in s.q(
        """SELECT format_group, group_type, group_value, window_matches, real_misses, status, direction, avg_error
             FROM patterns ORDER BY format_group, group_type, group_value""")]
    versions = [dict(zip(("id", "format_group", "version", "weights", "source", "parent_version_id", "approved_by",
                          "approved_at", "created_at", "is_active", "reliable", "points_values_final"), r)) for r in s.q(
        """SELECT id, format_group, version, weights, source, parent_version_id, approved_by, approved_at, created_at,
                  is_active, reliable, points_values_final FROM rubric_versions ORDER BY format_group, id""")]
    for v in versions:
        v["format_group"] = from_any(v["format_group"])
        v["approved_at"], v["created_at"] = _iso(v["approved_at"]), _iso(v["created_at"])
    return {"series": series, "summary": {"matches_scored": summ[0], "points_roi": summ[1], "captain_hit_rate": summ[2]},
            "backtest_mae": backtest, "inbox": inbox, "groups": groups, "versions": versions,
            "window": Settings(s).int("flag_window_matches")}


class Decision(BaseModel):
    decision: str
    version: dict | None = None


@app.post("/api/suggestions/{sid}/decision", dependencies=[Depends(need_passcode)])
def decision(sid: int, body: Decision):
    s = db()
    try:
        vid = learning.decide(s, sid, body.decision, body.version)
    except learning.DecisionError as e:
        raise HTTPException(422, str(e))
    ver = s.one("SELECT version FROM rubric_versions WHERE id = %s", (vid,)) if vid else None
    return {"ok": True, "new_version": ver}


# ---- settings --------------------------------------------------------------------------------------------------
@app.get("/api/settings")
def get_settings():
    s = db()
    rules = yaml.safe_load((ROOT / "config" / "dream11_rules.yaml").read_text(encoding="utf8"))
    points = yaml.safe_load((ROOT / "config" / "dream11_points.yaml").read_text(encoding="utf8"))
    teams = [{"id": a, "name": b, "code": c, "colour": d} for a, b, c, d in s.q(
        """SELECT DISTINCT t.id, t.name, t.short_code, t.colour_hex FROM teams t
           JOIN matches m ON t.id IN (m.team_a_id, m.team_b_id) WHERE m.start_time > now() - interval '60 days'
           ORDER BY t.name""")]
    return {"rules": rules, "points": points, "teams": teams, "gemini_cap_percent": Settings(s).float("gemini_cap_percent")}


class SettingsPut(BaseModel):
    gemini_cap_percent: float | None = None
    team_colours: dict[str, str] | None = None


@app.put("/api/settings", dependencies=[Depends(need_passcode)])
def put_settings(body: SettingsPut):
    import re
    s = db()
    if body.gemini_cap_percent is not None:
        if not 0 <= body.gemini_cap_percent <= 20:
            raise HTTPException(422, "Gemini's limit must be between 0 and 20%.")
        s.q("UPDATE settings SET value = %s, updated_by = 'aryan', updated_at = now() WHERE key = 'gemini_cap_percent' RETURNING key",
            (Jsonb(body.gemini_cap_percent),))
    for tid, hexv in (body.team_colours or {}).items():
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", hexv):
            raise HTTPException(422, f"Colour for {tid} must look like #1E6B45.")
        s.q("UPDATE teams SET colour_hex = %s WHERE id = %s RETURNING id", (hexv, tid))
    pipeline.log(s, "aryan", "settings_changed", None, body.model_dump())
    return {"ok": True}


# ---- cron ------------------------------------------------------------------------------------------------------
@app.get("/api/cron/daily")
def cron(request: Request):
    secret = env("CRON_SECRET")
    if not secret or request.headers.get("authorization") != f"Bearer {secret}":
        raise HTTPException(401, "Not allowed.")
    from engine.refresh import refresh_fixtures
    s = db()
    c = _client(s)
    saved = refresh_fixtures(s, c)
    pipeline.log(s, "system", "daily_refresh", None, {"matches": len(saved), "calls": c.calls_this_run,
                                                      "stale": c.data_stale, "warnings": c.warnings[:5]})
    return {"matches": len(saved), "calls": c.calls_this_run, "data_stale": c.data_stale}
