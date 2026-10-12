-- Decision by Shashank (13 Oct 2026): learnings update after every 5 scored matches in a format group, not 10.
UPDATE settings SET value = '5', updated_by = 'shashank', updated_at = now()
 WHERE key IN ('flag_window_matches', 'flag_min_misses', 'rollback_window_matches');
