"""CricketData.org client with a Neon cache (api_cache), data modes and call caps (api_usage).

Endpoints and fields are taken from real responses saved in tests/fixtures/cricketdata/
(base URL and endpoint paths from cricketdata.org's documentation pages).
Observed cost: match_squad and match_scorecard use 10 hits each (info.hitsUsed = 10 in the
saved responses); the other endpoints use 1.

Data modes (env CRICKETDATA_MODE, default offline):
  offline     never calls the API: Neon cache (any age), then the saved fixtures
  cache_only  never calls the API: Neon cache (any age) only
  live        calls allowed within three caps (settings): cricketdata_daily_limit (whole day),
              cricketdata_dev_daily_limit (development/CLI commands), cricketdata_max_calls_per_run
"""
import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.cricapi.com/v1/"
SOURCE = "cricketdata"
DEV_SOURCE = "cricketdata_dev"          # api_usage row counting development calls
CMD_PREFIX = "cricketdata_cmd:"         # api_usage rows counting calls per CLI command
COST = {"match_squad": 10, "match_scorecard": 10}
MODES = ("offline", "cache_only", "live")
# CricketData.org's generic "no photo" image (seen in the saved squad and players_info fixtures).
PLACEHOLDER_IMG = "https://h.cricapi.com/img/icon512.png"
FOREVER = dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc)

# Freshness from the spec (section 8.1). Finished scorecards / match info and past squads: permanent.
TTL = {
    "currentMatches": dt.timedelta(hours=6),
    "matches": dt.timedelta(hours=6),
    "series_info": dt.timedelta(hours=6),
    "match_squad": dt.timedelta(hours=6),
    "match_info": dt.timedelta(minutes=10),
    "match_scorecard": dt.timedelta(days=7),
    "players_info": dt.timedelta(days=30),
}

FIXTURES = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "cricketdata"
# Saved real responses and the request that produced each (tools/discover_cricketdata.py, 12 Oct 2026).
FIXTURE_INDEX = {
    ("match_scorecard", (("id", "0cb2b44c-69b3-4c50-b1a5-9af598ffecaf"),)): "match_scorecard.json",
    ("match_info", (("id", "0cb2b44c-69b3-4c50-b1a5-9af598ffecaf"),)): "match_info.json",
    ("series_info", (("id", "a67cb0af-300c-4449-8e80-e006301e5706"),)): "series_info.json",
    ("players_info", (("id", "52a6be27-1c5d-4c2b-86ab-98710ec7e0ef"),)): "players_info.json",
    ("match_squad", (("id", "586c0a37-7512-44c4-9e60-356a541d0ebb"),)): "match_squad.json",
    ("currentMatches", (("offset", 0),)): "currentMatches.json",
    ("matches", (("offset", 0),)): "matches.json",
}


class BudgetExhausted(Exception):
    pass


class ApiError(Exception):
    pass


def clean_image_url(url):
    """None for a missing photo or CricketData.org's generic placeholder (UI shows initials)."""
    return None if not url or url == PLACEHOLDER_IMG else url


def _http_get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf8"))


class CricketData:
    def __init__(self, store, api_key, daily_limit, now=None, http_get=None, mode=None,
                 dev_limit=None, run_limit=None, dev=True, command=None, dry_run=False):
        self.store = store
        self.api_key = api_key
        self.daily_limit = daily_limit
        self.dev_limit = dev_limit if dev_limit is not None else daily_limit
        self.run_limit = run_limit if run_limit is not None else daily_limit
        self.dev = dev
        self.command = command
        self.dry_run = dry_run
        self.mode = mode or os.environ.get("CRICKETDATA_MODE") or "offline"
        if self.mode not in MODES:
            raise ValueError(f"CRICKETDATA_MODE must be one of {MODES}")
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.http_get = http_get or _http_get
        self.data_stale = False
        self.warnings = []
        self.calls_this_run = 0     # hits used by this client (one command / one scoring run)
        self.would_call = 0         # dry run: hits the cache misses would have cost

    @staticmethod
    def request_key(endpoint, params):
        return endpoint + "?" + urllib.parse.urlencode(sorted(params.items()))

    def calls_today(self):
        return self.store.usage_get(SOURCE, self.now().date())

    def dev_calls_today(self):
        return self.store.usage_get(DEV_SOURCE, self.now().date())

    def summary(self):
        return (f"CricketData.org calls: this command {self.calls_this_run}, today {self.calls_today()} of "
                f"{self.daily_limit} (dev {self.dev_calls_today()} of {self.dev_limit})")

    def _warn(self, text):
        if text not in self.warnings:
            self.warnings.append(text)

    def _saved(self, cached, endpoint, why):
        """Return saved data (marking it stale) or None with a warning."""
        if cached:
            self.data_stale = True
            self._warn(f"Using saved data from {cached['fetched_at']:%Y-%m-%d %H:%M} UTC for {endpoint} ({why})")
            return cached["response"].get("data")
        self.data_stale = True
        self._warn(f"No saved data for {endpoint} ({why})")
        return None

    def _fixture(self, endpoint, params):
        name = FIXTURE_INDEX.get((endpoint, tuple(sorted(params.items()))))
        if not name:
            return None
        resp = json.loads((FIXTURES / name).read_text(encoding="utf8"))
        return resp

    def get(self, endpoint, permanent=False, **params):
        """Return the response `data` according to the data mode and caps."""
        key = self.request_key(endpoint, params)
        cached = self.store.cache_get(SOURCE, key)
        now = self.now()
        fresh = cached and cached["expires_at"] > now
        if self.mode in ("offline", "cache_only"):
            if fresh:
                return cached["response"].get("data")
            if cached:
                return self._saved(cached, endpoint, f"{self.mode} mode")
            if self.mode == "offline":
                fx = self._fixture(endpoint, params)
                if fx is not None:
                    self.data_stale = True
                    self._warn(f"Using a saved test response for {endpoint} (offline mode)")
                    return fx.get("data")
            return self._saved(None, endpoint, f"{self.mode} mode, no live calls")
        if fresh:
            return cached["response"].get("data")
        cost = COST.get(endpoint, 1)
        if self.dry_run:
            self.would_call += cost
            return cached["response"].get("data") if cached else None
        today = now.date()
        if self.calls_today() + cost > self.daily_limit:
            return self._saved(cached, endpoint, "daily CricketData.org limit reached")
        if self.dev and self.dev_calls_today() + cost > self.dev_limit:
            return self._saved(cached, endpoint, "development limit for today reached")
        if self.calls_this_run + cost > self.run_limit:
            return self._saved(cached, endpoint, "per-run call limit reached")
        try:
            resp = self.http_get(BASE + endpoint + "?" + urllib.parse.urlencode({"apikey": self.api_key, **params}))
        except Exception as e:   # outage, timeout, bad JSON
            return self._saved(cached, endpoint, f"CricketData.org request failed ({e})")
        used = int((resp.get("info") or {}).get("hitsUsed", cost))
        self.calls_this_run += used
        self.store.usage_add(SOURCE, today, used)
        if self.dev:
            self.store.usage_add(DEV_SOURCE, today, used)
        if self.command:
            self.store.usage_add(CMD_PREFIX + self.command, today, used)
        if resp.get("status") != "success":
            return self._saved(cached, endpoint, f"CricketData.org returned {resp.get('status')}: {resp.get('reason', '')}")
        resp.pop("apikey", None)
        data = resp.get("data")
        finished = isinstance(data, dict) and data.get("matchEnded")
        expires = FOREVER if (permanent or (endpoint in ("match_scorecard", "match_info") and finished)) \
            else now + TTL.get(endpoint, dt.timedelta(hours=1))
        self.store.cache_put(SOURCE, key, resp, now, expires)
        return data

    # endpoint helpers
    def current_matches(self):
        return self.get("currentMatches", offset=0) or []

    def matches(self, offset=0):
        return self.get("matches", offset=offset) or []

    def series_info(self, series_id):
        return self.get("series_info", id=series_id) or {}

    def match_info(self, match_id):
        return self.get("match_info", id=match_id) or {}

    def match_squad(self, match_id, match_finished=False):
        return self.get("match_squad", permanent=match_finished, id=match_id) or []

    def match_scorecard(self, match_id):
        return self.get("match_scorecard", id=match_id) or {}

    def player_info(self, player_id):
        return self.get("players_info", id=player_id) or {}
