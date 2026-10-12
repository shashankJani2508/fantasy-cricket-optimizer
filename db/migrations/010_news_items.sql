-- Google News RSS items shown to Gemini's moderator (GEMINI_RULES.md Job 1), and which path each adjustment used.
CREATE TABLE IF NOT EXISTS news_items (
  id bigserial PRIMARY KEY,
  match_id text REFERENCES matches(id),
  run_id uuid REFERENCES runs(id),
  title text NOT NULL,
  snippet text,
  link text NOT NULL,
  source_name text,
  published_at timestamptz,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS news_items_run ON news_items (run_id);
ALTER TABLE gemini_adjustments ADD COLUMN IF NOT EXISTS news_item_id bigint REFERENCES news_items(id);
ALTER TABLE gemini_adjustments ADD COLUMN IF NOT EXISTS news_path text CHECK (news_path IN ('rss', 'grounding'));
