# Backtest report: rubric v1

Generated 2026-10-12 13:11. Window: 2023-10-12 to 2026-10-12. Warm-up (history only, not evaluated): 2023-10-12 to 2024-04-12. Latest match in the data: 2026-10-07. No AI API was used.

## Match-type mapping

| Cricsheet match_type | Gender | Group | Matches in window |
|---|---|---|---|
| IT20 | male | T20 | 1 |
| MDM | male | Test | 672 |
| ODI | female | ODI | 222 |
| ODI | male | ODI | 323 |
| ODM | female | ODI | 188 |
| ODM | male | ODI | 550 |
| T20 | female | T20 | 1761 |
| T20 | male | T20 | 3641 |
| Test | female | Test | 8 |
| Test | male | Test | 114 |

Franchise and domestic matches (e.g. IPL, BBL) are included in T20, because Dream11 scores them.

## Exclusions

Match-level rule, applied in this order:

1. `info.balls_per_over` is not 6 (The Hundred uses 5-ball overs, which are not a Dream11 T20 format).
2. `info.outcome.result` is `no result`.
3. `info.outcome.method` is present (D/L, VJD, awarded, or a tie decided by a method).
4. Reduced overs: `info.overs` is below the standard (20 for T20, 50 for ODI), or any non-super-over innings has `target.overs` below the standard.
5. No ball-by-ball data.

Draws (Tests) and ties are kept. Player rows are excluded when the player was retired hurt (`wickets[].kind == 'retired hurt'`). Their points are not used as history either.

| Reason | Matches excluded |
|---|---|
| result by method (D/L) | 316 |
| non-6-ball overs (e.g. The Hundred) | 202 |
| reduced overs (revised target) | 180 |
| no result | 150 |
| result by method (VJD) | 2 |
| result by method (Awarded) | 2 |

## Data coverage, cold start and accuracy per group

| Group | Matches kept | Evaluated matches | Fit / test matches | Evaluated rows | Warm-up rows | Cold-start rows excluded | Retired-hurt rows | Form-only test MAE | Rubric test MAE | Beats baseline | Reliable |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ODI-female | 340 | 308 | 216 / 92 | 5784 | 596 | 1101 | 5 | 30.04 | 29.41 | yes | yes |
| ODI-male | 699 | 595 | 416 / 179 | 9794 | 1497 | 4081 | 17 | 32.97 | 32.51 | yes | yes |
| T20-female | 1533 | 1296 | 907 / 389 | 24683 | 4422 | 4597 | 32 | 21.79 | 21.35 | yes | yes |
| T20-male | 3262 | 2763 | 1934 / 829 | 53273 | 10068 | 9088 | 59 | 25.48 | 24.97 | yes | yes |
| Test-female | 8 | 2 | 1 / 1 | 28 | 66 | 82 | 0 | 50.39 | 50.39 | NO | **NO, too few matches** |
| Test-male | 786 | 689 | 482 / 207 | 13019 | 1740 | 2617 | 28 | 43.40 | 42.73 | yes | yes |

Cold start: players with fewer than 3 earlier matches in the group are excluded from fitting and evaluation. The counts above are rows in the evaluation period.

## Final weights (rubric v1)

| Group | form | venue | opponent | current_touch | opportunity | career | bat_first_or_chase | pitch_type | Dropped by ablation |
|---|---|---|---|---|---|---|---|---|---|
| ODI-female | 0.00 | 0.00 | 0.15 | 0.00 | 0.00 | 0.85 | 0.00 | 0.00 | form, venue, current_touch, opportunity, bat_first_or_chase, pitch_type |
| ODI-male | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | form, venue, opponent, current_touch, opportunity, bat_first_or_chase, pitch_type |
| T20-female | 0.00 | 0.00 | 0.29 | 0.00 | 0.00 | 0.62 | 0.10 | 0.00 | form, venue, current_touch, opportunity, pitch_type |
| T20-male | 0.00 | 0.14 | 0.05 | 0.05 | 0.00 | 0.76 | 0.00 | 0.00 | form, opportunity, bat_first_or_chase, pitch_type |
| Test-female | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | form, venue, opponent, current_touch, opportunity, career, bat_first_or_chase, pitch_type |
| Test-male | 0.00 | 0.00 | 0.05 | 0.05 | 0.00 | 0.90 | 0.00 | 0.00 | form, venue, opportunity, bat_first_or_chase, pitch_type |

### Ablation detail (test MAE when refitted without each factor)

- **ODI-female**: full rubric 29.45; without form 29.45, without venue 29.45, without opponent 29.46, without current_touch 29.41, without opportunity 29.45, without career 29.50, without bat_first_or_chase 29.45, without pitch_type 29.45
- **ODI-male**: full rubric 32.51; without form 32.51, without venue 32.51, without opponent 32.51, without current_touch 32.51, without opportunity 32.51, without career 32.73, without bat_first_or_chase 32.51, without pitch_type 32.51
- **T20-female**: full rubric 21.35; without form 21.35, without venue 21.35, without opponent 21.38, without current_touch 21.35, without opportunity 21.35, without career 21.37, without bat_first_or_chase 21.35, without pitch_type 21.35
- **T20-male**: full rubric 24.97; without form 24.97, without venue 24.97, without opponent 24.97, without current_touch 24.97, without opportunity 24.97, without career 25.03, without bat_first_or_chase 24.97, without pitch_type 24.97
- **Test-female**: full rubric 59.62; without form 59.62, without venue 59.62, without opponent 59.62, without current_touch 53.07, without opportunity 59.62, without career 59.62, without bat_first_or_chase 59.62, without pitch_type 59.62
- **Test-male**: full rubric 42.73; without form 42.73, without venue 42.73, without opponent 42.74, without current_touch 42.74, without opportunity 42.73, without career 42.89, without bat_first_or_chase 42.73, without pitch_type 42.73

## Groups with unreliable weights

These groups have fewer than 100 evaluated matches, so their weights should not be trusted (expect Tests and women's formats): Test-female.

## Dream11 point types not exactly derivable from Cricsheet

| Point type | How it was handled |
|---|---|
| Run out: direct hit vs not direct | Cricsheet lists the fielders involved but not whether the throw hit the stumps directly. One fielder listed = direct hit; two or more = each fielder gets the non-direct value. Approximate. |
| Duck and strike-rate points for bowlers | Dream11 does not apply these to players listed as bowlers, but Cricsheet has no player roles. Applied to every player. Approximate. |
| Playing XI points for substitutes | Everyone in Cricsheet `info.players` gets the playing-XI value. Impact players and concussion substitutes are listed inconsistently; substitute fielders who are not listed get nothing (including their catches). |
| Dot balls | Counted as a legal delivery (no wide or no-ball) with zero total runs, so a leg-bye off a legal ball is not a dot. Dream11's exact definition may differ. |
| Maidens | An over counts as a maiden only if one bowler bowled all 6 legal balls and conceded 0 (byes and leg-byes are not charged to the bowler). Mid-over bowler changes cannot earn a maiden. |
| Captain and vice-captain multipliers | There were no fantasy teams in past matches, so the multipliers are required in the config but not applied. Predictions are base points. |
| Super overs | Excluded from all points, consistent with Dream11. |
| Bowlers injured mid-match | Cricsheet has no field for this, so these rows cannot be detected or excluded. |

## Method notes and limitations

- Factors use only matches dated strictly before the match being predicted, within the 3-year window and the same group (format x gender). current_touch uses the same gender's other formats. Matches on the same date never see each other (Cricsheet gives dates, not start times). This is covered by `tests/test_no_peeking.py`.
- Weights minimise MAE with weights >= 0 summing to 1: an exact linear programme (HiGHS) for groups up to 20,000 fit rows, and SLSQP for larger groups (T20 men, T20 women), where the exact solver was too slow. They are then rounded to 0.05 and renormalised, so they may not be exact multiples of 0.05.
- Dream11 point values are PROVISIONAL. dream11.com's points pages were down, so they come from Dream11's older static points page, with gaps filled from a 2021 Sportskeeda guide. Rows neither source listed (dot balls, the LBW/bowled bonus) are 0. Each value's source is noted in config/dream11_points.yaml. Update the values from the Dream11 app and rerun.
- The ablation decision uses the test set, as specified, so the final test MAE is slightly optimistic. A future refresh should confirm it on newer matches.
- Batting position = order of first appearance at the crease. Players who did not bat are in band 8+. Tests have no bowling quota, so the bowling band uses the most overs bowled in one innings: under 20 overs or 20+. ODM is mapped to ODI and MDM to Test.
- Venue names are normalised by dropping any ", city" suffix. Ground renames are not merged.
- current_touch only uses another format whose average is positive and backed by at least 3 matches; otherwise that match is skipped.
- bat_first_or_chase uses the actual toss outcome: the backtest represents the post-toss run.
- Not tested here: Gemini/news inputs (past news cannot be recreated) and the team optimizer (past credit prices are unavailable).
- Bowlers injured mid-match cannot be detected from Cricsheet.
