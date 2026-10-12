"""Gemini client and its four jobs (docs/GEMINI_RULES.md). The app's only model; it never calculates or picks.

REST generateContent (field names from Google's API reference and the real responses saved in
tests/fixtures/gemini/probe_*.json): systemInstruction, contents[].parts[].text / inlineData,
generationConfig.responseMimeType + responseJsonSchema + temperature, tools [{"googleSearch": {}}].
Structured output together with Google Search works on Gemini 3 models (docs: "Structured outputs with tools").
Every attempt is logged to gemini_calls; code checks everything before it is used.
"""
import base64
import json
import re
import time
import urllib.error
import urllib.request

from engine.env import env
from engine.factors import FACTORS

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_RETRIES = 2
TIMEOUT_S = 90
REASON_TYPES = {"injury", "batting_order", "bowling_role", "pitch_differs", "dew_differs"}
NEEDS_SOURCE = {"injury", "batting_order", "bowling_role"}
ROLES = {"WK", "BAT", "AR", "BOWL"}
BANNED = ("good player", "can win the match", "match winner")

PROMPTS = {
    "moderator": (
        "You are the moderator for a fantasy cricket scoring engine. You receive each allowed player's base score, "
        "calculated from statistics. Your only job is to adjust scores for information the statistics cannot see: "
        "injury or fitness news, a confirmed batting-order or bowling-role change, or today's pitch or dew where it "
        "differs from the venue's usual type, which the statistics already count. You get a numbered list of news items "
        "and you can also search Google for today's team news and pitch report. Every adjustment must cite its source: "
        "either source_type \"rss\" with the news item's id, or source_type \"search\" with the exact link of a search "
        "result you used. Give the news date as published_at when known; ignore news older than 48 hours before the "
        "start. If two sources report the same news for a player, make one adjustment. If sources disagree about a "
        "player (for example fit vs ruled out), make no adjustment for him and list him in conflicts. You may change a "
        "score by at most 20% up or down, and only with a one-line reason. Never adjust for reputation or popularity. "
        "Never invent facts. If you find nothing reliable, make no adjustment and say \"no news found\". Return JSON "
        "only, using the schema provided."),
    "explainer": (
        "You explain a fantasy cricket team to its owner, who must be able to defend each pick to his league group. "
        "You receive the final team, captain, vice-captain, four left-out players and the numbers behind each. Write "
        "one line per player and two to three lines each for the captain and vice-captain. Every line must cite a "
        "specific number or fact from the data provided. Do not choose or change the captain or vice-captain; explain "
        "why they lead on expected points. For each left-out player, give the actual reason he was left out. Never "
        "use generic lines such as \"in form\", \"good player\" or \"match winner\". Return JSON only, using the schema provided."),
    "analyst": (
        "You review a fantasy cricket model's repeated prediction errors. You receive one group where predictions have "
        "missed in the same direction across at least 10 matches, with the numbers behind it and the current factor "
        "weights. Describe the pattern in one plain-English sentence. Propose one change to one factor's weight, of at "
        "most 0.10, or propose no change if the pattern may be chance. Explain why in one or two lines. Use only the "
        "numbers given. Never apply the change. Return JSON only, using the schema provided."),
    "screenshot": (
        "You read screenshots from the Dream11 app. Copy exactly what is visible: player names as written, team, role "
        "(WK, BAT, AR or BOWL), credits, or points, and the user's rank if shown. If any value is unreadable or cut off, "
        "return null and mark the row unsure. Never guess, never add players, never calculate. Return JSON only, using "
        "the schema provided."),
}

PROMPT_VERSION = {"moderator": 3, "explainer": 1, "analyst": 1, "screenshot": 1}   # moderator v2: news items
_S, _N, _I = {"type": "string"}, {"type": "number"}, {"type": "integer"}
_line = {"type": "object", "properties": {"player_id": _S, "reason": _S}, "required": ["player_id", "reason"]}
SCHEMAS = {
    "moderator": {"type": "object", "properties": {
        "adjustments": {"type": "array", "items": {"type": "object", "properties": {
            "player_id": _S, "change_percent": _N, "reason": _S,
            "reason_type": {"type": "string", "enum": sorted(REASON_TYPES)}, "source_url": _S,
            "source_type": {"type": "string", "enum": ["rss", "search"]}, "news_item_id": {"type": ["integer", "null"]},
            "published_at": {"type": ["string", "null"]}},
            "required": ["player_id", "change_percent", "reason", "reason_type"]}},
        "conflicts": {"type": "array", "items": {"type": "object", "properties": {"player_id": _S, "note": _S},
                                                 "required": ["player_id"]}},
        "pitch_note": _S, "news_checked": {"type": "boolean"}},
        "required": ["adjustments", "pitch_note", "news_checked"]},
    "explainer": {"type": "object", "properties": {
        "players": {"type": "array", "items": _line}, "captain": _line, "vice_captain": _line,
        "bench": {"type": "array", "items": _line}},
        "required": ["players", "captain", "vice_captain", "bench"]},
    "analyst": {"type": "object", "properties": {
        "pattern": _S, "evidence": _S,
        "proposal": {"type": "object", "properties": {"factor": _S, "current_weight": _N, "proposed_weight": _N},
                     "required": ["factor", "current_weight", "proposed_weight"]},
        "why": _S}, "required": ["pattern", "evidence", "proposal", "why"]},
    "screenshot": {"type": "object", "properties": {
        "kind": {"type": "string", "enum": ["player_list", "points"]},
        "rows": {"type": "array", "items": {"type": "object", "properties": {
            "name_on_screen": _S, "team_code": {"type": ["string", "null"]},
            "role": {"type": ["string", "null"]}, "credits": {"type": ["number", "null"]},
            "points": {"type": ["number", "null"]}, "unsure": {"type": "boolean"}},
            "required": ["name_on_screen", "unsure"]}},
        "rank": {"type": ["integer", "null"]}}, "required": ["kind", "rows"]},
}


class GeminiFailed(Exception):
    """All attempts failed or were invalid; the caller uses its designed fallback (CLAUDE.md section 14)."""


def _http(body, model, key, timeout=TIMEOUT_S):
    req = urllib.request.Request(URL.format(model=model), json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")[:200]
        except Exception:
            msg = ""
        raise GeminiFailed(f"Gemini HTTP {e.code} {msg}".strip()) from None


def response_text(resp):
    """JSON text from the first candidate, skipping thought parts; plus any grounding source links."""
    c = (resp.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []) if not p.get("thought"))
    chunks = (c.get("groundingMetadata") or {}).get("groundingChunks") or []
    # TODO-CONFIRM: field names from Google's API reference (GroundingMetadata.groundingChunks[].web.uri / .title);
    # no real grounded response saved yet (search quota exhausted on 13 Oct 2026).
    return text, [{"uri": ch["web"]["uri"], "title": ch["web"].get("title")} for ch in chunks if ch.get("web", {}).get("uri")]


class Gemini:
    def __init__(self, store=None, transport=None, model=None, key=None, sleep=time.sleep):
        self.store, self.sleep = store, sleep
        self.model = model or env("GEMINI_MODEL")
        self._key = key
        self.transport = transport or (lambda body: _http(body, self.model, self._key or env("GEMINI_API_KEY")))

    # prompts are versioned in gemini_rules; the spec text above is the seed
    def prompt(self, job):
        if self.store is None:
            return PROMPTS[job]
        row = self.store.q("SELECT system_prompt, version FROM gemini_rules WHERE job = %s ORDER BY version DESC LIMIT 1",
                           (job,))
        if row and row[0][1] >= PROMPT_VERSION[job]:
            return row[0][0]
        self.store.q("INSERT INTO gemini_rules (job, system_prompt, version) VALUES (%s, %s, %s) RETURNING id",
                     (job, PROMPTS[job], PROMPT_VERSION[job]))
        return PROMPTS[job]

    def _log(self, job, run_id, summary, output, valid, errors, ms):
        if self.store is None:
            return
        from psycopg.types.json import Jsonb
        self.store.q("""INSERT INTO gemini_calls (job, run_id, model, input_summary, output, valid, validation_errors,
                        latency_ms) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                     (job, run_id, self.model, summary[:500], Jsonb(output), valid, Jsonb(errors), ms))

    def call(self, job, text, check, images=(), search=False, run_id=None, summary=""):
        """check(data) -> (clean, errors, retry). Up to 1 + MAX_RETRIES attempts with backoff."""
        parts = [{"text": text}] + [{"inlineData": {"mimeType": m, "data": base64.b64encode(b).decode()}}
                                    for m, b in images]
        body = {"systemInstruction": {"parts": [{"text": self.prompt(job)}]},
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": SCHEMAS[job],
                                     "temperature": 0.1}}
        if search:
            body["tools"] = [{"googleSearch": {}}]
        last = "no attempt"
        for attempt in range(1 + MAX_RETRIES):
            if attempt:
                self.sleep(2 ** attempt)
            t0 = time.time()
            try:
                resp = self.transport(body)
                raw, sources = response_text(resp)
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("not a JSON object")
                self.model = resp.get("modelVersion") or self.model
            except (GeminiFailed, ValueError, KeyError, TypeError, OSError) as e:
                last = f"{type(e).__name__}: {e}"
                if "HTTP 429" in last and attempt < MAX_RETRIES:
                    self.sleep(10)   # rate limited: wait longer than the normal backoff
                self._log(job, run_id, summary, {"error": last}, False, [last], int((time.time() - t0) * 1000))
                continue
            data["_sources"] = sources
            clean, errors, retry = check(data)
            self._log(job, run_id, summary, data, not errors, errors, int((time.time() - t0) * 1000))
            if not retry:
                return clean, errors
            last = "; ".join(errors)
        raise GeminiFailed(f"Gemini {job} failed after {1 + MAX_RETRIES} attempts ({last})")

    # Job 1
    def moderate(self, players, match, forecast=None, cap=20, run_id=None, news=None):
        """players: [{"player_id","name","team","base_score","factors","trust","thin_data"}]. news: saved news_items
        rows. Google Search grounding is on in the same call; every adjustment must cite an item id or a grounding link."""
        body = {"match": match, "forecast": forecast or "not available", "players": players}
        if news:
            body["news_items"] = [{"id": n["id"], "title": n["title"], "snippet": n["snippet"], "source": n["source_name"],
                                   "published": str(n["published_at"]), "link": n["link"]} for n in news]
        items = {n["id"]: n for n in news or []}
        start = match.get("start_time_utc")
        return self.call("moderator", json.dumps(body, default=str),
                         lambda d: check_moderator(d, {p["player_id"] for p in players}, cap, items, start),
                         search=True, run_id=run_id, summary=f"moderate {match.get('id')} {len(players)} players")

    # Job 2
    def explain(self, payload, run_id=None):
        """payload: {"team":[...], "captain_id", "vc_id", "bench":[...], "adjustments":[...]} with numbers per player."""
        team = [p["player_id"] for p in payload["team"]]
        bench = [p["player_id"] for p in payload["bench"]]
        state = {"tries": 0}

        def check(d):
            state["tries"] += 1
            return check_explainer(d, team, payload["captain_id"], payload["vc_id"], bench, final=state["tries"] > 1)
        return self.call("explainer", json.dumps(payload, default=str), check, run_id=run_id,
                         summary=f"explain {len(team)} players")

    # Job 3
    def analyse(self, group, weights, max_change=0.10):
        return self.call("analyst", json.dumps({"group": group, "current_weights": weights}, default=str),
                         lambda d: check_analyst(d, weights, max_change), summary=f"analyse {group.get('label')}")

    # Job 4
    def read_screenshot(self, kind, images, teams, expected_names, credits_range, points_range):
        text = json.dumps({"screenshot_kind": kind, "teams": teams, "expected_player_names": expected_names})
        return self.call("screenshot", text, lambda d: check_screenshot(d, kind, credits_range, points_range),
                         images=images, summary=f"screenshot {kind} x{len(images)}")


def _when(x):
    import datetime as dt
    if not x:
        return None
    try:
        t = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def check_moderator(d, pool, cap, news=None, start=None):
    """news: {news_item_id: {"link", "published_at", ...}} sent in the call; the grounding sources of the same call are
    in d["_sources"]. Each adjustment must cite an RSS id from `news` or a link that appears in those grounding sources
    (dew differs is from Open-Meteo data we sent). News older than 48 h before `start` is ignored. Same news from two
    sources gives one adjustment; conflicting news gives none plus a warning."""
    import datetime as dt
    news = news or {}
    search = {s["uri"]: s for s in d.get("_sources") or [] if isinstance(s, dict)}
    t0 = _when(start)
    errors, kept, warnings = [], {}, []
    if not isinstance(d.get("adjustments"), list):
        return None, ["adjustments missing"], True
    conflicted = {c.get("player_id") for c in d.get("conflicts") or [] if c.get("player_id") in pool}
    for a in d["adjustments"]:
        pid = a.get("player_id")
        if pid not in pool:
            errors.append(f"rejected {pid}: not in the allowed pool")
            continue
        rt, reason = a.get("reason_type"), (a.get("reason") or "").strip()
        if rt not in REASON_TYPES or not reason:
            errors.append(f"rejected {pid}: reason or reason type missing")
            continue
        try:
            req = float(a.get("change_percent"))
        except (TypeError, ValueError):
            errors.append(f"rejected {pid}: change_percent not a number")
            continue
        if req == 0:
            continue
        st, nid, url, published = a.get("source_type"), a.get("news_item_id"), (a.get("source_url") or "").strip(), None
        if rt == "dew_differs" and not url and nid is None:
            st = "forecast"
        elif st == "rss" or (nid is not None and st != "search"):
            if nid not in news:
                errors.append(f"rejected {pid}: news item {nid} is not in the list sent")
                continue
            st, url, published = "rss", news[nid]["link"], news[nid].get("published_at")
        else:
            if url not in search:
                errors.append(f"rejected {pid}: {url or 'no link'} is not among this call's search sources")
                continue
            st, nid, published = "search", None, _when(a.get("published_at"))
        if t0 and published and published < t0 - dt.timedelta(hours=48):
            errors.append(f"rejected {pid}: news from {published:%d %b} is older than 48 hours before the start")
            continue
        applied = max(-cap, min(cap, req))
        adj = {"player_id": pid, "requested_pct": req, "applied_pct": applied, "clipped": applied != req, "reason": reason,
               "reason_type": rt, "source_url": url or None, "source_type": st, "news_item_id": nid,
               "search_title": search.get(url, {}).get("title") if st == "search" else None}
        if pid in kept:
            if (kept[pid]["applied_pct"] > 0) != (applied > 0):
                conflicted.add(pid)
            else:
                errors.append(f"duplicate news for {pid}: one adjustment kept")
            continue
        kept[pid] = adj
    for pid in conflicted:
        kept.pop(pid, None)
        warnings.append(pid)
        errors.append(f"conflicting news for {pid}: no adjustment")
    clean = {"adjustments": list(kept.values()), "pitch_note": d.get("pitch_note") or "no pitch report found",
             "news_checked": bool(d.get("news_checked")), "sources": list(search.values()), "conflicts": warnings}
    return clean, errors, False


def is_generic(line):
    low = (line or "").lower()
    if not low.strip() or any(b in low for b in BANNED):
        return True
    if not re.search(r"\d", low):   # every line must cite a number or a fact; a line with no number is checked by eye
        return "in form" in low or len(low) < 25
    return False


def check_explainer(d, team, cap_id, vc_id, bench, final=False):
    errors = []
    lines = {}
    for kind, rows in (("player", d.get("players") or []), ("bench", d.get("bench") or [])):
        for r in rows:
            key = (kind, r.get("player_id"))
            if key in lines:
                errors.append(f"{kind} {key[1]} explained twice")
            lines[key] = r.get("reason") or ""
    for kind, want in (("captain", cap_id), ("vice_captain", vc_id)):
        got = (d.get(kind) or {}).get("player_id")
        if got != want:
            errors.append(f"{kind} is {got}, optimizer chose {want}")
        lines[(kind, want)] = (d.get(kind) or {}).get("reason") or ""
    missing = [p for p in team if ("player", p) not in lines] + [p for p in bench if ("bench", p) not in lines]
    extra = [k for k in lines if k[0] in ("player", "bench") and k[1] not in (team if k[0] == "player" else bench)]
    if missing:
        errors.append(f"missing lines for {missing}")
    if extra:
        errors.append(f"lines for players not given: {[k[1] for k in extra]}")
    structural = bool(errors)
    rows = [{"player_id": pid, "kind": kind, "text": t, "generic_flag": is_generic(t)}
            for (kind, pid), t in lines.items() if not (kind in ("player", "bench") and (kind, pid) in extra)]
    generic = [r["player_id"] for r in rows if r["generic_flag"]]
    if generic:
        errors.append(f"generic lines for {generic}")
    if structural:
        return None, errors, True
    return rows, errors, bool(generic) and not final


def check_analyst(d, weights, max_change):
    p = d.get("proposal") or {}
    factor = p.get("factor")
    errors = []
    if factor not in FACTORS and factor not in (None, "", "none"):
        return None, [f"unknown factor {factor}"], True
    if factor in (None, "", "none"):
        return {**d, "proposal": None}, errors, False
    cur = float(weights[factor])
    try:
        prop = float(p.get("proposed_weight"))
    except (TypeError, ValueError):
        return None, ["proposed_weight not a number"], True
    if abs(prop - cur) > max_change + 1e-9:
        errors.append(f"change {prop - cur:+.3f} beyond ±{max_change}: clipped")
        prop = cur + max_change * (1 if prop > cur else -1)
    prop = max(0.0, prop)
    return {**d, "proposal": {"factor": factor, "current_weight": cur, "proposed_weight": round(prop, 4)}}, errors, False


def check_screenshot(d, kind, credits_range, points_range):
    errors, rows = [], []
    if d.get("kind") != kind:
        errors.append(f"screenshot read as {d.get('kind')}, expected {kind}")
    for r in d.get("rows") or []:
        name = (r.get("name_on_screen") or "").strip()
        if not name:
            errors.append("row without a name dropped")
            continue
        unsure = bool(r.get("unsure"))
        role = r.get("role")
        if role is not None and role not in ROLES:
            role, unsure = None, True
        vals = {}
        for f, (lo, hi) in (("credits", credits_range), ("points", points_range)):
            v = r.get(f)
            if v is not None and (not isinstance(v, (int, float)) or not lo <= v <= hi):
                v, unsure = None, True
            vals[f] = v
        if kind == "player_list" and (role is None or vals["credits"] is None):
            unsure = True
        if kind == "points" and vals["points"] is None:
            unsure = True
        rows.append({"name_on_screen": name, "team_code": r.get("team_code"), "role": role, **vals, "unsure": unsure})
    if not rows:
        return None, errors + ["no rows read"], True
    rank = d.get("rank") if isinstance(d.get("rank"), int) and d.get("rank") > 0 else None
    return {"kind": kind, "rows": rows, "rank": rank}, errors, False


def fallback_lines(team, bench, players, cap_id, vc_id):
    """Explainer fallback (CLAUDE.md section 14): numbers-only lines written by code, flagged as automatic."""
    def nums(pid):
        p = players[pid]
        f = p.get("factors") or {}
        bits = [f"expected {p['score']:.1f} points"]
        bits += [f"{k.replace('_', ' ')} {f[k]:.0f}" for k in ("venue", "form", "career") if f.get(k) is not None]
        return ", ".join(bits)
    rows = [{"player_id": pid, "kind": "player", "text": nums(pid).capitalize() + ".", "generic_flag": False}
            for pid in team]
    rows.append({"player_id": cap_id, "kind": "captain", "generic_flag": False,
                 "text": f"Highest expected score in the team ({players[cap_id]['score']:.1f}), so captain doubles it."})
    rows.append({"player_id": vc_id, "kind": "vice_captain", "generic_flag": False,
                 "text": f"Second-highest expected score ({players[vc_id]['score']:.1f}), so vice-captain at 1.5x."})
    rows += [{"player_id": b["player_id"], "kind": "bench", "text": b["reason_detail"].capitalize() + ".",
              "generic_flag": False} for b in bench]
    return rows
