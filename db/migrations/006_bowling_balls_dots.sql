-- Balls bowled and dot balls per player per match (exact from Cricsheet ball-by-ball), so provisional
-- scorecard rows can estimate dot balls from the bowler's own past dot-ball rate. Additive only.
ALTER TABLE player_match_points ADD COLUMN IF NOT EXISTS balls_bowled integer;
ALTER TABLE player_match_points ADD COLUMN IF NOT EXISTS dot_balls integer;
ALTER TABLE player_match_points ADD COLUMN IF NOT EXISTS dot_balls_estimated boolean NOT NULL DEFAULT false;

-- Our choice (not a Dream11 value): a bowler needs at least this many past legal balls in the format
-- group before his dot-ball rate is used. 60 balls = 10 overs.
INSERT INTO settings (key, value, updated_by) VALUES ('dot_rate_min_balls', '60', 'seed')
ON CONFLICT (key) DO NOTHING;
