"""The scoring engine (spec 9.6, 9.7): base score = sum(weight x factor value) per player."""
import datetime as dt
from dataclasses import dataclass, field

from engine.factors import FACTORS, Record, Target, VenueBook, compute_factors_with_trust
from engine.fallback import fallback
from engine.fresh import fill_recent
from engine.rubric import active_weights
from engine.settings import Settings

SUPPORTED = {"T20_men", "T20_women", "ODI_men", "ODI_women", "Test_men", "Test_women"}


@dataclass
class PlayerScore:
    player_id: str
    base_score: float | None
    factors: dict
    trust: dict
    weights: dict
    fallback_step: int
    fallback_note: str | None
    thin_data: bool
    provisional_inputs: bool


@dataclass
class ScoreResult:
    run_id: str
    match_id: str
    format_group: str
    run_type: str
    rubric_version_id: str
    provisional_weights: bool
    borrowed_from_group: str | None
    data_stale: bool
    players: list = field(default_factory=list)
    unmatched_names: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class ScoringFailed(Exception):
    def __init__(self, step, message, run_id):
        super().__init__(message)
        self.step, self.run_id = step, run_id


def _records(rows):
    return [Record(r["date"], r["format_group"], r["venue"] or "", r["opponent"] or "", bool(r["batted_first"]),
                   r["bat_band"], r["bowl_band"], float(r["points"])) for r in rows]


def score_match(store, client, points_cfg, match_id, player_ids, run_type, run_id=None, unmatched_names=None,
                coverage=None):
    if run_type not in ("pre_toss", "post_toss"):
        raise ValueError("run_type must be pre_toss or post_toss")
    step = "load match"
    if run_id is None:
        run_id = store.create_run(match_id, run_type)
    warnings, version_id, data_stale = [], None, False
    try:
        m = store.match(match_id)
        if m is None:
            raise ValueError(f"Match {match_id} not found")
        group = m["format_group"]
        if group not in SUPPORTED:
            raise ValueError("Format not supported")
        settings = Settings(store)
        cfg = settings.factor_cfg()
        cold = cfg["cold_start_min_matches"]
        threshold = settings.float("thin_data_trust_threshold")
        match_date = m["date"]

        step = "rubric"
        choice = active_weights(store, group)
        version_id = choice.version_id
        if choice.provisional:
            warnings.append("Rubric weights are provisional (points values not final)")
        if choice.borrowed_from:
            warnings.append(f"{group} weights unreliable; borrowed from {choice.borrowed_from}")
        if coverage:
            matched, listed = coverage
            warnings.append(f"{matched} of {listed} players matched")
            if listed - matched > 1:
                warnings.append(f"{listed - matched} players unmatched and not scored: confirm each once with "
                                "python -m engine.cli link --source cricketdata --name \"<name>\" --player <id>")

        step = "fill recent"
        if client is not None:
            warnings += fill_recent(store, client, points_cfg, player_ids, match_date, m.get("series_id"),
                                    dot_min_balls=settings.int("dot_rate_min_balls"))

        step = "score players"
        book = VenueBook(cfg["pitch_min_matches"])
        for date, venue, total in store.first_innings(group, match_date):
            book.add(date, venue, total)
        vcache = {}

        def venue_type(v):
            if v not in vcache:
                vcache[v] = book.classify(v, match_date)
            return vcache[v]

        players = []
        for pid in player_ids:
            rows = store.history(pid, match_date)
            same = [r for r in rows if r["format_group"] == group]
            gender = group.split("_")[1]
            other = [r for r in rows if r["format_group"] != group and r["format_group"].endswith("_" + gender)]
            prov = any(r["is_provisional"] for r in rows)
            if len(same) < cold:
                fb = fallback(store, client, points_cfg, pid, group, match_date)
                for w in fb.warnings:
                    if w not in warnings:
                        warnings.append(w)
                players.append(PlayerScore(pid, fb.base_score, {}, {}, choice.weights, fb.step, fb.note, True, prov))
                continue
            team = store.player_team(match_id, pid)
            opp = next((t for t in (m["team_a"], m["team_b"]) if t != team), "")
            target = Target(match_date, group, m["venue"] or "", opp, team == m.get("batting_first"))
            f, trust = compute_factors_with_trust(target, _records(same), _records(other), venue_type, cfg,
                                                  pre_toss=(run_type == "pre_toss"))
            base = sum(choice.weights[k] * f[k] for k in FACTORS)
            wtrust = sum(choice.weights[k] * trust[k] for k in FACTORS)
            thin = wtrust < threshold or choice.borrowed_from is not None
            players.append(PlayerScore(pid, base, f, trust, choice.weights, 1, None, thin, prov))

        step = "save"
        data_stale = bool(client and client.data_stale)
        if client is not None:
            warnings += [w for w in client.warnings if w not in warnings]
        for p in players:
            store.save_prediction(run_id, {
                "player_id": p.player_id, "factors": p.factors, "trust": p.trust,
                "fallback_step": p.fallback_step, "fallback_note": p.fallback_note, "thin_data": p.thin_data,
                "provisional_inputs": p.provisional_inputs, "provisional_weights": choice.provisional,
                "borrowed_from_group": choice.borrowed_from, "base_score": p.base_score})
        store.finish_run(run_id, "done", None, None, version_id, data_stale)
        players.sort(key=lambda p: (-(p.base_score if p.base_score is not None else float("-inf")), p.player_id))
        return ScoreResult(run_id, match_id, group, run_type, version_id, choice.provisional,
                           choice.borrowed_from, data_stale, players, list(unmatched_names or []), warnings)
    except Exception as e:
        store.finish_run(run_id, "failed", step, str(e), version_id, data_stale)
        raise ScoringFailed(step, str(e), run_id) from e
