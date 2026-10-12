# Neon Schema

The single source of truth for table and column names. Where another spec uses a different name (e.g. `bt_player_match_points`, `bt_predictions`), **this file wins**: the backtest writes `player_match_points` (with `source = 'cricsheet'`) and `backtest_predictions`.

Already created by the scoring engine build (migrations 001 to 004): the reference, match, data, settings, `runs` and `predictions` tables. Later phases add the rest with new migrations; check what exists before migrating.

Conventions: `id` is a UUID primary key unless stated; timestamps are `timestamptz`; JSON is `jsonb`; `format_group` is text like `'T20_men'`. Every table has `created_at` (default now).

---

## 1. Reference data

**teams**: `id`, `name`, `short_code`, `gender`, `colour_hex` (filled by us), `cricketdata_id`, `cricsheet_name`

**venues**: `id`, `name`, `city`, `country`, `lat`, `lon`, `cricketdata_id`, `cricsheet_name`

**venue_pitch_types**: `venue_id`, `format_group`, `pitch_type` (`batting` / `bowling` / `unknown`), `matches_n`, `avg_first_innings`, `updated_at`

**players**: `id`, `full_name`, `gender`, `cricsheet_id`, `cricketdata_id`, `image_url`, `image_source`, `batting_style` (nullable), `bowling_style` (nullable), `updated_at`

**player_name_links**: `id`, `player_id`, `source` (`dream11` / `cricketdata` / `cricsheet`), `source_name`, `confirmed_by_aryan` (bool), `confirmed_at`

---

## 2. Matches and data

**matches**: `id`, `cricketdata_id`, `cricsheet_id`, `format`, `gender`, `format_group`, `series_name`, `venue_id`, `team_a_id`, `team_b_id`, `start_time`, `status` (`upcoming` / `live` / `finished` / `abandoned`), `toss_winner_team_id`, `toss_decision`, `batting_first_team_id`, `rain_affected` (bool), `xi_announced` (bool), `updated_at`

**match_xi**: `match_id`, `team_id`, `player_id`, `source` (`cricketdata` / `cricsheet`), `fetched_at`

**player_match_points**: `id`, `player_id`, `match_id`, `format_group`, `batting_points`, `bowling_points`, `fielding_points`, `total_points`, `batting_position`, `overs_bowled`, `retired_hurt` (bool), `source` (`cricsheet` / `scorecard`), `is_provisional` (bool), `updated_at`
Unique on (`player_id`, `match_id`). A `scorecard` row is replaced, not duplicated, when Cricsheet publishes.

**api_cache**: `id`, `source`, `request_key`, `response` (jsonb), `fetched_at`, `expires_at`

**api_usage**: `source`, `date`, `calls` (primary key `source`, `date`)

---

## 3. Settings and rules

**settings**: `key` (primary key), `value` (jsonb), `updated_by`, `updated_at` (keys listed in RUBRIC.md section 11)

**dream11_rules**: `id`, `format`, `credit_budget`, `role_limits` (jsonb: `{WK:{min,max}, BAT:{...}, AR:{...}, BOWL:{...}}`), `max_per_side`, `captain_multiplier`, `vc_multiplier`, `version`, `updated_by`, `updated_at`

**dream11_points_table**: `id`, `format`, `point_type`, `value`, `version`, `updated_at`

**gemini_rules**: `id`, `job` (`moderator` / `explainer` / `analyst` / `screenshot`), `system_prompt`, `version`, `updated_at`

---

## 4. Rubric

**rubric_versions**: `id`, `format_group`, `version` (int), `weights` (jsonb, 8 factors), `thin_data_full_trust`, `source` (`backtest` / `approved_change` / `aryan_edit` / `rollback` / `benchmark_50_50`), `parent_version_id`, `test_mae`, `validation_mae`, `baseline_mae`, `benchmark_50_50_mae`, `reliable` (bool), `borrowed_from_group` (nullable), `points_values_final` (bool: Dream11 values copied from the app), `is_active` (bool), `approved_by`, `approved_at`

**format_scaling**: `from_group`, `to_group`, `ratio`, `players_n`, `updated_at`

**debutant_averages**: `format_group`, `avg_points`, `players_n`, `updated_at`

**backtest_predictions**: `id`, `match_id`, `player_id`, `format_group`, `factors` (jsonb), `predicted`, `actual`, `error`, `is_real_miss`, `split` (`warmup` / `fit` / `validation` / `test`), `run_label`

---

## 5. Aryan's choices and inputs

**match_choices**: `id`, `match_id`, `choice` (`play` / `skip`), `chosen_at`, `undone` (bool)

**credits**: `id`, `match_id`, `player_id`, `credits`, `dream11_role` (`WK` / `BAT` / `AR` / `BOWL`), `entered_via` (`screenshot` / `typed` / `prefill`), `confirmed_at`

**results**: `id`, `match_id`, `player_id`, `aryan_points`, `aryan_rank` (nullable, match-level copy allowed), `entered_via`, `calc_points`, `mismatch` (bool), `entered_at`

**overrides**: `id`, `run_id`, `match_id`, `out_player_id`, `in_player_id`, `captaincy_change` (jsonb), `reason`, `gate_passed` (bool), `created_at`

---

## 6. Runs and outputs

**runs**: `id`, `match_id`, `run_type` (`pre_toss` / `post_toss`), `status` (`checking` / `scoring` / `moderating` / `optimizing` / `explaining` / `done` / `failed`), `failed_step`, `error_message`, `pool_type` (jsonb per team: `confirmed` / `probable` / `full`), `rubric_version_id`, `warnings` (jsonb), `data_stale` (bool), `started_at`, `finished_at`

**predictions**: `id`, `run_id`, `player_id`, `factors` (jsonb), `trust` (jsonb), `fallback_step` (1–4), `fallback_note`, `thin_data` (bool), `provisional_inputs` (bool), `provisional_weights` (bool), `borrowed_from_group`, `base_score`, `gemini_change_pct`, `adjusted_score` (the last two are added in the Gemini phase)

**gemini_adjustments**: `id`, `run_id`, `player_id`, `requested_pct`, `applied_pct`, `clipped` (bool), `reason`, `reason_type`, `source_url`, `helped` (bool, filled after results)

**gemini_calls**: `id`, `job`, `run_id` (nullable), `model`, `input_summary`, `output` (jsonb), `valid` (bool), `validation_errors` (jsonb), `latency_ms`, `created_at`

**teams_picked**: `id`, `run_id`, `kind` (`system` / `aryan_final` / `simple` / `perfect`), `player_ids` (jsonb), `captain_id`, `vc_id`, `total_expected`, `total_actual` (filled after results), `credits_used`, `gate_passed` (bool)

**bench**: `id`, `run_id`, `player_id`, `rank` (1–4), `reason_code` (`credits` / `role_limit` / `side_cap` / `lower_score`), `reason_detail`, `points_cost`

**explanations**: `id`, `run_id`, `player_id`, `kind` (`player` / `captain` / `vice_captain` / `bench`), `text`, `generic_flag` (bool)

---

## 7. Learning

**metrics**: `id`, `match_id`, `format_group`, `system_points`, `aryan_points`, `simple_points`, `perfect_points`, `points_roi`, `efficiency`, `captain_hit` (bool), `override_hit_rate`, `gemini_value`, `mae`, `points_final` (bool: exact Cricsheet points used), `excluded_from_learning` (bool), `computed_at`

**patterns**: `id`, `format_group`, `group_type` (`role` / `batting_band` / `bat_first_chase` / `pitch_venue`), `group_value`, `window_matches`, `real_misses`, `same_direction_pct`, `avg_error`, `direction` (`over` / `under`), `status` (`watching` / `flagged` / `resolved`), `updated_at`

**weight_suggestions**: `id`, `kind` (`weight` / `rollback` / `gemini_cap`), `pattern_id` (nullable), `format_group`, `proposal` (jsonb), `gemini_text` (jsonb), `history_check` (`supported` / `not_supported`), `history_mae_before`, `history_mae_after`, `aryan_decision` (`approved` / `edited` / `rejected` / `pending`), `aryan_version` (jsonb), `decided_at`, `resulting_version_id`

---

## 8. Audit

**activity_log**: `id`, `at`, `actor` (`system` / `aryan` / `gemini`), `action`, `match_id` (nullable), `details` (jsonb)
