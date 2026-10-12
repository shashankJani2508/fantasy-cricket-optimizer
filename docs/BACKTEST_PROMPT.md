# Backtest Prompt (updated)

## Run 2 (do this next): changes after run 1

Run 1 (report dated 12 Oct 2026) worked, but its results cannot go live. Rerun with these changes:

1. **Real Dream11 point values.** Run 1 used provisional values (Dream11's older static page plus a 2021 Sportskeeda guide; dot balls and the LBW/bowled bonus set to 0). We will fill `config/dream11_points.yaml` from the Dream11 app. Mark every value's source as `dream11_app`. Refuse to run if any value still comes from another source. Set `rubric_versions.points_values_final = true` only when all values come from the app.
2. **Honest validation.** Split each group's evaluated matches chronologically **60% fit / 20% validation / 20% test**. Fit weights on fit; run ablation and choose factors on **validation**; report the final error on **test** only once. Run 1 used the test set for ablation, so its test error was slightly optimistic.
3. **Items run 1 did not produce** (items 13, 15, 16, 17, 18 below): the 50/50 benchmark, `format_scaling`, `debutant_averages`, flag-rule calibration, and the bowling-style check.
4. **Real-miss calibration.** The real-miss rule is now relative: a real miss is an error larger than `real_miss_mae_multiplier` (default 1.5) × the group's test MAE. Report, per group, what share of predictions count as real misses at multipliers 1.25, 1.5 and 2.0, and how often the flag rule (last 10 matches, 10+ real misses, 70%+ same direction) fires at each. Recommend the multiplier and the 70% value that keep false flags rare (a flagged group's direction should usually persist over the following 10 matches).
5. **Unreliable groups.** A group with fewer than 100 evaluated matches is marked `reliable = false` and borrows the same format's other-gender weights (`borrowed_from_group`). Test women borrows Test men.
6. **Form check.** Run 1 gave form a weight of 0 in every reliable group, with career at 0.62 to 1.00. Report the correlation between form and career per group, and the validation MAE of (a) the fitted weights, (b) career only, (c) form only, (d) 50/50. This tells us whether form truly adds nothing or is just overlapping with career.
7. **Keep run 1** in `rubric_versions` with `is_active = false` and run label `run1_provisional`, for comparison.
8. **Report additions:** a one-paragraph plain-English summary at the top ("what the weights mean for Aryan"), and a run 1 vs run 2 comparison table.

9. **Don't break run 1.** Before changing anything: commit the current state, run the existing tests (including `tests/test_no_peeking.py`) and confirm they pass. Make run 2 changes as small, separate commits. Run the tests after each. If a passing test starts failing, stop and report.
10. **Table renames:** migrate `bt_player_match_points` → `player_match_points` (`source = 'cricsheet'`) and `bt_predictions` → `backtest_predictions` with a migration that copies the data and checks row counts. Update code references in the same commit. Keep the old tables until we confirm; never drop them without a yes.
11. **No invented values or fields.** If something needed for run 2 is missing (a points value, a Cricsheet field, a bowling-style source), stop and ask rather than fill it in.

Everything below still applies, with the split in step 10 replaced by the 60/20/20 split above.

---

Read `CLAUDE.md`, `RUBRIC.md`, `NEON_SCHEMA.md` and `BACKTEST_MAP.md` first. This prompt replaces the earlier backtest prompt. If you have already started, apply the changes marked **(new)** and the table renames.

---

You are building the one-off backtest for "Fantasy Cricket Match Day Optimizer". It lives in `/backtest`, separate from the live app, and **imports** the shared modules in `/engine` (`points.py`, `factors.py`); it never duplicates them. It uses no AI API.

## Goal

Replay past matches in date order. For each match, predict every player's Dream11 points using only data from before that match, compare with actual points, and find the factor weights that predict best. Save rubric v1 and supporting tables to Neon, and write `backtest_report.md`.

## The live engine is separate (new)

The live scoring engine (`SCORING_ENGINE.md`) runs per match inside the app. The backtest runs once before launch and again when we refresh weights. They share **only** `/engine/points.py` and `/engine/factors.py`, so factors are computed identically in both. Do not put backtest-only logic in `/engine`.

## Data

1. Download Cricsheet ball-by-ball JSON for all formats from cricsheet.org; cache in `/backtest/data`; never re-download if present.
2. Format groups: T20 (incl. T20 internationals), ODI, Test, each split men's and women's (Cricsheet `gender`). Print the match-type mapping used.
3. Last 3 years from today; the first 6 months are warm-up (used for factors, not evaluated).

## Dream11 points (do not guess)

4. Read `config/dream11_points.yaml` (one section per format). Refuse to run while any value is null and print which are missing. Never fill values from memory.
5. List every point type that cannot be derived exactly from Cricsheet (e.g. direct-hit run-outs) and how it was handled.
6. Compute batting, bowling, fielding and total points for every player in every match via `engine/points.py`. Write to **`player_match_points`** with `source = 'cricsheet'`, `is_provisional = false`.

## Factors and rules

7. The 8 factors, thin-data rule, cold start and exclusions exactly as in `RUBRIC.md` sections 3 and 5 (cold start: fewer than 3 earlier matches in the group → excluded and counted). Factors only see matches dated strictly before the match (unit test required).
8. Exclusions: rain-shortened / reduced-overs / DLS matches and no-results (document the detection rule); player rows with a "retired hurt" dismissal. Note that bowlers injured mid-match cannot be detected.
9. Venue pitch types: compute and store in `venue_pitch_types` (min 5 earlier matches, from settings).

## Fitting

10. Per format group: chronological split of evaluated matches, older 70% fit, newer 30% test.
11. Fit weights minimising mean absolute error, weights ≥ 0 and summing to 1 (e.g. SLSQP). Round to 0.05 and renormalise.
12. Ablation: refit without each factor; if test MAE is not worse without it, set its weight to 0.
13. Benchmarks on the test set:
    - Form only.
    - **(new)** Fixed 50/50 blend: 0.5 × average of recent factors (form, current touch) + 0.5 × average of past factors (career, venue, opponent). If the fitted weights don't beat it, save the 50/50 blend as the active v1 with `source = 'benchmark_50_50'` and say so in the report.
14. Flag groups with too few matches for reliable weights.

## Extra outputs for the live engine (new)

15. **Format scaling:** from players who played in two format groups, the typical ratio of their average points between each pair. Save to `format_scaling` with `players_n`.
16. **Debutant averages:** per format group, the average points of players in their first 3 matches. Save to `debutant_averages`.
17. **Flag-rule false alarms:** on the test period, apply the learning flag rule (`RUBRIC.md` section 9: last 10 matches, 10+ real misses, 70%+ same direction) to every group. Report how often groups get flagged, and how often a flagged group's direction reverses in the following 10 matches (a sign of false alarms). Recommend whether 70% should be raised.
18. **(optional, check first)** Bowling styles: look for a source that maps Cricsheet players to bowling styles (for example, the `cricketdata` R package's `player_meta` dataset, which combines Cricsheet and ESPNcricinfo player attributes). If one exists and covers most players, store styles in `players.bowling_style` and report coverage. Do not add pace vs spin to the rubric; just report.

## Outputs

- **`player_match_points`** (source `cricsheet`)
- **`backtest_predictions`**: match, player, format group, factor values, predicted, actual, error, `is_real_miss` (|error| > 15 or > 40% of predicted), split, run label
- **`rubric_versions`**: version 1 per format group, weights, thin-data threshold 10, test MAE, baseline MAE, `source = 'backtest'` (or `benchmark_50_50`), `is_active = true`, `approved_by = NULL`
- **`format_scaling`**, **`debutant_averages`**, **`venue_pitch_types`**
- **`backtest_report.md`**: coverage per group, mapping, exclusions, cold-start counts, MAE vs both benchmarks, final weights, dropped factors, scaling ratios, debutant averages, flag-rule false-alarm analysis, bowling-style coverage (if checked), limitations

Connection string from `DATABASE_URL`; never hardcode.

Before writing code, show the plan and the Cricsheet fields you will use for each factor and exclusion, and wait for the go-ahead.
