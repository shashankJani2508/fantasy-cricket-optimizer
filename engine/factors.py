"""Prediction factors (shared with the live app). Each factor is the player's average Dream11
points in some situation, computed ONLY from matches dated strictly before the match being
predicted. Every public function checks this and raises PeekingError otherwise.
"""
import collections
import datetime as dt
from dataclasses import dataclass

FACTORS = ("form", "venue", "opponent", "current_touch", "opportunity", "career",
           "bat_first_or_chase", "pitch_type")
THIN_DATA_FACTORS = ("venue", "opponent", "opportunity", "bat_first_or_chase", "pitch_type")


class PeekingError(Exception):
    pass


@dataclass(frozen=True)
class Record:
    """One earlier player-match, as seen by the factor functions."""
    date: str            # YYYY-MM-DD
    group: str           # e.g. "T20-male"
    venue: str
    opponent: str
    batted_first: bool
    bat_band: str
    bowl_band: str
    points: float


@dataclass(frozen=True)
class Target:
    """The match being predicted (pre-match knowledge plus the toss outcome)."""
    date: str
    group: str
    venue: str
    opponent: str
    batted_first: bool


def assert_before(records, date, what="history"):
    for r in records:
        if r.date >= date:
            raise PeekingError(f"{what} contains a match dated {r.date}, not before {date}")


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def form(hist, n_matches=10, recent_double=5):
    """Last n matches (oldest -> newest order in hist); the most recent `recent_double` count twice."""
    last = hist[-n_matches:]
    if not last:
        return None
    weights = [2.0 if i >= len(last) - recent_double else 1.0 for i in range(len(last))]
    return sum(w * r.points for w, r in zip(weights, last)) / sum(weights)


def blend(avg, n, form_value, threshold):
    if n == 0 or avg is None:
        return form_value
    trust = min(n / threshold, 1.0)
    return trust * avg + (1 - trust) * form_value


def _mode_recent(values):
    """Most frequent value; ties go to the one seen most recently."""
    counts = collections.Counter(values)
    best = max(counts.values())
    for v in reversed(values):
        if counts[v] == best:
            return v


class VenueBook:
    """Running first-innings totals per venue for one format group. classify(date) only works
    for dates after everything added so far, so it cannot see the match being predicted."""

    def __init__(self, min_matches):
        self.min_matches = min_matches
        self.sum = collections.defaultdict(float)
        self.cnt = collections.defaultdict(int)
        self.total_sum = 0.0
        self.total_cnt = 0
        self.last_date = ""

    def add(self, date, venue, first_innings_total):
        self.last_date = max(self.last_date, date)
        self.sum[venue] += first_innings_total
        self.cnt[venue] += 1
        self.total_sum += first_innings_total
        self.total_cnt += 1

    def classify(self, venue, date):
        if self.last_date >= date:
            raise PeekingError(f"venue book holds a match dated {self.last_date}, not before {date}")
        if self.cnt[venue] < self.min_matches or self.total_cnt == 0:
            return "unknown"
        return "batting" if self.sum[venue] / self.cnt[venue] >= self.total_sum / self.total_cnt else "bowling"


def compute_factors(target, hist, other_hist, venue_type, cfg):
    """
    target      Target for the match being predicted.
    hist        Records for this player in the same format group, sorted by date, all earlier.
    other_hist  Records for this player in other format groups (same gender), sorted, all earlier.
    venue_type  callable(venue) -> "batting" / "bowling" / "unknown", built from earlier matches.
    Returns (factors dict, n dict) where n is the number of matches behind each factor.
    """
    assert_before(hist, target.date, "same-format history")
    assert_before(other_hist, target.date, "other-format history")
    if not hist:
        raise ValueError("compute_factors needs at least one earlier match (cold start)")
    thr = cfg["thin_data_threshold"]
    f = {}
    n = {}

    f["form"] = form(hist, cfg["form_matches"], cfg["form_recent_double"])
    n["form"] = min(len(hist), cfg["form_matches"])
    f["career"] = _mean([r.points for r in hist])
    n["career"] = len(hist)

    def situational(name, rows):
        avg = _mean([r.points for r in rows])
        n[name] = len(rows)
        f[name] = blend(avg, len(rows), f["form"], thr)

    situational("venue", [r for r in hist if r.venue == target.venue])
    situational("opponent", [r for r in hist if r.opponent == target.opponent])
    situational("bat_first_or_chase", [r for r in hist if r.batted_first == target.batted_first])

    recent = hist[-cfg["form_matches"]:]
    usual_bat = _mode_recent([r.bat_band for r in recent])
    usual_bowl = _mode_recent([r.bowl_band for r in recent])
    situational("opportunity", [r for r in hist if r.bat_band == usual_bat and r.bowl_band == usual_bowl])

    vt = venue_type(target.venue)
    if vt == "unknown":
        f["pitch_type"], n["pitch_type"] = f["form"], 0
    else:
        situational("pitch_type", [r for r in hist if venue_type(r.venue) == vt])

    # current_touch: last N other-format matches within D days before this match
    start = (dt.date.fromisoformat(target.date) - dt.timedelta(days=cfg["current_touch_days"])).isoformat()
    window = [r for r in other_hist if r.date >= start][-cfg["current_touch_matches"]:]
    by_group = collections.defaultdict(list)
    for r in other_hist:
        by_group[r.group].append(r.points)
    ratios = []
    for r in window:
        pts = by_group[r.group]
        avg = _mean(pts)
        # need a stable, positive average in that format for the ratio to mean anything
        if len(pts) >= cfg["cold_start_min_matches"] and avg and avg > 0:
            ratios.append(r.points / avg)
    f["current_touch"] = f["form"] * _mean(ratios) if ratios else f["form"]
    n["current_touch"] = len(ratios)
    return f, n


def predict(factors, weights):
    return sum(weights.get(k, 0.0) * factors[k] for k in FACTORS)


# ---------------------------------------------------------------- added for the scoring engine

def trust_from_n(n, full_trust):
    """Thin-data trust (spec 6.3): 0 for n = 0, else min(n / full_trust, 1)."""
    return 0.0 if n <= 0 else min(n / full_trust, 1.0)


def compute_factors_with_trust(target, hist, other_hist, venue_type, cfg, pre_toss=False):
    """compute_factors plus a trust per factor (form, career, current_touch = 1).
    pre_toss=True applies the spec's pre-toss rule: bat_first_or_chase = form, trust 0
    (target.batted_first is ignored)."""
    f, n = compute_factors(target, hist, other_hist, venue_type, cfg)
    trust = {"form": 1.0, "career": 1.0, "current_touch": 1.0}
    for k in THIN_DATA_FACTORS:
        trust[k] = trust_from_n(n[k], cfg["thin_data_threshold"])
    if pre_toss:
        f = dict(f)
        f["bat_first_or_chase"] = f["form"]
        trust["bat_first_or_chase"] = 0.0
    return f, trust
