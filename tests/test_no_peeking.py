"""Proves factor functions only ever see matches dated strictly before the match predicted."""
import copy

import pytest
import yaml

from backtest.parse import Match, PlayerMatch
from backtest.run_backtest import ROOT, replay
from engine.factors import PeekingError, Record, Target, VenueBook, compute_factors
from engine.points import PointsConfigError, load_points_config

CFG = yaml.safe_load((ROOT / "config" / "backtest.yaml").read_text(encoding="utf8"))


def rec(date, pts, group="T20-male"):
    return Record(date, group, "V1", "TeamB", True, "1-3", "none", pts)


def test_compute_factors_rejects_same_day_or_future_history():
    t = Target("2025-01-10", "T20-male", "V1", "TeamB", True)
    for bad in ("2025-01-10", "2025-02-01"):
        with pytest.raises(PeekingError):
            compute_factors(t, [rec("2025-01-01", 10), rec(bad, 50)], [], lambda v: "unknown", CFG)
        with pytest.raises(PeekingError):
            compute_factors(t, [rec("2025-01-01", 10)], [rec(bad, 50, "ODI-male")], lambda v: "unknown", CFG)


def test_venue_book_rejects_classifying_a_date_it_already_holds():
    b = VenueBook(1)
    b.add("2025-01-10", "V1", 180)
    with pytest.raises(PeekingError):
        b.classify("V1", "2025-01-10")
    assert b.classify("V1", "2025-01-11") in ("batting", "bowling")


def _match(i, date, pts_by_player):
    m = Match(f"m{i}", date, "T20", "male", "T20", "V1", ["A", "B"], "A", 150 + i)
    for pid in pts_by_player:
        m.players[pid] = PlayerMatch(pid, pid, "A", "B", 1, "1-3", "none", False, {})
    return m


def _run(matches, points):
    return replay(matches, lambda m, pm: {"batting": 0, "bowling": 0, "fielding": 0, "playing_xi": 0,
                                          "total": points[(m.match_id, pm.player_id)]}, CFG, "2000-01-01")[0]


def test_changing_future_or_same_day_results_does_not_change_earlier_predictions():
    dates = ["2025-01-01", "2025-01-05", "2025-01-09", "2025-01-12", "2025-01-12", "2025-01-20"]
    matches = [_match(i, d, ["p1"]) for i, d in enumerate(dates)]
    points = {(m.match_id, "p1"): 10.0 * (i + 1) for i, m in enumerate(matches)}
    base = {(r["match_id"]): r["factors"] for r in _run(matches, points)}

    # perturb the same-day pair and everything after: predictions up to and including 12 Jan must not move
    changed = dict(points)
    for mid in ("m3", "m4", "m5"):
        changed[(mid, "p1")] = 999.0
    after = {(r["match_id"]): r["factors"] for r in _run(copy.deepcopy(matches), changed)}
    for mid in ("m3", "m4"):
        assert after[mid] == base[mid], f"{mid} saw a same-day or future result"
    assert after["m5"] != base["m5"]   # sanity: later matches do see them


def test_points_config_refuses_nulls(tmp_path):
    txt = (ROOT / "config" / "dream11_points.yaml").read_text(encoding="utf8")
    bad = tmp_path / "points.yaml"
    bad.write_text(txt.replace("wicket: 30", "wicket: null", 1), encoding="utf8")
    with pytest.raises(PointsConfigError) as e:
        load_points_config(bad)
    assert "T20.bowling.wicket" in str(e.value)
    load_points_config(ROOT / "config" / "dream11_points.yaml")   # the real file is complete
