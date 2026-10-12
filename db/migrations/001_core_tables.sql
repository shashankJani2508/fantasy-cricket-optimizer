-- Scoring engine tables (spec section 7). Additive only: CREATE ... IF NOT EXISTS.
-- Extra columns beyond the spec, flagged in the build summary:
--   matches.first_innings_total      (needed by the pitch_type factor)
--   player_match_points.bowling_band (needed by the opportunity factor; Tests use most overs in one innings)

CREATE TABLE IF NOT EXISTS teams (
  id text PRIMARY KEY,
  name text NOT NULL,
  short_code text,
  gender text,
  cricketdata_id text,
  cricsheet_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS venues (
  id text PRIMARY KEY,
  name text NOT NULL,
  city text,
  country text,
  lat double precision,
  lon double precision,
  cricketdata_id text,
  cricsheet_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS players (
  id text PRIMARY KEY,
  full_name text NOT NULL,
  gender text,
  cricsheet_id text,
  cricketdata_id text,
  image_url text,
  image_source text,
  batting_style text,
  bowling_style text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS player_name_links (
  id bigserial PRIMARY KEY,
  player_id text NOT NULL REFERENCES players(id),
  source text NOT NULL CHECK (source IN ('dream11', 'cricketdata', 'cricsheet')),
  source_name text NOT NULL,
  confirmed_by_aryan boolean NOT NULL DEFAULT false,
  confirmed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, source_name, player_id)
);

CREATE TABLE IF NOT EXISTS matches (
  id text PRIMARY KEY,
  cricketdata_id text UNIQUE,
  cricsheet_id text UNIQUE,
  format text,
  gender text,
  format_group text,
  series_name text,
  venue_id text REFERENCES venues(id),
  team_a_id text REFERENCES teams(id),
  team_b_id text REFERENCES teams(id),
  start_time timestamptz,
  status text,
  toss_winner_team_id text REFERENCES teams(id),
  toss_decision text,
  batting_first_team_id text REFERENCES teams(id),
  rain_affected boolean NOT NULL DEFAULT false,
  xi_announced boolean NOT NULL DEFAULT false,
  first_innings_total integer,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS match_xi (
  match_id text NOT NULL REFERENCES matches(id),
  team_id text REFERENCES teams(id),
  player_id text NOT NULL REFERENCES players(id),
  source text,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS player_match_points (
  id bigserial PRIMARY KEY,
  player_id text NOT NULL REFERENCES players(id),
  match_id text NOT NULL REFERENCES matches(id),
  format_group text,
  batting_points real,
  bowling_points real,
  fielding_points real,
  total_points real,
  batting_position integer,
  overs_bowled real,
  bowling_band text,
  retired_hurt boolean NOT NULL DEFAULT false,
  source text NOT NULL CHECK (source IN ('cricsheet', 'scorecard')),
  is_provisional boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (player_id, match_id)
);

CREATE TABLE IF NOT EXISTS api_cache (
  id bigserial PRIMARY KEY,
  source text NOT NULL,
  request_key text NOT NULL,
  response jsonb NOT NULL,
  fetched_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  UNIQUE (source, request_key)
);

CREATE TABLE IF NOT EXISTS api_usage (
  source text NOT NULL,
  date date NOT NULL,
  calls integer NOT NULL DEFAULT 0,
  PRIMARY KEY (source, date)
);

CREATE TABLE IF NOT EXISTS settings (
  key text PRIMARY KEY,
  value jsonb NOT NULL,
  updated_by text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  match_id text REFERENCES matches(id),
  run_type text NOT NULL CHECK (run_type IN ('pre_toss', 'post_toss')),
  status text NOT NULL,
  failed_step text,
  error_message text,
  rubric_version_id text,
  data_stale boolean NOT NULL DEFAULT false,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS predictions (
  id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES runs(id),
  player_id text NOT NULL REFERENCES players(id),
  factors jsonb,
  trust jsonb,
  fallback_step integer,
  fallback_note text,
  thin_data boolean,
  provisional_inputs boolean,
  provisional_weights boolean,
  borrowed_from_group text,
  base_score real,
  created_at timestamptz NOT NULL DEFAULT now()
);
