-- Upcoming tab shows internationals and the IPL only (config/competitions.yaml).
INSERT INTO settings (key, value, updated_by) VALUES
  ('show_international', 'true', 'seed'), ('show_womens_international', 'true', 'seed'),
  ('show_ipl', 'true', 'seed'), ('show_domestic', 'false', 'seed')
ON CONFLICT (key) DO NOTHING;
