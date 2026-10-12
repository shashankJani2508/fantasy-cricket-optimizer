-- NEON_SCHEMA.md section 4 columns missing from run 1's rubric_versions (additive).
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'backtest';
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS parent_version_id integer;
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS approved_at timestamptz;
