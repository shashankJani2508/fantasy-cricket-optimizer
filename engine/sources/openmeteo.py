"""Open-Meteo forecast at the venue at match time (free, no key). Fields from the real responses saved in
tests/fixtures/openmeteo/ (geocode.json, forecast.json). Cached per venue per hour in api_cache."""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request

GEO = "https://geocoding-api.open-meteo.com/v1/search?"
FORECAST = "https://api.open-meteo.com/v1/forecast?"
HOURLY = "precipitation_probability,dew_point_2m,relative_humidity_2m,temperature_2m"
SUFFIX = re.compile(r"\b(international|cricket|stadium|ground|oval|park|club|academy|the)\b", re.I)


def _get(url, http=None):
    if http:
        return http(url)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def geocode(store, venue_id, name, city=None, http=None):
    """lat/lon for a venue, saved to venues so it is looked up once."""
    row = store.q("SELECT lat, lon FROM venues WHERE id = %s", (venue_id,))
    if row and row[0][0] is not None:
        return row[0][0], row[0][1]
    for term in filter(None, [city, SUFFIX.sub(" ", name or "").split(",")[0].strip(), name]):
        res = _get(GEO + urllib.parse.urlencode({"name": term, "count": 1}), http).get("results") or []
        if res:
            lat, lon = res[0]["latitude"], res[0]["longitude"]
            store.q("UPDATE venues SET lat = %s, lon = %s WHERE id = %s RETURNING id", (lat, lon, venue_id))
            return lat, lon
    return None


def forecast_at(store, venue_id, name, start_time, city=None, http=None):
    """{"rain_chance_pct", "dew_point_c", "humidity_pct", "temperature_c", "hour_utc"} or None (beyond range / no venue)."""
    if start_time is None:
        return None
    try:
        ll = geocode(store, venue_id, name, city, http)
    except OSError:
        return None
    if not ll:
        return None
    hour = start_time.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:00")
    key = f"{venue_id}|{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H}"
    cached = (store.cache_get("openmeteo", key) or {}).get("response")
    if cached is None:
        try:
            cached = _get(FORECAST + urllib.parse.urlencode({"latitude": ll[0], "longitude": ll[1], "hourly": HOURLY,
                                                             "timezone": "UTC", "forecast_days": 16}), http)
        except OSError:
            return None
        now = dt.datetime.now(dt.timezone.utc)
        store.cache_put("openmeteo", key, cached, now, now + dt.timedelta(hours=1))
    h = cached.get("hourly") or {}
    times = h.get("time") or []
    if hour not in times:
        return None
    i = times.index(hour)
    return {"hour_utc": hour, "rain_chance_pct": h["precipitation_probability"][i], "dew_point_c": h["dew_point_2m"][i],
            "humidity_pct": h["relative_humidity_2m"][i], "temperature_c": h["temperature_2m"][i]}
