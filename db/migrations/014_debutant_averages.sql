-- New-player estimate (fallback step 4): average points of every player's first match in the format group,
-- from player_match_points (Cricsheet rows). Replaced by backtest run 2's values when that runs.
CREATE TABLE IF NOT EXISTS debutant_averages (
  format_group text PRIMARY KEY, avg_points real NOT NULL, players_n integer, updated_at timestamptz NOT NULL DEFAULT now());
INSERT INTO debutant_averages (format_group, avg_points, players_n)
SELECT format_group, avg(total_points), count(*) FROM (
  SELECT DISTINCT ON (p.player_id, p.format_group) p.format_group, p.total_points
    FROM player_match_points p JOIN matches m ON m.id = p.match_id
   WHERE p.source = 'cricsheet' ORDER BY p.player_id, p.format_group, m.start_time) first
GROUP BY format_group
ON CONFLICT (format_group) DO NOTHING;
