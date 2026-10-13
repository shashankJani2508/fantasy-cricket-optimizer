"""Player photos: CricketData.org playerImg if real, else Wikimedia Commons via Wikidata, else none (initials avatar).

Fields and IDs from real responses saved in tests/fixtures/wikimedia/ (12-13 Oct 2026):
  cricketer (occupation) = Q12299841; Pakistan = Q843 (national team Q182538); Sri Lanka = Q854 (national team Q203092).
  Country evidence on a person: P27 citizenship, P1532 country for sport, or P54 member of the national team.
  Commons imageinfo (iiprop=url|extmetadata, iiurlwidth=400): thumburl, descriptionurl, extmetadata License /
  LicenseShortName / Artist.
Never show the wrong person: a match needs exact name (label or alias), occupation cricketer, matching country and
exactly one candidate left. TODO-CONFIRM: Wikimedia's guidance on hotlinking upload.wikimedia.org thumbnails from an
app (we use the API's thumburl, cache results 30 days, and send a descriptive User-Agent).
"""
import datetime as dt
import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from engine.sources.cricketdata import PLACEHOLDER_IMG

UA = "MatchDayOptimizer/1.0 (student project; https://github.com/shashankJani2508/fantasy-cricket-optimizer)"
WD = "https://www.wikidata.org/w/api.php?"
COMMONS = "https://commons.wikimedia.org/w/api.php?"
CRICKETER = "Q12299841"
COUNTRIES = {  # team name -> (country item, national cricket team item), confirmed by the saved searches
    "Pakistan": ("Q843", "Q182538"),
    "Sri Lanka": ("Q854", "Q203092"),
    # confirmed 13 Oct 2026, tests/fixtures/wikimedia/search_national_teams.json
    "India": ("Q668", "Q1143793"), "West Indies": (None, "Q912881"), "Australia": ("Q408", "Q142555"),
    "England": ("Q21", "Q1321565"), "New Zealand": ("Q664", "Q1143797"), "South Africa": ("Q258", "Q1423651"),
    "Bangladesh": ("Q902", "Q806537"), "Afghanistan": ("Q889", "Q86477"), "Zimbabwe": ("Q954", "Q1254704"),
    "Ireland": ("Q27", "Q137660"),
}
RECHECK_DAYS = 30


def http_json(url, pause=0.3):
    time.sleep(pause)   # polite rate
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]+", " ", s).split()


def free_licence(meta):
    """Public domain, CC0, CC BY, CC BY-SA only (no NC / ND / unknown)."""
    lic = (meta.get("License", {}).get("value") or "").lower()
    short = (meta.get("LicenseShortName", {}).get("value") or "").lower()
    if "nc" in re.split(r"[-\s]", lic) or "nd" in re.split(r"[-\s]", lic):
        return None
    if lic == "cc0" or lic.startswith("pd") or "public domain" in short:
        return short or lic
    if re.fullmatch(r"cc-by(-sa)?(-\d(\.\d)?)?(-[a-z]+)?", lic):
        return meta.get("LicenseShortName", {}).get("value") or lic
    return None


def _ids(claims, prop):
    return {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get(prop, [])
            if isinstance(c["mainsnak"].get("datavalue", {}).get("value"), dict)}


def initials_ok(short, label):
    """'K Pooran' / 'KMA Paul' vs 'Nicholas Pooran' / 'Keemo Paul': same surname and the first given-name initial
    appears in the short form's initials. Only used with the cricketer + team + single-candidate checks."""
    a, b = norm(short), norm(label)
    if len(a) < 2 or len(b) < 2 or a[-1] != b[-1]:
        return False
    given = "".join(w[0] for w in a[:-1]) if not (len(a[0]) <= 4 and short.split()[0].isupper()) else a[0]
    return b[0][0] in given


def pick(entities, names, team):
    """The single entity that is this player, or (None, reason)."""
    want = {" ".join(norm(n)) for n in names if n}
    country, nat_team = COUNTRIES.get(team, (None, None))
    if not country and not nat_team:
        return None, f"no confirmed Wikidata country for {team}"
    hits = []
    for q, e in entities.items():
        labels = [e.get("labels", {}).get("en", {}).get("value", "")] + [a["value"] for a in e.get("aliases", {}).get("en", [])]
        if not want & {" ".join(norm(l)) for l in labels} and not any(initials_ok(n, l) for n in names if n for l in labels):
            continue
        c = e.get("claims", {})
        if CRICKETER not in _ids(c, "P106"):
            continue
        if not (country and country in _ids(c, "P27") | _ids(c, "P1532")) and nat_team not in _ids(c, "P54"):
            continue
        hits.append(q)
    if len(hits) != 1:
        return None, "no Wikidata match" if not hits else f"ambiguous ({len(hits)} candidates)"
    return hits[0], None


def wikimedia_photo(names, team, get=http_json):
    """-> ({url, license, author, page}, None) or (None, reason)."""
    ids = []
    surnames = [norm(n)[-1] for n in names if n and len(norm(n)) > 1]
    for n in list(dict.fromkeys([n for n in names if n] + surnames))[:4]:
        d = get(WD + urllib.parse.urlencode({"action": "wbsearchentities", "search": n, "language": "en", "type": "item",
                                             "limit": 7, "format": "json"}))
        ids += [x["id"] for x in d.get("search", []) if x["id"] not in ids]
    if not ids:
        return None, "no Wikidata match"
    ents = get(WD + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(ids[:50]), "props": "labels|aliases|claims",
                                            "languages": "en", "format": "json"})).get("entities", {})
    q, why = pick(ents, names, team)
    if not q:
        return None, why
    files = [c["mainsnak"].get("datavalue", {}).get("value") for c in ents[q].get("claims", {}).get("P18", [])]
    if not files or not files[0]:
        return None, "no image on Wikidata"
    page = list(get(COMMONS + urllib.parse.urlencode({"action": "query", "titles": "File:" + files[0], "prop": "imageinfo",
                                                      "iiprop": "url|extmetadata", "iiurlwidth": 400, "format": "json"}))
                .get("query", {}).get("pages", {}).values())
    info = (page[0].get("imageinfo") or [{}])[0] if page else {}
    lic = free_licence(info.get("extmetadata", {}))
    if not lic:
        return None, "non-free or unknown licence"
    author = html.unescape(re.sub(r"<[^>]+>", "", info.get("extmetadata", {}).get("Artist", {}).get("value", ""))).strip()
    return {"url": info.get("thumburl") or info.get("url"), "license": lic, "author": author or "unknown",
            "page": info.get("descriptionurl")}, None


def refresh_player(store, pid, team, force=False, get=http_json, now=None):
    """Fill one player's photo fields. Never overwrites a real CricketData.org photo."""
    now = now or dt.datetime.now(dt.timezone.utc)
    url, source, checked = store.q("SELECT image_url, image_source, image_checked_at FROM players WHERE id = %s", (pid,))[0]
    if url and url != PLACEHOLDER_IMG and source in (None, "cricketdata"):
        store.q("UPDATE players SET image_source = 'cricketdata', image_checked_at = %s WHERE id = %s RETURNING id", (now, pid))
        return "cricketdata", None
    if not force and checked and checked > now - dt.timedelta(days=RECHECK_DAYS):
        return source or "none", "checked recently"
    names = [store.full_name(pid)] + store.links_for_player(pid, "cricketdata") + store.links_for_player(pid, "dream11")
    try:
        photo, why = wikimedia_photo(names, team, get)
    except OSError as e:
        return source or "none", f"Wikimedia unavailable ({type(e).__name__})"
    if photo:
        store.q("""UPDATE players SET image_url = %s, image_source = 'wikimedia', image_license = %s, image_author = %s,
                   image_page_url = %s, image_checked_at = %s, image_skip_reason = NULL WHERE id = %s RETURNING id""",
                (photo["url"], photo["license"], photo["author"], photo["page"], now, pid))
        return "wikimedia", None
    store.q("""UPDATE players SET image_url = NULL, image_source = 'none', image_checked_at = %s, image_skip_reason = %s
               WHERE id = %s RETURNING id""", (now, why, pid))
    return "none", why


def squad_players(store, days=7):
    """(player_id, name, team) for every player in the squads of matches in the next `days` days."""
    return store.q("""SELECT DISTINCT p.id, p.full_name, t.name FROM match_xi x JOIN players p ON p.id = x.player_id
                      JOIN teams t ON t.id = x.team_id JOIN matches m ON m.id = x.match_id
                      WHERE m.start_time BETWEEN now() - interval '1 day' AND now() + %s * interval '1 day'
                      ORDER BY 3, 2""", (days,))
