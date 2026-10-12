-- Phase 4-7 tables from docs/NEON_SCHEMA.md (additive only; nothing dropped or renamed).
ALTER TABLE runs ADD COLUMN IF NOT EXISTS pool_type jsonb;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS warnings jsonb;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS gemini_change_pct real;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS adjusted_score real;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS colour_hex text;

CREATE TABLE IF NOT EXISTS gemini_rules (
  id bigserial PRIMARY KEY,
  job text NOT NULL CHECK (job IN ('moderator', 'explainer', 'analyst', 'screenshot')),
  system_prompt text NOT NULL,
  version integer NOT NULL DEFAULT 1,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (job, version)
);

CREATE TABLE IF NOT EXISTS gemini_calls (
  id bigserial PRIMARY KEY,
  job text NOT NULL,
  run_id uuid REFERENCES runs(id),
  model text,
  input_summary text,
  output jsonb,
  valid boolean,
  validation_errors jsonb,
  latency_ms integer,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gemini_adjustments (
  id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES runs(id),
  player_id text NOT NULL REFERENCES players(id),
  requested_pct real,
  applied_pct real,
  clipped boolean NOT NULL DEFAULT false,
  reason text,
  reason_type text,
  source_url text,
  helped boolean,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS teams_picked (
  id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES runs(id),
  kind text NOT NULL CHECK (kind IN ('system', 'aryan_final', 'simple', 'perfect')),
  player_ids jsonb NOT NULL,
  captain_id text,
  vc_id text,
  total_expected real,
  total_actual real,
  credits_used real,
  gate_passed boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bench (
  id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES runs(id),
  player_id text NOT NULL REFERENCES players(id),
  rank integer,
  reason_code text CHECK (reason_code IN ('credits', 'role_limit', 'side_cap', 'lower_score')),
  reason_detail text,
  points_cost real,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS explanations (
  id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES runs(id),
  player_id text NOT NULL REFERENCES players(id),
  kind text NOT NULL CHECK (kind IN ('player', 'captain', 'vice_captain', 'bench')),
  text text NOT NULL,
  generic_flag boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS match_choices (
  id bigserial PRIMARY KEY,
  match_id text NOT NULL REFERENCES matches(id),
  choice text NOT NULL CHECK (choice IN ('play', 'skip')),
  chosen_at timestamptz NOT NULL DEFAULT now(),
  undone boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS credits (
  id bigserial PRIMARY KEY,
  match_id text NOT NULL REFERENCES matches(id),
  player_id text NOT NULL REFERENCES players(id),
  credits real NOT NULL,
  dream11_role text NOT NULL CHECK (dream11_role IN ('WK', 'BAT', 'AR', 'BOWL')),
  entered_via text CHECK (entered_via IN ('screenshot', 'typed', 'prefill')),
  confirmed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS results (
  id bigserial PRIMARY KEY,
  match_id text NOT NULL REFERENCES matches(id),
  player_id text NOT NULL REFERENCES players(id),
  aryan_points real,
  aryan_rank integer,
  entered_via text,
  calc_points real,
  mismatch boolean NOT NULL DEFAULT false,
  entered_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS overrides (
  id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES runs(id),
  match_id text REFERENCES matches(id),
  out_player_id text,
  in_player_id text,
  captaincy_change jsonb,
  reason text,
  gate_passed boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS metrics (
  id bigserial PRIMARY KEY,
  match_id text NOT NULL UNIQUE REFERENCES matches(id),
  format_group text,
  system_points real,
  aryan_points real,
  simple_points real,
  perfect_points real,
  points_roi real,
  efficiency real,
  captain_hit boolean,
  override_hit_rate real,
  gemini_value real,
  mae real,
  points_final boolean NOT NULL DEFAULT false,
  excluded_from_learning boolean NOT NULL DEFAULT false,
  computed_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS patterns (
  id bigserial PRIMARY KEY,
  format_group text NOT NULL,
  group_type text NOT NULL CHECK (group_type IN ('role', 'batting_band', 'bat_first_chase', 'pitch_venue')),
  group_value text NOT NULL,
  window_matches integer,
  real_misses integer,
  same_direction_pct real,
  avg_error real,
  direction text CHECK (direction IN ('over', 'under')),
  status text NOT NULL DEFAULT 'watching' CHECK (status IN ('watching', 'flagged', 'resolved')),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (format_group, group_type, group_value)
);

CREATE TABLE IF NOT EXISTS weight_suggestions (
  id bigserial PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('weight', 'rollback', 'gemini_cap')),
  pattern_id bigint REFERENCES patterns(id),
  format_group text,
  proposal jsonb,
  gemini_text jsonb,
  history_check text CHECK (history_check IN ('supported', 'not_supported')),
  history_mae_before real,
  history_mae_after real,
  aryan_decision text NOT NULL DEFAULT 'pending' CHECK (aryan_decision IN ('approved', 'edited', 'rejected', 'pending')),
  aryan_version jsonb,
  decided_at timestamptz,
  resulting_version_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS activity_log (
  id bigserial PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL CHECK (actor IN ('system', 'aryan', 'gemini')),
  action text NOT NULL,
  match_id text,
  details jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Settings used by the Gemini and learning phases (RUBRIC.md section 11); never overwrite existing values.
-- screenshot_credits_range / screenshot_points_range are sanity bounds for flagging rows as unsure, not Dream11
-- rules. TODO-CONFIRM: tune from real screenshots.
INSERT INTO settings (key, value, updated_by) VALUES
  ('gemini_cap_percent', '20', 'seed'),
  ('real_miss_mae_multiplier', '1.5', 'seed'),
  ('flag_window_matches', '10', 'seed'),
  ('flag_min_misses', '10', 'seed'),
  ('flag_same_direction', '0.70', 'seed'),
  ('max_weight_change', '0.10', 'seed'),
  ('rollback_window_matches', '10', 'seed'),
  ('gemini_trust_window_matches', '20', 'seed'),
  ('bench_size', '4', 'seed'),
  ('probable_xi_days', '30', 'seed'),
  ('screenshot_credits_range', '[3, 13]', 'seed'),
  ('screenshot_points_range', '[-50, 500]', 'seed')
ON CONFLICT (key) DO NOTHING;
