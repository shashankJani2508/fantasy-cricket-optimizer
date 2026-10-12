-- Player photo provenance (engine/photos.py): CricketData.org playerImg, else Wikimedia Commons via Wikidata, else none.
ALTER TABLE players ADD COLUMN IF NOT EXISTS image_license text;
ALTER TABLE players ADD COLUMN IF NOT EXISTS image_author text;
ALTER TABLE players ADD COLUMN IF NOT EXISTS image_page_url text;
ALTER TABLE players ADD COLUMN IF NOT EXISTS image_checked_at timestamptz;
ALTER TABLE players ADD COLUMN IF NOT EXISTS image_skip_reason text;
