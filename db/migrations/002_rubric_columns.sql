-- Add the spec's missing columns to the run 1 rubric_versions table. Additive only.
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS validation_mae real;
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS benchmark_50_50_mae real;
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS reliable boolean;
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS borrowed_from_group text;
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS points_values_final boolean NOT NULL DEFAULT false;
ALTER TABLE rubric_versions ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT false;

-- Backfill from backtest run 1 (backtest_report.md): every group had >= 100 evaluated matches
-- except Test-female (2), which the report flags as unreliable. Point values are provisional.
UPDATE rubric_versions SET reliable = (format_group <> 'Test-female')
 WHERE version = 'v1' AND reliable IS NULL;
UPDATE rubric_versions r SET is_active = true
 WHERE r.version = 'v1'
   AND NOT EXISTS (SELECT 1 FROM rubric_versions o WHERE o.format_group = r.format_group AND o.is_active);
