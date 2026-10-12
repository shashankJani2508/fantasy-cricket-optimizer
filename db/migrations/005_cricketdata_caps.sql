-- Extra CricketData.org caps (RUBRIC.md section 11, SCORING_ENGINE.md fix-up 5). Seed only if absent.
INSERT INTO settings (key, value, updated_by) VALUES
  ('cricketdata_dev_daily_limit', '30', 'seed'),
  ('cricketdata_max_calls_per_run', '15', 'seed')
ON CONFLICT (key) DO NOTHING;
