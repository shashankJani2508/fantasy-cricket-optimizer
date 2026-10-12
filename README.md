# Fantasy Cricket Match Day Optimizer

A match-day agent for Dream11 players. Swipe through this week's matches, upload a screenshot of Dream11's player
list, and get a valid 11 with captain, vice-captain, a sourced reason for every pick and the 4 best players left out.
After the match, enter your points; the app compares predicted with actual points and suggests weight changes that
you approve or reject.

## How it works

| Part | What it does |
|---|---|
| Scoring engine (`engine/score.py`) | 8 factors from ball-by-ball history, weighted by the active rubric version. Deterministic, no AI |
| Gemini Flash (`engine/gemini.py`) | Reads what numbers can't: today's news and pitch report (Google News RSS + Google Search grounding in the same call, every cited link code-checked, max ±20% per player), writes the reasons, analyses repeated misses, reads Dream11 screenshots. Never picks players or changes weights |
| Optimizer + gate (`engine/optimizer.py`, `engine/gate.py`) | Exact integer programme for the best valid team incl. captain 2x and vice-captain 1.5x; every team (and every edit) passes the Dream11 rules |
| Run pipeline (`engine/pipeline.py`) | checking → scoring → moderating → optimizing → explaining → done; each step saved in Neon, resumable |
| Learning loop (`engine/learning.py`) | Metrics per match, patterns, flags after 10 matches, history replay, rollback and Gemini-limit checks; weights change only with your approval |
| API (`api/index.py`) | FastAPI app on Vercel's Python runtime, wrapping `/engine` |
| App (`app/`, `components/`) | Next.js + TypeScript + Tailwind, mobile first |

## Data sources

- **CricketData.org**: fixtures, squads, scorecards, player photos (cached; free tier 100 calls a day, the app stops at 95).
- **Cricsheet**: ball-by-ball history and exact points.
- **Open-Meteo**: rain chance, dew point and humidity at the venue (no key).
- **Google News RSS** (fetched and filtered by our code) **+ Google Search through Gemini**: today's team news and pitch report, with source links. If the API key's search quota is exhausted, the moderator reads the RSS items only.
- **Dream11**: only through Aryan's screenshots or typing. The app never logs in to, scrapes or automates Dream11.

## Database: Neon

The case suggests Supabase; we chose **Neon (Postgres)** deliberately: plain Postgres, branchable for safe
migration tests. Migrations are in `db/migrations` (additive only): `python -m db.migrate --schema dev` first, then `--schema public`.

## Run locally

```
pip install -r requirements.txt -r requirements-dev.txt
npm install
cp .env.example .env        # fill in the values
npm run dev:api             # Python API on :8000
npm run dev                 # app on :3000 (proxies /api to :8000)
python -m pytest -q tests   # tests never call a live API
```

## Environment variables

`DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `CRICKETDATA_API_KEY`, `CRICKETDATA_MODE` (`live` in production),
`APP_PASSCODE` (optional; left empty there is no passcode, because the link is private to Aryan), `CRON_SECRET` (daily refresh).

## Limitations

- Points calculated before Cricsheet publishes a match are provisional (from the scorecard) and are replaced later.
- Dream11 can't be automated: credits, roles and actual points come from Aryan's screenshots or typing.
- Gemini's news reading can't be backtested; its value is measured live (`gemini_adjustments.helped`).
- Dream11 point values in `config/dream11_points.yaml` are marked with their source; until all come from the app,
  the rubric weights are labelled provisional.
- No confirmed-XI endpoint has been verified on CricketData.org yet, so post-toss runs use the squad.

The app talks only to Gemini Flash; no other model is called.
