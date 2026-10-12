# Rubric (the marking scheme)

The rubric tells the scoring engine how to predict each player's Dream11 points before a match. It is **ours**: we wrote it, the backtest sets its starting weights, and the learning loop improves them with Aryan's approval.

It is **not** Dream11's points system. Dream11's points table decides *actual* points after a match and cannot be changed by us. The rubric *predicts* those points.

| | Dream11's points table | Our rubric |
|---|---|---|
| Owner | Dream11 | Us (changes approved by Aryan) |
| Job | Awards actual points after the match | Predicts points before the match |
| Stored in | `dream11_points_table` (copied from the app) | `rubric_versions` |

---

## 1. Scope

- **All formats**, each with its own settings: T20, ODI, Test (T10 only if we add its points table).
- **Men's and women's** kept separate.
- A **format group** = format × gender (e.g. "T20 men"). Every number below is kept per format group.

---

## 2. What is predicted

**Expected Dream11 points** for each allowed player = batting + bowling + fielding, in Dream11's points for that format. Captain (2x) and vice-captain (1.5x) are applied by the optimizer, not here.

History is converted to Dream11 points with the shared `engine/points.py`, using Dream11's points table from settings.

---

## 3. The 8 factors

Each factor is "the player's average Dream11 points in situation X", using only matches **in the same format group** and **dated before** the match being predicted.

| # | Factor | Definition | Thin-data rule |
|---|---|---|---|
| 1 | **Form** | Last 10 matches, any competition; the most recent 5 count double | No (it is the fallback) |
| 2 | **Venue** | Average at this venue | Yes |
| 3 | **Opponent** | Average against this opposing team | Yes |
| 4 | **Current touch** | His last 5 matches in **other** formats, only if played in the last 30 days. For each: ratio = points ÷ his average in that format. Value = form × average ratio. None qualify → form | No |
| 5 | **Opportunity** | Average in matches where his batting band (1–3, 4–5, 6–7, 8+) **and** bowling band (did not bowl / under half the maximum quota / half or more) match his usual bands (most frequent in his last 10) | Yes |
| 6 | **Career** | Average over all earlier matches in the data window | No |
| 7 | **Batting first or chasing** | Average when his team batted first vs chased, matching today's situation. **Post-toss only**; before the toss its value = form (neutral) | Yes |
| 8 | **Pitch type** | Venue classed batting-friendly or bowling-friendly by its average first-innings score in earlier matches vs the format average (needs 5+ earlier matches at the venue, else "unknown" → value = form). Factor = his average at venues of the same type. Pace vs spin is added only if a bowling-style data source is found | Yes |

Left out of version 1 (can be tested in a later backtest): home vs away, day vs night.

**Implementation details confirmed by backtest run 1:**
- Batting position = order of first appearance at the crease; players who did not bat are in band 8+.
- Tests have no bowling quota: bowling band uses the most overs bowled in one innings (under 20 / 20+).
- Current touch only uses another format where the player's average is positive and backed by at least 3 matches.
- Matches on the same date never see each other (Cricsheet gives dates, not start times).
- Venue names are normalised by dropping a ", city" suffix; ground renames are not merged.
- Cricsheet match types: IT20 and T20 → T20 (franchise and domestic included); ODI and ODM → ODI; Test and MDM → Test.
- **Excluded formats:** The Hundred (5-ball overs) is not a T20 and is not supported.

---

## 4. How factors combine

**Weighted average:**

```
base_score = Σ (weight_i × factor_value_i)      weights ≥ 0, Σ weights = 1
```

Weights are set per format group (section 7).

---

## 5. Thin-data rule

Applies to venue, opponent, opportunity, batting first or chasing, and pitch type.

```
trust = min(n / 10, 1)                 n = matches behind that factor
value = trust × factor_average + (1 − trust) × form
n = 0  →  value = form
```

Example: 2 matches at a venue averaging 90, form 40 → trust 0.2 → value = 0.2 × 90 + 0.8 × 40 = 50.

---

## 6. Players with little history (fallback chain)

Used when a player has fewer than 3 matches in the format group. Steps 2 to 4 always set the **thin-data** flag.

| Step | When | Value |
|---|---|---|
| 1 | 3+ matches in this format group | Normal: 8 factors |
| 2 | Under 3, but history in other formats | His other-format average × format scaling ratio (measured by the backtest from players who played both; table `format_scaling`) |
| 3 | No Cricsheet history at all | CricketData.org career stats converted to a rough points estimate |
| 4 | Nothing anywhere | Historical debutant average for this format group (table `debutant_averages`) |

---

## 7. Weights

- **Rubric v1 weights come from the backtest**, per format group (`BACKTEST_PROMPT.md`).
- A factor that doesn't improve accuracy gets weight 0.
- The rubric must beat two benchmarks: "form only" and a fixed 50/50 blend of recent (form, current touch) and past (career, venue, opponent). If it doesn't beat the 50/50 blend, the 50/50 blend is used.

### Backtest run 1 results (12 Oct 2026, PROVISIONAL)

Window 12 Oct 2023 to 12 Oct 2026 (first 6 months warm-up). Points were calculated with **provisional Dream11 values** (Dream11's older points page plus a 2021 guide, because dream11.com's points pages were down); dot balls and the LBW/bowled bonus were set to 0. **These weights must not go live until the backtest is rerun with values copied from the Dream11 app** (section 7.2).

| Format group | Form | Venue | Opponent | Current touch | Opportunity | Career | Bat first / chase | Pitch type | Form-only MAE | Rubric MAE | Reliable |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T20 men | 0.00 | 0.14 | 0.05 | 0.05 | 0.00 | 0.76 | 0.00 | 0.00 | 25.48 | 24.97 | yes |
| T20 women | 0.00 | 0.00 | 0.29 | 0.00 | 0.00 | 0.62 | 0.10 | 0.00 | 21.79 | 21.35 | yes |
| ODI men | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 32.97 | 32.51 | yes |
| ODI women | 0.00 | 0.00 | 0.15 | 0.00 | 0.00 | 0.85 | 0.00 | 0.00 | 30.04 | 29.41 | yes |
| Test men | 0.00 | 0.00 | 0.05 | 0.05 | 0.00 | 0.90 | 0.00 | 0.00 | 43.40 | 42.73 | yes |
| Test women | 1.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 50.39 | 50.39 | **no (8 matches)** |

**What run 1 tells us:**
1. **Career average dominates** (0.62 to 1.00) and **form got 0 everywhere.** Form and career overlap heavily, and fantasy points are noisy, so the long-term average predicted slightly better. This is a data result, not a bug, but it must be confirmed with real point values and an honest validation split (7.2).
2. **The gain over "form only" is small:** about 2% in every reliable group (e.g. T20 men 25.48 → 24.97). The rubric is still the better predictor, but most of the edge will have to come from Gemini's news reading and the learning loop.
3. **Typical misses are large:** 21 to 43 points on average. A fixed "15 points or 40%" real-miss rule would mark almost every prediction a miss, so the rule is now relative to each group's typical miss (section 9).
4. **Weights at 0 are not final.** The learning loop can raise any weight (including form) by up to 0.10 per approved change, if the live evidence supports it.

### 7.1 Unreliable groups

A group with fewer than 100 evaluated matches is unreliable. It **borrows the weights of the same format's other gender** (Test women → Test men) and every prediction in it carries the thin-data flag. Stored with `rubric_versions.borrowed_from_group`.

### 7.2 Rerun required before go-live

Run 2 of the backtest (`BACKTEST_PROMPT.md`, "Run 2") must: use point values copied from the Dream11 app; split time 60% fit / 20% validation / 20% test and decide ablation on **validation** (so the reported test error is honest); and produce the items run 1 skipped (50/50 benchmark, format scaling, debutant averages, flag-rule calibration).

## 8. From scores to team (applied by other parts, listed here for completeness)

| Rule | Value |
|---|---|
| Gemini moderation | ±20% per player; only injury/fitness news, confirmed batting-order or bowling-role change, today's pitch or dew where it **differs** from venue history (no double counting); source link required; no news → no change |
| Player pool | Post-toss: confirmed XI. Pre-toss: probable XI (team's last XI in this format within 30 days), else Aryan's full Dream11 list |
| Team | Highest total expected points within Dream11 rules (settings); tie-break: fewer thin-data players |
| Captain / VC | Highest / second-highest expected points in the team; Gemini explains only |
| Contest type | Not used; always highest expected points |
| Bench | 4 highest-scoring players not picked, with the solver's real reason |
| Reasons | One line per player; 2 to 3 lines for captain and VC |

---

## 9. Learning rules

| Rule | Value |
|---|---|
| Real miss | Off by more than **1.5 × the group's typical miss** (its backtest test MAE). From run 1: T20 men about 37 points, T20 women 32, ODI men 49, ODI women 44, Test men 64. Replaces the earlier fixed "15 points or 40%", which run 1 showed would mark almost every prediction a miss. Recalibrated in run 2 |
| Groups watched | Per format group: player role, batting position band, batting first vs chasing, pitch type/venue |
| Flag | Last 10 matches of a group: at least 10 real misses, at least 70% in the same direction (70% checked by the backtest for false alarms) |
| Proposal | One factor, at most ±0.10 per change; weights renormalised to sum to 1 |
| History check | Code replays the proposal on stored predictions; "not supported by history" shown if past error wouldn't drop |
| Decision | Aryan approves, edits (warning beyond ±0.10) or rejects |
| Rollback | After a change, replay the previous weights on the next 10 matches; suggest rollback if previous was better |
| Gemini trust | If Gemini's changes made predictions worse over 20 matches, suggest lowering its cap to ±10% |
| Skipped in learning | Rain-shortened matches; players injured during the match |

---

## 10. Warnings ("check this yourself")

Raised when any of these is true: XI not confirmed; rain forecast at the venue; 3 or more picked players flagged thin data; Gemini wanted to go beyond ±20%.

---

## 11. Settings (stored in Neon `settings`, editable with the passcode, every change logged)

| Key | Default |
|---|---|
| `form_window` | 10 matches, last 5 double |
| `current_touch_window` | 5 matches within 30 days |
| `thin_data_full_trust` | 10 matches |
| `cold_start_min_matches` | 3 |
| `form_recent_double` | 5 |
| `current_touch_matches` / `current_touch_days` | 5 / 30 |
| `thin_data_trust_threshold` | 0.5 (a player is thin data if Σ weight × trust is below this, or a fallback step 2 to 4 was used, or the group borrowed weights) |
| `cricketdata_daily_limit` / `cricketdata_dev_daily_limit` / `cricketdata_max_calls_per_run` | 95 / 30 / 15 |
| `pitch_type_min_matches` | 5 |
| `probable_xi_days` | 30 |
| `gemini_cap_percent` | 20 |
| `real_miss_mae_multiplier` | 1.5 (× the group's backtest test MAE; calibrated in run 2) |
| `flag_window_matches` / `flag_min_misses` / `flag_same_direction` | 5 / 5 / 0.70 (was 10 / 10; changed 13 Oct 2026) |
| `max_weight_change` | 0.10 |
| `rollback_window_matches` | 5 |
| `gemini_trust_window_matches` | 20 |
| `bench_size` | 4 |
