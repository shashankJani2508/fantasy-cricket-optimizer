"""CricketData.org client with a Neon cache (api_cache) and a daily budget (api_usage).

Endpoints and fields are taken from real responses saved in tests/fixtures/cricketdata/
(base URL and endpoint paths from cricketdata.org's documentation pages).
Observed cost: match_squad and match_scorecard use 10 hits each (info.hitsUsed = 10 in the
saved responses); the other endpoints use 1.
"""
import datetime as dt
import json
import urllib.parse
import urllib.request

BASE = "https://api.cricapi.com/v1/"
SOURCE = "cricketdata"
COST = {"match_squad": 10, "match_scorecard": 10}

# Freshness from the spec (section 8.1). Scorecards: 7 days once the match is finished.
TTL = {
    "currentMatches": dt.timedelta(hours=6),
    "matches": dt.timedelta(hours=6),
    "series_info": dt.timedelta(hours=6),
    "match_squad": dt.timedelta(hours=6),
    "match_info": dt.timedelta(minutes=10),
    "match_scorecard": dt.timedelta(days=7),
    "players_info": dt.timedelta(days=30),
}


class BudgetExhausted(Exception):
    pass


class ApiError(Exception):
    pass


def _http_get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf8"))


class CricketData:
    def __init__(self, store, api_key, daily_limit, now=None, http_get=None):
        self.store = store
        self.api_key = api_key
        self.daily_limit = daily_limit
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.http_get = http_get or _http_get
        self.data_stale = False
        self.warnings = []

    @staticmethod
    def request_key(endpoint, params):
        return endpoint + "?" + urllib.parse.urlencode(sorted(params.items()))

    def calls_today(self):
        return self.store.usage_get(SOURCE, self.now().date())

    def get(self, endpoint, **params):
        """Return the response `data`. Fresh cache first; else a live call if the budget allows;
        else stale cache with data_stale set; else raise."""
        key = self.request_key(endpoint, params)
        cached = self.store.cache_get(SOURCE, key)
        now = self.now()
        if cached and cached["expires_at"] > now:
            return cached["response"].get("data")
        cost = COST.get(endpoint, 1)
        if self.calls_today() + cost > self.daily_limit:
            return self._stale(cached, endpoint, "daily CricketData.org limit reached")
        try:
            resp = self.http_get(BASE + endpoint + "?" + urllib.parse.urlencode({"apikey": self.api_key, **params}))
        except Exception as e:   # outage, timeout, bad JSON
            return self._stale(cached, endpoint, f"CricketData.org request failed ({e})")
        used = (resp.get("info") or {}).get("hitsUsed", cost)
        self.store.usage_add(SOURCE, now.date(), int(used))
        if resp.get("status") != "success":
            return self._stale(cached, endpoint, f"CricketData.org returned {resp.get('status')}: {resp.get('reason', '')}")
        resp.pop("apikey", None)
        self.store.cache_put(SOURCE, key, resp, now, now + TTL.get(endpoint, dt.timedelta(hours=1)))
        return resp.get("data")

    def _stale(self, cached, endpoint, why):
        if cached:
            self.data_stale = True
            self.warnings.append(f"Using saved data from {cached['fetched_at']:%Y-%m-%d %H:%M} UTC for {endpoint} ({why})")
            return cached["response"].get("data")
        if "limit" in why:
            raise BudgetExhausted(f"{why}; no saved data for {endpoint}")
        raise ApiError(f"{why}; no saved data for {endpoint}")

    # endpoint helpers
    def current_matches(self):
        return self.get("currentMatches", offset=0) or []

    def matches(self, offset=0):
        return self.get("matches", offset=offset) or []

    def series_info(self, series_id):
        return self.get("series_info", id=series_id) or {}

    def match_info(self, match_id):
        return self.get("match_info", id=match_id) or {}

    def match_squad(self, match_id):
        return self.get("match_squad", id=match_id) or []

    def match_scorecard(self, match_id):
        return self.get("match_scorecard", id=match_id) or {}

    def player_info(self, player_id):
        return self.get("players_info", id=player_id) or {}
