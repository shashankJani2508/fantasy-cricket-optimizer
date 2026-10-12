"""Upcoming filter: internationals and IPL show, domestic and unclassifiable are hidden; history untouched."""
import json
from pathlib import Path

from engine.competitions import classify, load, visible

CFG = load()
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "cricketdata"


def kind(m):
    from engine.fresh import base_team
    t = [base_team(x) for x in m["teams"]]
    return classify(t[0], t[1], m["name"], "male", CFG)


def test_real_fixtures_international_shown_domestic_hidden():
    rows = {m["name"]: m for m in json.loads((FIX / "currentMatches.json").read_text(encoding="utf8"))["data"]}
    pak = next(m for n, m in rows.items() if n.startswith("Pakistan vs Sri Lanka"))
    ranji = next(m for n, m in rows.items() if "Ranji Trophy" in n)
    assert kind(pak) == "international" and visible("international", "male", CFG)
    assert kind(ranji) == "domestic" and not visible("domestic", "male", CFG)


def test_ipl_shows_and_unclassifiable_hidden():
    k = classify("Mumbai Indians", "Chennai Super Kings", "Indian Premier League 2027", "male", CFG)
    assert k == "ipl" and visible(k, "male", CFG)
    assert classify(None, "India", "x", "male", CFG) is None and not visible(None, "male", CFG)


def test_history_is_not_filtered():
    import inspect
    from engine import db, factors, score
    for mod in (db, factors, score):
        assert "competitions" not in inspect.getsource(mod)
