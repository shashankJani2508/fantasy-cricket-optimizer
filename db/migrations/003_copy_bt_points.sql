-- Copy run 1 points (bt_player_match_points) into player_match_points with source = 'cricsheet'.
-- bt_player_match_points is kept untouched. Run 1 group names ("T20-male") become spec names ("T20_men").
-- Players and matches get minimal rows here; `engine.cli refresh-cricsheet --full` enriches them
-- (venues, teams, XI, batting position, bowling band, first-innings totals) from the Cricsheet files.

INSERT INTO players (id, full_name, gender, cricsheet_id)
SELECT DISTINCT ON (player_id) player_id, player_name, split_part(format_group, '-', 2), player_id
  FROM bt_player_match_points
 ORDER BY player_id, match_date DESC
ON CONFLICT (id) DO NOTHING;

INSERT INTO matches (id, cricsheet_id, format, gender, format_group, start_time, status)
SELECT DISTINCT ON (match_id) match_id, match_id, split_part(format_group, '-', 1), split_part(format_group, '-', 2),
       split_part(format_group, '-', 1) || '_' ||
         CASE split_part(format_group, '-', 2) WHEN 'male' THEN 'men' ELSE 'women' END,
       match_date::timestamptz, 'finished'
  FROM bt_player_match_points
 ORDER BY match_id
ON CONFLICT (id) DO NOTHING;

INSERT INTO player_match_points (player_id, match_id, format_group, batting_points, bowling_points,
                                 fielding_points, total_points, source, is_provisional)
SELECT player_id, match_id,
       split_part(format_group, '-', 1) || '_' ||
         CASE split_part(format_group, '-', 2) WHEN 'male' THEN 'men' ELSE 'women' END,
       batting, bowling, fielding, total, 'cricsheet', false
  FROM bt_player_match_points
ON CONFLICT (player_id, match_id) DO NOTHING;
