"""Player photos from Wikimedia (saved real responses only): correct match, ambiguity, wrong country, non-free licence,
placeholder rule, never overwriting a real CricketData.org photo."""
import copy
import datetime as dt
import json
from pathlib import Path

from engine.photos import free_licence, pick, refresh_player, wikimedia_photo
from engine.sources.cricketdata import PLACEHOLDER_IMG

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "wikimedia"
load = lambda n: json.loads((FIX / f"{n}.json").read_text(encoding="utf8"))


def fake_get(responses):
    def get(url):
        if "wbsearchentities" in url:
            return responses["search"]
        if "wbgetentities" in url:
            return responses["entities"]
        return responses["commons"]
    return get


REAL = {"search": load("search_shadab_khan"), "entities": load("entities_shadab_khan"), "commons": load("commons_shadab_khan")}


def test_accepts_the_right_person_with_free_licence():
    photo, why = wikimedia_photo(["Shadab Khan"], "Pakistan", fake_get(REAL))
    assert why is None and photo["license"] == "CC BY 3.0" and photo["page"].endswith("File:Shadab_Khan.png")
    assert photo["url"].startswith("https://upload.wikimedia.org/")


def test_rejects_wrong_country():
    assert pick(REAL["entities"]["entities"], ["Shadab Khan"], "Sri Lanka") == (None, "no Wikidata match")


def test_rejects_ambiguous_name():
    ents = copy.deepcopy(REAL["entities"]["entities"])
    ents["Q999"] = copy.deepcopy(ents["Q24005995"])   # a second Pakistani cricketer with the same name
    q, why = pick(ents, ["Shadab Khan"], "Pakistan")
    assert q is None and why.startswith("ambiguous")


def test_rejects_non_free_licences():
    meta = load("commons_shadab_khan")["query"]["pages"]
    md = list(meta.values())[0]["imageinfo"][0]["extmetadata"]
    assert free_licence(md) == "CC BY 3.0"
    for lic in ("cc-by-nc-4.0", "cc-by-nd-3.0", "all rights reserved", ""):
        assert free_licence({**md, "License": {"value": lic}, "LicenseShortName": {"value": lic}}) is None
    assert free_licence({"License": {"value": "cc0"}, "LicenseShortName": {"value": "CC0"}}) == "cc0"


class Store:
    def __init__(self, url, source=None, checked=None):
        self.row = [url, source, checked]
        self.updates = []

    def q(self, sql, args=()):
        if sql.startswith("SELECT"):
            return [tuple(self.row)]
        self.updates.append((sql, args))
        return [(1,)]

    def full_name(self, pid):
        return "Shadab Khan"

    def links_for_player(self, pid, source):
        return []


def test_never_overwrites_a_real_cricketdata_photo():
    s = Store("https://h.cricapi.com/img/players/real.jpg")
    assert refresh_player(s, "p", "Pakistan", get=lambda u: (_ for _ in ()).throw(AssertionError("no lookup"))) == ("cricketdata", None)
    assert all("image_url" not in sql for sql, _ in s.updates)


def test_placeholder_counts_as_no_photo():
    s = Store(PLACEHOLDER_IMG)
    src, why = refresh_player(s, "p", "Pakistan", get=fake_get(REAL), now=dt.datetime(2026, 10, 13, tzinfo=dt.timezone.utc))
    assert src == "wikimedia" and why is None and "image_source = 'wikimedia'" in s.updates[-1][0]
