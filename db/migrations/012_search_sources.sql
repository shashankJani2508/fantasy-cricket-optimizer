-- Moderator uses Google News RSS and Google Search grounding on every run (GEMINI_RULES.md Job 1).
CREATE TABLE IF NOT EXISTS search_sources (
  id bigserial PRIMARY KEY,
  run_id uuid REFERENCES runs(id),
  title text,
  link text NOT NULL,
  source_name text,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE gemini_adjustments ADD COLUMN IF NOT EXISTS source_type text CHECK (source_type IN ('rss', 'search', 'forecast'));
ALTER TABLE gemini_adjustments ADD COLUMN IF NOT EXISTS search_source_id bigint REFERENCES search_sources(id);
