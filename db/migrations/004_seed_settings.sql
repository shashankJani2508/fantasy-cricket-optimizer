-- Seed settings only if absent; never overwrite (spec section 7).
INSERT INTO settings (key, value, updated_by) VALUES
  ('form_window', '10', 'seed'),
  ('form_recent_double', '5', 'seed'),
  ('current_touch_matches', '5', 'seed'),
  ('current_touch_days', '30', 'seed'),
  ('thin_data_full_trust', '10', 'seed'),
  ('cold_start_min_matches', '3', 'seed'),
  ('pitch_type_min_matches', '5', 'seed'),
  ('thin_data_trust_threshold', '0.5', 'seed'),
  ('cricketdata_daily_limit', '95', 'seed')
ON CONFLICT (key) DO NOTHING;
