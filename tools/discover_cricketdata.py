"""One real call per CricketData.org endpoint; saves raw responses (API key redacted)."""
import json, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
KEY = [l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text().splitlines() if l.startswith("CRICKETDATA_API_KEY=")][0]
OUT = ROOT / "tests" / "fixtures" / "cricketdata"

def call(endpoint, **params):
    q = urllib.parse.urlencode({"apikey": KEY, **params})
    with urllib.request.urlopen(f"https://api.cricapi.com/v1/{endpoint}?{q}", timeout=30) as r:
        body = r.read().decode("utf8")
    (OUT / f"{endpoint}.json").write_text(body.replace(KEY, "REDACTED"), encoding="utf8")
    d = json.loads(body)
    print(endpoint, d.get("status"), d.get("info", {}).get("hitsToday"), "/", d.get("info", {}).get("hitsLimit"), d.get("reason", ""))
    return d

which = sys.argv[1]
if which == "lists":
    m = call("matches", offset=0)
    c = call("currentMatches", offset=0)
else:
    endpoint, mid = which, sys.argv[2]
    call(endpoint, id=mid)
