"""Google News RSS: our code fetches today's team news; Gemini only reads the items we pass it (GEMINI_RULES.md Job 1).

Fields from the real feeds saved in tests/fixtures/news_rss/: channel/item with title, link, guid, pubDate (RFC 822),
description (HTML: an <a> to the article plus the source name) and source (text = outlet, attribute url).
TODO-CONFIRM: Google News RSS is unofficial and undocumented; the query syntax (quotes, OR, "when:2d") and the
hl/gl/ceid parameters were confirmed only by those real responses. We never fetch full articles or scrape sites.
"""
import datetime as dt
import difflib
import email.utils
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


BASE = "https://news.google.com/rss/search?"
UA = "MatchDayOptimizer/1.0 (student project; contact via github.com/shashankJani2508)"
TOPICS = '(squad OR injury OR "playing XI" OR "team news")'
CACHE_HOURS, WINDOW_HOURS, MAX_ITEMS = 2, 48, 20


def queries(team_a, team_b):
    """One query for the match and one per team."""
    return [f'"{team_a}" "{team_b}" {TOPICS} when:2d', f'"{team_a}" cricket {TOPICS} when:2d',
            f'"{team_b}" cricket {TOPICS} when:2d']


def feed_url(q):
    return BASE + urllib.parse.urlencode({"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})


def _http(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf8")


def parse(xml_text):
    out = []
    for it in ET.fromstring(xml_text).iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = it.findtext("description") or ""
        snippet = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", desc))).strip()
        src = it.find("source")
        try:
            pub = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            pub = None
        out.append({"title": title, "snippet": snippet, "link": (it.findtext("link") or "").strip(),
                    "guid": it.findtext("guid"), "source_name": src.text.strip() if src is not None and src.text else None,
                    "published_at": pub})
    return out


def _norm(title, source=None):
    t = title.lower()
    if source and t.endswith(" - " + source.lower()):
        t = t[: -len(source) - 3]
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def _mentions(text, names):
    low = text.lower()
    return any(re.search(r"\b" + re.escape(n.lower()) + r"\b", low) for n in names if n and len(n) >= 3)


def filter_items(items, now, players, teams, venue=None, hours=WINDOW_HOURS, cap=MAX_ITEMS):
    """Last `hours` before `now`; mentions a pooled player (full name or surname), a team or the venue; no near-duplicate
    headlines; newest first, at most `cap`."""
    names = set(teams)
    for p in players:
        names.add(p)
        if len(p.split()) > 1 and len(p.split()[-1]) >= 4:
            names.add(p.split()[-1])
    if venue:
        names.add(venue.split(",")[0].strip())
    kept, seen = [], []
    for it in sorted((i for i in items if i["published_at"]), key=lambda i: i["published_at"], reverse=True):
        if not (now - dt.timedelta(hours=hours) <= it["published_at"] <= now):
            continue
        if not _mentions(it["title"] + " " + it["snippet"], names):
            continue
        key = _norm(it["title"], it["source_name"])
        if any(key == k or difflib.SequenceMatcher(None, key, k).ratio() > 0.9 for k in seen):
            continue
        seen.append(key)
        kept.append(it)
        if len(kept) >= cap:
            break
    return kept


def fetch(store, q, http=_http, now=None):
    """Feed text for a query, cached 2 hours in api_cache."""
    now = now or dt.datetime.now(dt.timezone.utc)
    key = feed_url(q)
    c = store.cache_get("news_rss", key)
    if c and c["expires_at"] and c["expires_at"] > now:
        return c["response"]["xml"]
    xml_text = http(key)
    store.cache_put("news_rss", key, {"xml": xml_text}, now, now + dt.timedelta(hours=CACHE_HOURS))
    return xml_text


def news_for_match(store, match_id, run_id, team_a, team_b, players, venue=None, http=_http, now=None):
    """Fetch, filter and save to news_items. Returns [{id, title, snippet, link, source_name, published_at}]."""
    now = now or dt.datetime.now(dt.timezone.utc)
    items = []
    for q in queries(team_a, team_b):
        try:
            items += parse(fetch(store, q, http, now))
        except Exception:   # feed down or blocked: that query adds nothing; the moderator falls back to grounding
            continue
    kept = filter_items(items, now, players, [team_a, team_b], venue)
    saved = []
    for it in kept:
        nid = store.one("""INSERT INTO news_items (match_id, run_id, title, snippet, link, source_name, published_at, fetched_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (match_id, run_id, it["title"], it["snippet"][:500], it["link"], it["source_name"], it["published_at"], now))
        saved.append({"id": nid, **{k: it[k] for k in ("title", "snippet", "link", "source_name", "published_at")}})
    return saved
