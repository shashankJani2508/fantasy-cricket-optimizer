"""Backtest: replay past matches in date order, predict Dream11 points from earlier matches only,
fit factor weights per format group, and save rubric v1 to Neon plus backtest_report.md.

Run from the backtest folder:
    python -m backtest.run_backtest            # writes to Neon (needs DATABASE_URL)
    python -m backtest.run_backtest --no-db    # writes CSVs to output/ instead
No AI APIs are used.
"""
import argparse
import collections
import csv
import datetime as dt
import itertools
import json
import os
import sys
from pathlib import Path

import numpy as np
import yaml

from backtest.download import ensure_data
from backtest.fit import fit_group
from backtest.parse import load_matches
from engine.factors import FACTORS, Record, Target, VenueBook, compute_factors
from engine.points import PointsConfigError, load_points_config, player_points

ROOT = Path(__file__).resolve().parent.parent


def months_before(date, months):
    y, m = date.year, date.month - months
    while m <= 0:
        m += 12
        y -= 1
    return date.replace(year=y, month=m, day=min(date.day, 28))


def replay(matches, points_of, cfg, eval_start):
    """Walk matches in date order. Factors for a match are computed before ANY match on that
    date is added to history, so a match never sees itself or anything on the same day.

    Returns (prediction rows, points rows, counters)."""
    hist = collections.defaultdict(list)        # (player, group)  -> [Record]
    gender_hist = collections.defaultdict(list)  # (player, gender) -> [Record], all groups
    books = {}
    rows, points_rows = [], []
    counts = {"cold_start": collections.Counter(), "retired_hurt": collections.Counter(),
              "warmup_rows": collections.Counter()}
    for date, day in itertools.groupby(matches, key=lambda m: m.date):
        day = list(day)
        pending = []
        for m in day:
            book = books.setdefault(m.group, VenueBook(cfg["pitch_min_matches"]))
            cache = {}

            def venue_type(v, book=book, date=m.date, cache=cache):
                if v not in cache:
                    cache[v] = book.classify(v, date)
                return cache[v]

            for pid, pm in m.players.items():
                if pm.retired_hurt:
                    counts["retired_hurt"][m.group] += 1
                    continue
                pts = points_of(m, pm)
                points_rows.append({"match_id": m.match_id, "match_date": m.date, "format_group": m.group,
                                    "player_id": pid, "player_name": pm.name, "team": pm.team, **pts})
                batted_first = pm.team == m.batted_first
                pending.append((pid, m, Record(m.date, m.group, m.venue, pm.opponent, batted_first,
                                               pm.bat_band, pm.bowl_band, pts["total"])))
                if m.date < eval_start:
                    counts["warmup_rows"][m.group] += 1
                    continue
                h = hist[(pid, m.group)]
                if len(h) < cfg["cold_start_min_matches"]:
                    counts["cold_start"][m.group] += 1
                    continue
                other = [r for r in gender_hist[(pid, m.gender)] if r.group != m.group]
                target = Target(m.date, m.group, m.venue, pm.opponent, batted_first)
                f, n = compute_factors(target, h, other, venue_type, cfg)
                rows.append({"match_id": m.match_id, "match_date": m.date, "format_group": m.group,
                             "player_id": pid, "player_name": pm.name, "factors": f, "n": n,
                             "actual": pts["total"]})
        for pid, m, rec in pending:
            hist[(pid, m.group)].append(rec)
            gender_hist[(pid, m.gender)].append(rec)
        for m in day:
            books[m.group].add(m.date, m.venue, m.first_innings_total)
    return rows, points_rows, counts


def split_rows(rows, fit_fraction):
    """Chronological split by match: the older fit_fraction of matches are fit, the rest test."""
    match_ids = sorted({(r["match_date"], r["match_id"]) for r in rows})
    cut = int(round(len(match_ids) * fit_fraction))
    fit_ids = {mid for _, mid in match_ids[:cut]}
    for r in rows:
        r["split"] = "fit" if r["match_id"] in fit_ids else "test"
    return len(match_ids), cut


# ---------------------------------------------------------------- output

DDL = """
CREATE TABLE IF NOT EXISTS bt_player_match_points (
  match_id text, match_date date, format_group text, player_id text, player_name text, team text,
  batting real, bowling real, fielding real, playing_xi real, total real,
  PRIMARY KEY (match_id, player_id));
CREATE TABLE IF NOT EXISTS bt_predictions (
  rubric_version text, match_id text, match_date date, format_group text, player_id text,
  player_name text, form real, venue real, opponent real, current_touch real, opportunity real,
  career real, bat_first_or_chase real, pitch_type real, predicted real, actual real, error real,
  is_real_miss boolean, split text, PRIMARY KEY (rubric_version, match_id, player_id));
CREATE TABLE IF NOT EXISTS rubric_versions (
  id serial PRIMARY KEY, version text NOT NULL, format_group text NOT NULL, weights jsonb NOT NULL,
  thin_data_threshold integer NOT NULL, test_mae real, baseline_mae real,
  created_at timestamptz NOT NULL DEFAULT now(), approved_by text NULL,
  UNIQUE (version, format_group));
"""
POINT_COLS = ["match_id", "match_date", "format_group", "player_id", "player_name", "team",
              "batting", "bowling", "fielding", "playing_xi", "total"]
PRED_COLS = ["rubric_version", "match_id", "match_date", "format_group", "player_id", "player_name",
             *FACTORS, "predicted", "actual", "error", "is_real_miss", "split"]


def check_db(url):
    import psycopg
    with psycopg.connect(url, connect_timeout=15) as conn:
        conn.execute("SELECT 1")


def write_db(url, points_rows, pred_rows, rubric_rows):
    import psycopg
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("DELETE FROM bt_player_match_points")
            cur.execute("DELETE FROM bt_predictions WHERE rubric_version = 'v1'")
            cur.execute("DELETE FROM rubric_versions WHERE version = 'v1' AND approved_by IS NULL")
            with cur.copy(f"COPY bt_player_match_points ({', '.join(POINT_COLS)}) FROM STDIN") as cp:
                for r in points_rows:
                    cp.write_row([r[c] for c in POINT_COLS])
            with cur.copy(f"COPY bt_predictions ({', '.join(PRED_COLS)}) FROM STDIN") as cp:
                for r in pred_rows:
                    cp.write_row([r[c] for c in PRED_COLS])
            for r in rubric_rows:
                cur.execute(
                    "INSERT INTO rubric_versions (version, format_group, weights, thin_data_threshold,"
                    " test_mae, baseline_mae, approved_by) VALUES (%s, %s, %s, %s, %s, %s, NULL)",
                    (r["version"], r["format_group"], json.dumps(r["weights"]), r["thin_data_threshold"],
                     r["test_mae"], r["baseline_mae"]))
        conn.commit()


def write_csv(out_dir, points_rows, pred_rows, rubric_rows):
    out_dir.mkdir(exist_ok=True)
    for name, cols, rows in (("bt_player_match_points", POINT_COLS, points_rows),
                             ("bt_predictions", PRED_COLS, pred_rows)):
        with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    (out_dir / "rubric_versions.json").write_text(json.dumps(rubric_rows, indent=2), encoding="utf8")


# ---------------------------------------------------------------- report

NOT_DERIVABLE = [
    ("Run out: direct hit vs not direct", "Cricsheet lists the fielders involved but not whether the "
     "throw hit the stumps directly. One fielder listed = direct hit; two or more = each fielder gets "
     "the non-direct value. Approximate."),
    ("Duck and strike-rate points for bowlers", "Dream11 does not apply these to players listed as "
     "bowlers, but Cricsheet has no player roles. Applied to every player. Approximate."),
    ("Playing XI points for substitutes", "Everyone in Cricsheet `info.players` gets the playing-XI "
     "value. Impact players and concussion substitutes are listed inconsistently; substitute fielders "
     "who are not listed get nothing (including their catches)."),
    ("Dot balls", "Counted as a legal delivery (no wide or no-ball) with zero total runs, so a leg-bye "
     "off a legal ball is not a dot. Dream11's exact definition may differ."),
    ("Maidens", "An over counts as a maiden only if one bowler bowled all 6 legal balls and conceded 0 "
     "(byes and leg-byes are not charged to the bowler). Mid-over bowler changes cannot earn a maiden."),
    ("Captain and vice-captain multipliers", "There were no fantasy teams in past matches, so the "
     "multipliers are required in the config but not applied. Predictions are base points."),
    ("Super overs", "Excluded from all points, consistent with Dream11."),
    ("Bowlers injured mid-match", "Cricsheet has no field for this, so these rows cannot be detected "
     "or excluded."),
]


def fmt_mae(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"


def write_report(path, ctx):
    L = []
    a = L.append
    a("# Backtest report: rubric v1\n")
    a(f"Generated {ctx['generated']}. Window: {ctx['start']} to {ctx['today']}. Warm-up (history "
      f"only, not evaluated): {ctx['start']} to {ctx['eval_start']}. Latest match in the data: "
      f"{ctx['max_date']}. No AI API was used.\n")
    a("## Match-type mapping\n")
    a("| Cricsheet match_type | Gender | Group | Matches in window |\n|---|---|---|---|")
    for (mt, g), c in sorted(ctx["type_counts"].items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        a(f"| {mt} | {g} | {ctx['cfg']['match_type_map'].get(mt, 'not mapped (excluded)')} | {c} |")
    a("\nFranchise and domestic matches (e.g. IPL, BBL) are included in T20, because Dream11 scores "
      "them.\n")
    a("## Exclusions\n")
    a("Match-level rule, applied in this order:\n")
    a("1. `info.balls_per_over` is not 6 (The Hundred uses 5-ball overs, which are not a Dream11 T20 format).")
    a("2. `info.outcome.result` is `no result`.")
    a("3. `info.outcome.method` is present (D/L, VJD, awarded, or a tie decided by a method).")
    a("4. Reduced overs: `info.overs` is below the standard (20 for T20, 50 for ODI), or any non-super-over "
      "innings has `target.overs` below the standard.")
    a("5. No ball-by-ball data.\n")
    a("Draws (Tests) and ties are kept. Player rows are excluded when the player was retired hurt "
      "(`wickets[].kind == 'retired hurt'`). Their points are not used as history either.\n")
    a("| Reason | Matches excluded |\n|---|---|")
    for r, c in ctx["excluded"].most_common():
        a(f"| {r} | {c} |")
    a("\n## Data coverage, cold start and accuracy per group\n")
    a("| Group | Matches kept | Evaluated matches | Fit / test matches | Evaluated rows | Warm-up rows | "
      "Cold-start rows excluded | Retired-hurt rows | Form-only test MAE | Rubric test MAE | Beats baseline | Reliable |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for g, s in sorted(ctx["groups"].items()):
        r = s.get("result")
        beats = "n/a" if not r else ("yes" if r["test_mae"] < r["baseline_test_mae"] else "NO")
        a(f"| {g} | {s['matches']} | {s['eval_matches']} | {s['fit_matches']} / {s['test_matches']} | "
          f"{s['rows']} | {s['warmup_rows']} | {s['cold_start']} | {s['retired_hurt']} | "
          f"{fmt_mae(r and r['baseline_test_mae'])} | {fmt_mae(r and r['test_mae'])} | {beats} | "
          f"{'yes' if s['reliable'] else '**NO, too few matches**'} |")
    a("\nCold start: players with fewer than "
      f"{ctx['cfg']['cold_start_min_matches']} earlier matches in the group are excluded from fitting "
      "and evaluation. The counts above are rows in the evaluation period.\n")
    a("## Final weights (rubric v1)\n")
    a("| Group | " + " | ".join(FACTORS) + " | Dropped by ablation |\n|---|" + "---|" * (len(FACTORS) + 1))
    for g, s in sorted(ctx["groups"].items()):
        r = s.get("result")
        if not r:
            a(f"| {g} | " + " | ".join("-" for _ in FACTORS) + " | not fitted |")
            continue
        a(f"| {g} | " + " | ".join(f"{r['final_weights'][f]:.2f}" for f in FACTORS) +
          f" | {', '.join(r['dropped']) or 'none'} |")
    a("\n### Ablation detail (test MAE when refitted without each factor)\n")
    for g, s in sorted(ctx["groups"].items()):
        r = s.get("result")
        if not r:
            continue
        a(f"- **{g}**: full rubric {fmt_mae(r['full_test_mae'])}; " +
          ", ".join(f"without {f} {fmt_mae(m)}" for f, m in r["ablation_test_mae"].items()))
    flagged = [g for g, s in ctx["groups"].items() if not s["reliable"]]
    a("\n## Groups with unreliable weights\n")
    if flagged:
        a(f"These groups have fewer than {ctx['cfg']['min_reliable_matches']} evaluated matches, so their "
          "weights should not be trusted (expect Tests and women's formats): " + ", ".join(sorted(flagged)) + ".")
    else:
        a("None.")
    a("\n## Dream11 point types not exactly derivable from Cricsheet\n")
    a("| Point type | How it was handled |\n|---|---|")
    for p, h in NOT_DERIVABLE:
        a(f"| {p} | {h} |")
    a("\n## Method notes and limitations\n")
    a("- Factors use only matches dated strictly before the match being predicted, within the 3-year "
      "window and the same group (format x gender). current_touch uses the same gender's other formats. "
      "Matches on the same date never see each other (Cricsheet gives dates, not start times). This is "
      "covered by `tests/test_no_peeking.py`.")
    a("- Weights minimise MAE with weights >= 0 summing to 1: an exact linear programme (HiGHS) for groups "
      "up to 20,000 fit rows, and SLSQP for larger groups (T20 men, T20 women), where the exact solver "
      "was too slow. They are then rounded to 0.05 and renormalised, so they may not be exact multiples "
      "of 0.05.")
    a("- Dream11 point values are PROVISIONAL. dream11.com's points pages were down, so they come from "
      "Dream11's older static points page, with gaps filled from a 2021 Sportskeeda guide. Rows neither "
      "source listed (dot balls, the LBW/bowled bonus) are 0. Each value's source is noted in "
      "config/dream11_points.yaml. Update the values from the Dream11 app and rerun.")
    a("- The ablation decision uses the test set, as specified, so the final test MAE is slightly "
      "optimistic. A future refresh should confirm it on newer matches.")
    a("- Batting position = order of first appearance at the crease. Players who did not bat are in "
      "band 8+. Tests have no bowling quota, so the bowling band uses the most overs bowled in one "
      f"innings: under {ctx['cfg']['test_bowling_split']} overs or {ctx['cfg']['test_bowling_split']}+. "
      "ODM is mapped to ODI and MDM to Test.")
    a("- Venue names are normalised by dropping any \", city\" suffix. Ground renames are not merged.")
    a("- current_touch only uses another format whose average is positive and backed by at least "
      f"{ctx['cfg']['cold_start_min_matches']} matches; otherwise that match is skipped.")
    a("- bat_first_or_chase uses the actual toss outcome: the backtest represents the post-toss run.")
    a("- Not tested here: Gemini/news inputs (past news cannot be recreated) and the team optimizer "
      "(past credit prices are unavailable).")
    a("- Bowlers injured mid-match cannot be detected from Cricsheet.")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf8")


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db", action="store_true", help="write CSVs to output/ instead of Neon")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load((ROOT / "config" / "backtest.yaml").read_text(encoding="utf8"))
    try:
        points_cfg = load_points_config(ROOT / "config" / "dream11_points.yaml")
    except PointsConfigError as e:
        print(f"REFUSING TO RUN: {e}", file=sys.stderr)
        return 2

    db_url = os.environ.get("DATABASE_URL")
    env_file = ROOT / ".env"
    if not db_url and env_file.exists():
        for line in env_file.read_text(encoding="utf8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                db_url = line.split("=", 1)[1].strip().strip('"').strip("'") or None
    if not args.no_db:
        if not db_url:
            print("REFUSING TO RUN: DATABASE_URL is not set (or pass --no-db).", file=sys.stderr)
            return 2
        check_db(db_url)

    today = dt.date.fromisoformat(cfg["today"]) if cfg.get("today") else dt.date.today()
    start = months_before(today, 12 * cfg["window_years"])
    eval_start = months_before(today, 12 * cfg["window_years"] - cfg["warmup_months"])
    print(f"[run] window {start} .. {today}; evaluation from {eval_start}")
    print("[run] match-type mapping:", ", ".join(f"{k} -> {v}" for k, v in cfg["match_type_map"].items()))

    raw_dir = ensure_data(ROOT / "data")
    matches, excluded, type_counts = load_matches(raw_dir, cfg, start.isoformat(), today.isoformat())
    print(f"[run] {len(matches)} matches kept; excluded: {dict(excluded)}")

    rows, points_rows, counts = replay(
        matches, lambda m, pm: player_points(pm.stats, m.fmt, points_cfg), cfg, eval_start.isoformat())
    print(f"[run] {len(rows)} evaluated player-match rows")

    groups = {}
    pred_rows, rubric_rows = [], []
    by_group = collections.defaultdict(list)
    for r in rows:
        by_group[r["format_group"]].append(r)
    match_count = collections.Counter(m.group for m in matches)
    for g in sorted(set(match_count) | set(by_group)):
        grows = by_group.get(g, [])
        n_eval, n_fit = split_rows(grows, cfg["fit_fraction"]) if grows else (0, 0)
        s = {"matches": match_count[g], "eval_matches": n_eval, "fit_matches": n_fit,
             "test_matches": n_eval - n_fit, "rows": len(grows), "warmup_rows": counts["warmup_rows"][g],
             "cold_start": counts["cold_start"][g], "retired_hurt": counts["retired_hurt"][g],
             "reliable": n_eval >= cfg["min_reliable_matches"]}
        groups[g] = s
        fit = [r for r in grows if r["split"] == "fit"]
        test = [r for r in grows if r["split"] == "test"]
        if not fit or not test:
            print(f"[fit] {g}: not enough evaluated matches to fit")
            continue
        X = lambda rs: np.array([[r["factors"][f] for f in FACTORS] for r in rs], dtype=float)
        y = lambda rs: np.array([r["actual"] for r in rs], dtype=float)
        res = fit_group(X(fit), y(fit), X(test), y(test), cfg["weight_step"])
        s["result"] = res
        print(f"[fit] {g}: test MAE {res['test_mae']:.2f} vs form-only {res['baseline_test_mae']:.2f}; "
              f"dropped {res['dropped']}")
        w = res["final_vec"]
        for r in grows:
            pred = float(np.dot(w, [r["factors"][f] for f in FACTORS]))
            err = r["actual"] - pred
            pred_rows.append({"rubric_version": "v1", "match_id": r["match_id"], "match_date": r["match_date"],
                              "format_group": g, "player_id": r["player_id"], "player_name": r["player_name"],
                              **{f: r["factors"][f] for f in FACTORS}, "predicted": pred,
                              "actual": r["actual"], "error": err,
                              "is_real_miss": abs(err) > cfg["real_miss_abs"] or abs(err) > cfg["real_miss_rel"] * pred,
                              "split": r["split"]})
        rubric_rows.append({"version": "v1", "format_group": g, "weights": res["final_weights"],
                            "thin_data_threshold": cfg["thin_data_threshold"],
                            "test_mae": res["test_mae"], "baseline_mae": res["baseline_test_mae"]})

    if args.no_db:
        write_csv(ROOT / "output", points_rows, pred_rows, rubric_rows)
        print(f"[out] CSVs written to {ROOT / 'output'}")
    else:
        write_db(db_url, points_rows, pred_rows, rubric_rows)
        print(f"[out] Neon: {len(points_rows)} points rows, {len(pred_rows)} predictions, "
              f"{len(rubric_rows)} rubric rows")

    write_report(ROOT / "backtest_report.md", {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "start": start, "today": today,
        "eval_start": eval_start, "max_date": max((m.date for m in matches), default="n/a"),
        "type_counts": type_counts, "excluded": excluded, "groups": groups, "cfg": cfg})
    print(f"[out] report written to {ROOT / 'backtest_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
