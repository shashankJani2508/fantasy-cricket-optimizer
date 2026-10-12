"""Google News RSS (saved real feeds only): parsing, 48-hour window, mention filter, de-duplication, 20-item cap,
and the moderator rejecting a news id that isn't in the list."""
import datetime as dt
from pathlib import Path

from engine.gemini import check_moderator
from engine.sources.news_rss import fetch, filter_items, parse, queries

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "news_rss"


def items(name="pak_sl_match.xml"):
    return parse((FIX / name).read_text(encoding="utf8"))


def newest(its):
    return max(i["published_at"] for i in its if i["published_at"])


def test_parse_real_feed():
    its = items()
    assert len(its) == 40
    assert all(i["title"] and i["link"].startswith("https://news.google.com/") for i in its)
    assert all(i["published_at"] is not None and i["published_at"].tzinfo for i in its)
    assert any(i["source_name"] for i in its)


def test_48_hour_window():
    its = items()
    now = newest(its) + dt.timedelta(hours=1)
    kept = filter_items(its, now, [], ["Pakistan", "Sri Lanka"], cap=100)
    assert kept and all(now - dt.timedelta(hours=48) <= i["published_at"] <= now for i in kept)
    assert not filter_items(its, now + dt.timedelta(days=30), [], ["Pakistan", "Sri Lanka"])


def test_mention_filter_and_cap():
    its = items() + items("sri_lanka_team.xml")
    now = newest(its) + dt.timedelta(hours=1)
    assert filter_items(its, now, ["Zzyzx Qwerty"], ["Atlantis"]) == []
    kept = filter_items(its, now, [], ["Pakistan", "Sri Lanka"])
    assert 0 < len(kept) <= 20
    assert all("pakistan" in (i["title"] + i["snippet"]).lower() or "sri lanka" in (i["title"] + i["snippet"]).lower()
               for i in kept)


def test_near_duplicate_headlines_removed():
    its = items()
    dup = dict(its[0], title=its[0]["title"] + "!", link="https://news.google.com/rss/articles/other")
    now = newest(its) + dt.timedelta(hours=1)
    kept = filter_items(its + [dup], now, [], ["Pakistan", "Sri Lanka"], cap=100)
    titles = [k["title"] for k in kept]
    assert not (its[0]["title"] in titles and dup["title"] in titles)


def test_queries_one_per_match_and_team():
    q = queries("Pakistan", "Sri Lanka")
    assert len(q) == 3 and '"Pakistan" "Sri Lanka"' in q[0] and q[1].startswith('"Pakistan"') and q[2].startswith('"Sri Lanka"')


class _Cache:
    def __init__(self):
        self.c = {}

    def cache_get(self, s, k):
        return self.c.get((s, k))

    def cache_put(self, s, k, r, f, e):
        self.c[(s, k)] = {"response": r, "fetched_at": f, "expires_at": e}


def test_feed_cached_two_hours():
    calls = []
    xml = (FIX / "pak_sl_match.xml").read_text(encoding="utf8")
    http = lambda url: calls.append(url) or xml
    store, now = _Cache(), dt.datetime(2026, 10, 12, 12, tzinfo=dt.timezone.utc)
    fetch(store, "q", http, now)
    fetch(store, "q", http, now + dt.timedelta(minutes=90))
    assert len(calls) == 1
    fetch(store, "q", http, now + dt.timedelta(hours=3))
    assert len(calls) == 2


def test_moderator_rejects_news_id_not_in_list():
    d = {"adjustments": [
        {"player_id": "a", "change_percent": -10, "reason": "ruled out", "reason_type": "injury", "source_type": "rss", "news_item_id": 7},
        {"player_id": "b", "change_percent": -10, "reason": "hamstring", "reason_type": "injury", "source_type": "rss", "news_item_id": 99},
        {"player_id": "c", "change_percent": 5, "reason": "heavy dew expected", "reason_type": "dew_differs"}],
        "pitch_note": "no pitch report found", "news_checked": True, "_sources": []}
    out, errors, _ = check_moderator(d, {"a", "b", "c"}, 20, {7: {"link": "https://news.google.com/rss/articles/x", "published_at": None}})
    got = {a["player_id"]: a for a in out["adjustments"]}
    assert set(got) == {"a", "c"} and got["c"]["source_type"] == "forecast"
    assert got["a"]["source_url"] == "https://news.google.com/rss/articles/x" and got["a"]["news_item_id"] == 7
    assert any("99" in e for e in errors)
