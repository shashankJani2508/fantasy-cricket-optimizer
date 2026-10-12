-- Learnings in two modes (13 Oct 2026, Shashank): 'demo' flags a pattern after every single scored match,
-- 'real' after 5 (settings flag_window_matches / flag_min_misses). Both need Aryan's approval.
ALTER TABLE patterns ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'real' CHECK (mode IN ('demo', 'real'));
ALTER TABLE weight_suggestions ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'real' CHECK (mode IN ('demo', 'real'));
ALTER TABLE patterns DROP CONSTRAINT IF EXISTS patterns_format_group_group_type_group_value_key;
CREATE UNIQUE INDEX IF NOT EXISTS patterns_mode_key ON patterns (format_group, group_type, group_value, mode);
INSERT INTO settings (key, value, updated_by) VALUES ('demo_flag_window_matches', '1', 'seed'), ('demo_flag_min_misses', '1', 'seed')
ON CONFLICT (key) DO NOTHING;
