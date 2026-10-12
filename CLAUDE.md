# CLAUDE.md: Master Build Prompt

> Fantasy Cricket Match Day Optimizer. MESA Cohort C4, AI and its Applications, Section 1 Final.
> This is the entry point for Claude Code. Read this file completely, then every spec in `/docs`, before writing any code.

---

## 0. How to work on this project

You are the lead engineer and the product designer on a small, high-stakes build. The person you work with (Shashank) designed the system in detail; every decision below was deliberate. Your job is to build it faithfully, to an exceptional standard, and to raise problems instead of papering over them.

Working agreements:

1. **Read before you build.** Read this file, then `docs/UI_UX.md`, `docs/RUBRIC.md`, `docs/NEON_SCHEMA.md`, `docs/SCORING_ENGINE.md`, `docs/GEMINI_RULES.md`, `docs/OPTIMIZER.md`, `docs/LEARNING_LOOP.md`, `docs/BACKTEST_PROMPT.md`, `docs/BACKTEST_MAP.md`, and look at `docs/components-map.png` and `design/reference/`.
2. **Plan, then build, phase by phase** (section 12). At the start of each phase, write a short plan (files, functions, tables, tests) and wait for a go-ahead. At the end, show what was built and the tests that pass.
3. **Never guess facts.** Dream11 point values, Dream11 rules, API field names, model IDs: if a spec doesn't give it, ask or check official documentation. Never fill a value from memory and present it as fact.
4. **Never fake data on screen.** No placeholder players, invented scores or lorem ipsum in anything that ships. Use real data or a designed empty state.
5. **Prefer simple, correct and observable** over clever. Every important step writes what it did to Neon (`activity_log`, `runs`, `gemini_calls`).
6. **When specs conflict,** apply the precedence table (section 5). If still unclear, stop and ask.
7. **The UI is the product.** A correct engine behind a mediocre interface is a failed project. Treat `UI_UX.md` as a requirement, not a suggestion.

### 0.1 No hallucination: rules for facts

1. **Every external fact must come from a source you actually checked:** official docs, a real API response, the Dream11 app (via us), or these specs. If you can't check it, write `TODO-CONFIRM: <what and where>` in code and in your summary, and ask. Never present a guess as fact.
2. **API fields:** before writing a client for CricketData.org, Open-Meteo or Gemini, make one real call (or read the official docs), save the raw response to `/tests/fixtures/<source>/`, and write code against that saved response. Never write field names from memory.
3. **Dream11 values** (points, credits, rules) come only from `config/` files filled by us from the app. If a value is missing, stop and ask.
4. **Libraries:** use only libraries you have installed and imported successfully; check their current documentation for function names. If a library doesn't support something, say so instead of inventing an API.
5. **Numbers in summaries** (errors, weights, counts) must be copied from actual outputs, not estimated.
6. **When this file or a spec seems wrong** (e.g. a field doesn't exist, a limit is different), report it with evidence. Don't silently work around it.

### 0.2 Don't break working code: rules for changes

Some code already works, especially the backtest from run 1 and the shared `/engine/points.py` and `/engine/factors.py`. Protect it.

1. **Git discipline:** work on a branch per phase; commit before and after every significant change; never force-push `main`; never delete files without listing them first and getting a yes.
2. **Run the existing tests before you change anything,** and again after. If anything that passed now fails, stop, show the failure, and fix or revert before continuing.
3. **Small, reviewable diffs.** No broad refactors, renames or "cleanups" that weren't asked for. If you think a refactor is needed, propose it first.
4. **Shared engine modules** (`points.py`, `factors.py`): change them only when `RUBRIC.md` requires it. After any change, rerun the no-peeking and determinism tests, and confirm the backtest still runs.
5. **Database changes are additive and reversible.** Every change is a new migration (never edit an applied one); test it on a Neon development branch first; take a Neon branch snapshot before migrating production; never drop a table or column holding data without a yes.
6. **Table renames from run 1:** run 1 created `bt_player_match_points` and `bt_predictions`. Migrate them to `player_match_points` (with `source = 'cricsheet'`) and `backtest_predictions` with a migration that **copies the data**, verify row counts match, update every code reference in the same commit, run the tests, and only then (with a yes) drop the old tables. Until then, keep them.
7. **Config and secrets:** never overwrite `config/` values we filled in; never commit `.env`.
8. **If you're unsure whether a change could break something, ask first.**

---

## 1. The product in one page

### The user

**Aryan** has played Dream11 seriously for three years. Before every match he spends 45 to 60 minutes researching player form, pitch conditions, team announcements and captaincy. When two or three matches fall in one week he can't give each the same care. He also has no record of whether his past picks were good decisions or lucky, so he can't improve.

### What he wants (from the case)

1. A match day agent that decides **which players to pick, who to bench, who to captain, and why**, with reasoning specific to this match and venue, not generic "in form" lines.
2. A team that is **valid to submit in Dream11 without any corrections.**
3. Captain and vice-captain picks with reasons he'd **confidently explain to his fantasy league group.**
4. **Self-improvement:** when picks keep going wrong for a type of match or player, the system recognises the pattern and adjusts.
5. After each match, Aryan **manually enters actual Dream11 points** for the players he selected; the system stores predicted vs actual, finds where predictions are consistently wrong, and **suggests adjustments to the scoring weights.**

### What we built (the experience)

- **Upcoming:** Aryan swipes through this week's matches like a dating app. Right = play, left = skip.
- **Swipe right:** he uploads a screenshot of Dream11's player list (credits and roles), checks it, taps "Build my team". In about a minute a team appears.
- **Results:** a team sheet with real player photos on a cricket ground, captain and vice-captain badged, a one-line reason per player, 4 benched players with reasons, warnings when he should double-check, and a checklist for entering the team in Dream11. He can edit the team; the app keeps it valid. After the toss he rebuilds with the confirmed XI. After the match he uploads the points screenshot and sees a scorecard.
- **Learnings:** how accurate the system is, and suggested weight changes he approves, edits or rejects.

### Success means

- From swipe to team in under 2 minutes of Aryan's effort.
- Every team passes Dream11's rules, every time.
- Every reason cites something specific (a number, a fact, a news source).
- Every learning change is evidence-backed, history-checked and approved by Aryan.
- The app feels as good as the best consumer sports apps.

---

## 2. Non-negotiable constraints (exam brief)

1. **All AI tasks use Gemini Flash** (Gemini 3.5 Flash via the Gemini API). The app must never call the Claude API or any other model. You (Claude Code) build it; the shipped app talks only to Gemini.
2. **Live external data** wherever possible; the app must work with real data at submission time.
3. **Deploy on Vercel** with a working public URL. **Public GitHub repository.**
4. **Database: Neon (Postgres).** The case names Supabase; Neon is our deliberate choice. The README states this.
5. **Components Map** submitted with the build (`docs/components-map.png`).

---

## 3. Glossary (use these words consistently in code and UI)

| Term | Meaning |
|---|---|
| Dream11 | The fantasy cricket app Aryan plays. Free-to-play in India since August 2025 (no cash contests), so "ROI" in this app means points, rank and time, never money |
| Credits | Dream11's price for each player. Teams must fit a credit budget (value from settings) |
| Dream11 role | WK (wicket-keeper), BAT (batter), AR (all-rounder), BOWL (bowler), as Dream11 labels the player. Only Dream11's label counts |
| Captain (C) / Vice-captain (VC) | Fantasy multipliers: C 2x, VC 1.5x (values from settings) |
| Playing XI / confirmed XI | The 11 each real team announces at the toss |
| Probable XI | Before the toss: the team's XI from its last match in the same format within 30 days |
| Toss | Start-of-match coin toss; decides who bats first. The XI is confirmed then |
| Format group | Format × gender, e.g. `T20_men`. All rubric numbers are per format group |
| Rubric | Our marking scheme: 8 factors and their weights per format group |
| Base score | Scoring engine's expected Dream11 points for a player |
| Adjusted score | Base score after Gemini's moderation (max ±20%) |
| Thin data | A prediction resting on little history (fallback steps 2 to 4, or low trust) |
| Provisional | (a) A team built before the toss; (b) points calculated from a scorecard before Cricsheet publishes |
| Real miss | A prediction error larger than 1.5 × the group's typical miss |
| Simple team | Benchmark: top 11 by recent average, made valid |
| Perfect team | Benchmark: best valid team in hindsight, from actual points |
| Run | One execution of the pipeline for a match: `pre_toss` or `post_toss` |

---

## 4. System overview

```
DAILY REFRESH (cron) ─► CricketData.org fixtures ─► Neon (matches, venues, teams)
                      └► Cricsheet new matches ─► player_match_points (replace provisional rows)

UPCOMING TAB
  swipe right ─► match_choices
             ─► screenshot of Dream11 player list ─► Gemini Job 4 (read) ─► review ─► credits
             ─► "Build my team" ─► RUN (pre_toss)

RUN PIPELINE (resumable steps, status in runs.status)
  1 checking    eligibility filter: Aryan's list ∩ pool (confirmed XI / probable XI / full list), name matching
  2 scoring     scoring engine: 8 factors, thin-data rule, fallback chain, active rubric version → base scores
  3 moderating  Gemini Job 1 with Google Search + Open-Meteo context → code checks → adjusted scores
  4 optimizing  optimizer (C 2x, VC 1.5x, Dream11 rules) → validity gate → bench 4 with forced re-solves
  5 explaining  Gemini Job 2 → code checks → explanations
  6 done        team sheet in Results; warnings computed

TOSS ─► XI announced ─► "Rebuild team" ─► RUN (post_toss)
EDITS ─► My final team ─► validity gate (live) ─► overrides
AFTER MATCH ─► points screenshot ─► Gemini Job 4 ─► results; scorecard auto-calculates all 22 players
LEARNING ─► metrics ─► patterns ─► flag ─► Gemini Job 3 ─► history replay ─► Aryan decides ─► rubric_versions
```

**Roles, in one line each:**
- **Rubric:** the marking scheme. Written by us; weights from the backtest; changed only by approved suggestions.
- **Scoring engine:** the calculator that applies the rubric. Code, no AI, deterministic.
- **Gemini:** reads what numbers can't (news, pitch, dew), explains picks, analyses error patterns, reads screenshots. Never calculates, never picks players, never changes weights.
- **Gemini's rules:** the limits on Gemini (`GEMINI_RULES.md`).
- **Optimizer + validity gate:** picks the best valid 11 and checks every team, including Aryan's edits.
- **Learning loop:** predicted vs actual → patterns → suggestions → Aryan's approval.

---

## 5. Documents and precedence

| File | Covers | Wins on |
|---|---|---|
| `CLAUDE.md` (this file) | Process, stack, flows, phases, constraints | Process and constraints |
| `docs/UI_REDESIGN.md` | The visual design, matched to `design/reference/dribbble-reference.png` | **How anything looks** |
| `docs/UI_UX.md` | Every screen, state, gesture and word | Flows and behaviour |
| `docs/NEON_SCHEMA.md` | Every table and column | Table and column names |
| `docs/RUBRIC.md` | Factors, formula, thresholds, fallbacks, backtest results | Factor definitions and numbers |
| `docs/SCORING_ENGINE.md` | Engine flow, freshness, fallback chain, call budget | Engine behaviour |
| `docs/GEMINI_RULES.md` | Gemini's 4 jobs, prompts, schemas, code checks | Anything Gemini does |
| `docs/OPTIMIZER.md` | Pool, solver, bench, validity gate | Team selection |
| `docs/LEARNING_LOOP.md` | Scorecard, flags, suggestions, rollback, Gemini trust | Learning |
| `docs/BACKTEST_PROMPT.md`, `docs/BACKTEST_MAP.md` | Backtest runs | Backtest |
| `docs/components-map.png` | Visual overview | Nothing (reference) |

Older table names in specs (`bt_player_match_points`, `bt_predictions`) are superseded by `NEON_SCHEMA.md` (`player_match_points` with `source='cricsheet'`, `backtest_predictions`).

---

## 6. Current status

| Item | Status |
|---|---|
| Design and specs | Complete |
| Backtest run 1 | Done (12 Oct 2026). Weights recorded in `RUBRIC.md` §7. **Provisional:** point values were not from the Dream11 app. Not for go-live |
| Backtest run 2 | **Next.** Instructions at the top of `BACKTEST_PROMPT.md` |
| Dream11 points table and rules | To be filled by us from the Dream11 app (`config/`) |
| Scoring engine (phase 3) | **Built** standalone on 12 Oct 2026; tests pass. **Fix-ups pending** (name matching coverage, fallback date, placeholder photos): see `SCORING_ENGINE.md` "Status" |
| Core tables | Created by the engine build (migrations 001 to 004). Later phases add tables with new migrations |
| Everything else | To build (section 12) |

### Next steps, in order

1. **Engine fix-ups:** prompt in `SCORING_ENGINE.md` "Status".
2. **Fill `config/dream11_points.yaml` from the Dream11 app** (us), then **backtest run 2** (`BACKTEST_PROMPT.md`).
3. **Phase 0 and 1 remainder:** anything from section 12 not yet built (check first; much of phase 0 and 1 exists from the engine build).
4. Phases 4 to 9 in order.

Key run 1 findings that shape the build:
- Career average dominates the weights; form got 0 (to be re-checked in run 2).
- The rubric beats "form only" by about 2%: Gemini's news reading and the learning loop matter for the rest of the edge.
- Typical misses are 21 to 43 points, so "real miss" is now relative to each group's typical miss.
- Test women has too few matches: it borrows Test men's weights.

---

## 7. Stack and repository

### Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript | Mobile-first PWA-quality web app |
| Styling | Tailwind CSS with the design tokens in `UI_UX.md` §2 as CSS variables | No component kit that imposes its own look |
| Motion | Framer Motion (`motion`) | Swipe deck drag, sheet transitions, the single team-sheet reveal |
| Charts | A light charting library (e.g. Recharts or visx) styled with our tokens | Learnings line chart, scorecard bars |
| Backend | Python serverless functions on Vercel | Shares `/engine` with the backtest. **Confirm in Vercel's docs how Python functions coexist with a Next.js project**; if they can't share one project cleanly, deploy the Python API as a second Vercel project and call it from Next.js with a server-side secret |
| Database | Neon Postgres | Migrations in `/db/migrations`; use a Neon branch for development |
| AI | Gemini 3.5 Flash via the official Google Gen AI SDK | Structured JSON output, Google Search grounding, image input |
| Optimizer | Integer programming (PuLP or OR-Tools) | **Verify it runs within Vercel's Python runtime and bundle limits**; fallback: exact pure-Python branch-and-bound (pools ≤ 30 players) |
| Scheduled jobs | Vercel Cron | Daily refresh; check the plan's cron frequency limits |
| Tests | pytest (Python), Vitest (TS), Playwright (end-to-end on a phone viewport) | |

### Repository layout

```
/app                         Next.js app (routes per UI_UX.md)
  /(tabs)/upcoming           swipe deck, setup sheet
  /(tabs)/results            match list, match view, editing, results entry, scorecard
  /(tabs)/learnings          health, inbox, groups, rubric history, settings
  /components                FixtureCard, SwipeDeck, TeamSheet, PlayerAvatar, PlayerSheet,
                             ValidityMeters, ProgressSteps, SuggestionCard, ScoreBoard, ...
  /lib                       API client, formatting, design tokens
/api                         Python endpoints (thin wrappers around /engine)
/engine
  points.py                  Dream11 points from ball-by-ball or scorecard (shared with backtest)
  factors.py                 8 factors + thin-data rule (shared with backtest)
  fallback.py                fallback chain steps 2-4
  matching.py                player name matching across sources
  fresh.py                   provisional points from CricketData.org scorecards
  score.py                   scoring engine entry point
  pool.py                    eligibility filter and pool selection
  optimizer.py               integer programme, bench re-solves
  gate.py                    validity gate (also used for Aryan's edits)
  gemini.py                  Gemini client, 4 jobs, schema validation, logging
  learning.py                metrics, patterns, flags, replay, rollback, Gemini trust
  warnings.py                "check this yourself" rules
  sources/cricketdata.py     client with cache + daily budget
  sources/cricsheet.py       downloader and parser
  sources/openmeteo.py       forecast client
  db.py                      Neon access
/backtest                    run scripts; imports /engine only
/config
  dream11_points.yaml        per format, every point type, value + source (filled from the app)
  dream11_rules.yaml         per format: budget, role limits, per-side cap, multipliers
  settings.yaml              seed values for `settings` (RUBRIC.md §11)
  team_colours.yaml          team short code → hex
/db/migrations
/docs                        all specs
/design/reference            Dribbble reference screenshot(s)
/tests
```

---

## 8. Configuration and environment

### Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Neon connection string |
| `GEMINI_API_KEY` | Gemini API key |
| `GEMINI_MODEL` | Exact Gemini 3.5 Flash model ID (confirm in Google's docs) |
| `CRICKETDATA_API_KEY` | CricketData.org key (free tier: 100 calls/day) |
| `CRICKETDATA_MODE` | `offline` (default for dev and tests), `cache_only` or `live` |
| `APP_PASSCODE` | Aryan's passcode for data-changing actions |
| `INTERNAL_API_SECRET` | Only if the Python API is a separate Vercel project |
| `CRON_SECRET` | Protects the daily refresh endpoint |

Never hardcode or log secrets. Provide `.env.example` with names only.

### Config files

- `dream11_points.yaml` and `dream11_rules.yaml` are seeded into `dream11_points_table` and `dream11_rules`. Every value carries a `source`. The app refuses to run a pipeline if any value is null; the backtest refuses to mark results final unless every source is `dream11_app`.
- `settings.yaml` seeds `settings` (keys in `RUBRIC.md` §11, including `real_miss_mae_multiplier: 1.5`).
- Gemini prompts in `GEMINI_RULES.md` are seeded into `gemini_rules` so they can be versioned.

---

## 9. Data sources: what, when, and the rules

**CricketData.org budget (free tier: 100 calls a day) is precious.** Default to `CRICKETDATA_MODE=offline` (fixtures and cache only) for all development and tests; use `cache_only` to re-run on cached data; use `live` only when needed, after a `--dry-run` shows the call count. Caps: 95 per day total, 30 per day for development commands, 15 per scoring run. Never fetch a finished match's scorecard twice. Every command prints calls used. Details in `SCORING_ENGINE.md` fix-up 5.

| Source | Used for | When | Rules |
|---|---|---|---|
| **CricketData.org** | Fixtures, squads, confirmed XI, toss, scorecards (provisional points), player info (career stats, image URL, role, bowling style if available) | Daily refresh; each run; after matches | Cache every response in `api_cache`; count calls in `api_usage`; hard stop at 95/day leaving headroom; on limit or outage use cache and set `runs.data_stale`. **Confirm endpoint names and fields** in their docs during phase 1 |
| **Cricsheet** | Ball-by-ball history; exact points | Daily refresh; backtest | Download once and cache; new matches replace provisional rows |
| **Open-Meteo** | Rain chance, dew point, humidity at the venue | Each run; fixture cards | Free, no key; cache per venue per hour |
| **Google Search via Gemini** | Today's team news and pitch report | Moderator step | Only through Gemini grounding; source links stored |
| **Dream11 app** | Credits, roles, actual points, rank, rules, points table | Aryan (screenshots or typing); us (settings) | **Never automate or scrape Dream11.** No logins, no bots |
| **Upcoming filter** | Which fixtures the Upcoming tab shows | Deck, story row, fixture refresh | `config/competitions.yaml`: internationals (both teams national sides) and the IPL only; history, factors and the backtest are never filtered |
| **Google News RSS** | Today's team news for the moderator | Each run | Our code fetches, filters (48 h, mentions, de-dup, max 20) and saves `news_items`; never fetch full articles |
| **Player photos** | Team sheet, cards, player sheet | `engine.cli photos --squads` (30-day recheck) | CricketData.org `playerImg` if real, else Wikimedia Commons via Wikidata (exact person, free licence, credit shown), else initials avatar; never scrape other sites |

Do not scrape ESPNcricinfo, Cricbuzz or Dream11.

---

## 10. End-to-end flows (implement exactly)

### A. Daily refresh (cron, once a day)
1. Fetch fixtures for the next 7 days → upsert `matches`, `teams`, `venues`.
2. Download new Cricsheet matches → compute points → replace `player_match_points` rows with `source='scorecard'` by `source='cricsheet'`; recompute affected `metrics` (`points_final = true`).
3. Update `venue_pitch_types`.
4. Mark finished matches; set `Enter results` state where Aryan played.
5. Log a summary to `activity_log`.

### B. Swipe and setup
1. Upcoming deck shows `matches` with `status='upcoming'` in the next 7 days, sorted by start time.
2. Swipe right → `match_choices(play)`; left → `match_choices(skip)` with Undo for 5 s.
3. Setup step 1: screenshot upload → Gemini Job 4 → rows → name matching (`player_name_links`; ask Aryan once for unmatched) → pre-fill from last match → review table → "Looks right" → `credits`.
4. Setup step 2: "Build my team" → create `runs(pre_toss)` → pipeline.

### C. Run pipeline (resumable)
Each step reads the previous step's saved output and writes its own, then updates `runs.status`. If a function times out or fails, the run can resume from the last completed step. The UI polls `runs.status` (or uses server-sent events) to tick the progress list.

1. **checking:** build the pool per team (`OPTIMIZER.md` §2) intersected with Aryan's Dream11 list; record `pool_type`.
2. **scoring:** `engine.score` for every pooled player → `predictions` (factors, trust, fallback_step, thin_data, base_score). Uses the active `rubric_versions` row for the format group (borrowed weights if unreliable).
3. **moderating:** Gemini Job 1 with search grounding and Open-Meteo context → validate → `gemini_adjustments` → `predictions.adjusted_score`.
4. **optimizing:** optimizer → gate → `teams_picked(kind='system')`; bench re-solves → `bench`; also build `teams_picked(kind='simple')` (expected).
5. **explaining:** Gemini Job 2 → validate (retry once for banned phrases) → `explanations`.
6. **done:** compute warnings (`RUBRIC.md` §10) → `runs.warnings`.
On failure: `runs.status='failed'`, `failed_step`, plain-English `error_message` with the fix.

### D. Toss refresh
When the daily or on-demand check finds `xi_announced = true` for a played match, show `Toss done: refresh`. "Rebuild team" creates `runs(post_toss)` with the confirmed XI. If Aryan had edits, offer to keep players still in the XI; re-gate.

### E. Aryan's edits
"My final team" starts from the latest system team. Every change calls the gate (client-side mirror for instant meters, server-side for the authoritative check). Save only when valid → `teams_picked(kind='aryan_final')` + `overrides`.

### F. Results entry
Points screenshot → Gemini Job 4 → review → `results` (with `calc_points` and `mismatch`). Then compute `metrics` with all 22 players' points (provisional from the scorecard if Cricsheet hasn't published), `teams_picked(kind='perfect')` via the optimizer on actual points, captain hit, override hit, Gemini value (`gemini_adjustments.helped`).

### G. Learning
After metrics: update `patterns`; on a new flag → Gemini Job 3 → replay on stored predictions → `weight_suggestions(kind='weight')` → Learnings inbox. On decision → new `rubric_versions` row (active from the next run). Rollback and Gemini-cap checks run after each scored match (`LEARNING_LOOP.md` §5).

---

## 11. Backend contract (endpoints)

Shapes are JSON. All mutating endpoints require the passcode session. Names are suggestions; keep them consistent.

| Method and path | Purpose |
|---|---|
| `POST /api/auth/passcode` | Verify passcode; set a 30-day httpOnly session cookie |
| `GET /api/matches/upcoming` | Deck data: matches, teams (codes, colours), venue, start time, rain chance, XI status, Aryan's choice |
| `POST /api/matches/{id}/choice` | `{choice: play|skip}`; `DELETE` to undo |
| `POST /api/matches/{id}/screenshots/player-list` | Images → Gemini Job 4 → rows with match suggestions and unsure flags |
| `POST /api/players/link` | Confirm a name match |
| `PUT /api/matches/{id}/credits` | Save reviewed credits and roles |
| `POST /api/matches/{id}/runs` | `{run_type}` → `run_id` |
| `GET /api/runs/{id}` | Status, step, warnings; when done: team, C/VC, bench, explanations, predictions, adjustments, player photos |
| `POST /api/runs/{id}/gate` | Validate a proposed team; returns per-rule results and the first fix hint |
| `PUT /api/runs/{id}/final-team` | Save Aryan's final team + overrides (must pass the gate) |
| `POST /api/matches/{id}/screenshots/points` | Images → Gemini Job 4 → points rows + rank |
| `PUT /api/matches/{id}/results` | Save results; triggers metrics and learning |
| `GET /api/matches/{id}/scorecard` | Metrics, team totals, predicted vs actual, swaps |
| `GET /api/learnings` | Health series, inbox, groups, rubric history |
| `POST /api/suggestions/{id}/decision` | `{decision: approve|edit|reject, version?}` |
| `GET/PUT /api/settings` | Rules, points table, colours, Gemini cap (passcode) |
| `GET /api/cron/daily` | Daily refresh (requires `CRON_SECRET`) |

---

## 12. Build phases, tasks and acceptance criteria

Work in order. Show a plan before each phase and a summary after.

### Phase 0: Foundations
- Repo, tooling, lint/format, CI running tests.
- Migrations for every table in `NEON_SCHEMA.md`; seed `settings`, `gemini_rules`, `team_colours`.
- Config loaders with null checks.
- **Done when:** migrations run on a fresh Neon branch; seeds load; null config values are refused with a clear message.

### Phase 1: Data sources and matching
- CricketData.org client (cache, budget, stale handling); confirm endpoints and fields, including player image URL.
- Cricsheet loader; Open-Meteo client; name matching with confidence and a confirmation path.
- Daily refresh job.
- **Done when:** this week's real fixtures, squads and venues are in Neon; budget logic proven by tests; a known player resolves across all three sources.

### Phase 2: Shared engine modules and backtest run 2
- `points.py` and `factors.py` (already used by run 1: review against `RUBRIC.md`, keep identical behaviour).
- Execute `BACKTEST_PROMPT.md` run 2 once the points table is filled from the app.
- **Done when:** run 2 report exists; active `rubric_versions` per group with `points_values_final = true`; `format_scaling`, `debutant_averages`, calibrated miss multiplier and flag threshold saved.

### Phase 3: Scoring engine (built; apply fix-ups)
- Pool, factors, thin-data rule, fallback chain, provisional fill, unreliable-group borrowing.
- **Done when:** determinism test passes; each fallback step sets thin_data; a run on a real upcoming match produces base scores for every pooled player.

### Phase 4: Gemini
- Client with structured output, search grounding, image input; per-job schema validation; retries with backoff (max 2); timeouts; logging to `gemini_calls`.
- Jobs 1 to 4 exactly per `GEMINI_RULES.md`.
- **Done when:** invalid outputs are clipped or rejected and logged; a real moderator call returns sourced adjustments or "no news found"; screenshot reading marks unreadable values as unsure.

### Phase 5: Optimizer, gate and bench
- Integer programme with C and VC; tie-break; bench forced re-solves; gate with plain-English messages.
- **Done when:** every returned team passes the gate; captain is the top scorer and VC second; bench reasons match forced re-solves; changing a rule in settings changes results without code changes.

### Phase 6: UI (the most important phase)
- Implement `UI_UX.md` completely: tokens, type, swipe deck, setup sheet, progress list, team sheet with photos and the single reveal, player sheet, editing with live meters, bench, copy-to-Dream11 checklist, toss refresh, results entry, scorecard, Learnings, Settings, every empty/loading/error/stale/view-only state.
- Build against real data from earlier phases.
- **Done when:** on a 390 px phone viewport and on desktop, a full journey works end to end with real data; Playwright tests cover swipe right/left/undo, setup, build, edit (invalid then valid), results entry, approve a suggestion; accessibility checks pass (keyboard, focus, contrast, reduced motion); no layout shift on photo load.

### Phase 7: Learning loop
- Metrics, simple and perfect teams, patterns, flags, suggestions with replay, rollback, Gemini trust.
- **Done when:** with seeded history (backtest predictions), a flag can be produced, a suggestion replayed, approved, and a new version activated; rollback and Gemini-cap suggestions trigger in tests.

### Phase 8: Hardening
- Error handling matrix (section 14), performance budgets (section 16), security review (section 15).
- **Done when:** simulated API outage, Gemini failure and solver infeasibility each produce the designed UI state.

### Phase 9: Deploy and submission
- Vercel production deploy; cron configured; environment variables set; README.
- Run at least one real match end to end before submission.
- **Done when:** the checklist in section 18 passes.

---

## 13. UI non-negotiables (summary; full spec in `UI_UX.md`)

- Mobile-first; bottom tabs (Upcoming, Results, Learnings); desktop left rail.
- Swipe deck: right = Play, left = Skip, Undo; buttons and arrow keys mirror swipes.
- Team sheet: real player photos on an oval ground, rows by Dream11 role, red C and yellow VC badges, "Picked by the system" label, one orchestrated reveal (under 700 ms; reduced-motion respected).
- Tokens exactly as specified (sightscreen, pavilion, turf, ball, floodlight, clay, slate); Big Shoulders Display for numbers and headlines; Hanken Grotesk for text; sentence case; no all-caps labels.
- Every action button says what happens; every error says what's wrong and how to fix it; every empty state invites the next action.
- Skeletons, not spinners. No fake data.
- Use `design/reference/` for mood and quality, never copy its layout or assets.

---

## 14. Error handling matrix

| Situation | Behaviour |
|---|---|
| CricketData.org down or limit reached | Use cache; `data_stale`; clay chip "Showing saved data from {time}" |
| No fixtures this week | Empty state with the next match date |
| Screenshot unreadable | Rows marked unsure; Aryan edits or types |
| Unmatched player name | Ask once; remember |
| Null config value | Block the run with "Fill the Dream11 points table in Settings" |
| No valid team possible | Run fails at optimizing with the rule that can't be met (likely a credit or role typo) |
| Gemini timeout or invalid output (moderator) | Retry up to 2; then continue **without** adjustments and add warning "News not checked" |
| Gemini failure (explainer) | Retry; then show numbers-based fallback lines generated by code ("Venue average 48, form 41") flagged as automatic |
| Gemini failure (analyst) | Leave the pattern flagged; retry on next match |
| Solver unavailable | Pure-Python exact fallback |
| Function timeout mid-run | Resume from last completed step |
| Points calculator mismatch | Alert in Results; never block saving |

---

## 15. Security and privacy

- View-only for visitors; passcode for anything that changes data; httpOnly session cookie; rate-limit passcode attempts.
- Secrets only in Vercel environment variables.
- Validate every input server-side (sizes, types, ranges); limit screenshot size and count.
- No personal data beyond Aryan's entries; no tracking scripts.

---

## 16. Performance budgets

- Upcoming deck interactive within 2 s on a mid-range phone over 4G.
- Run pipeline: target under 60 s end to end (moderator search is the slowest step; show progress).
- Images lazy-loaded at the rendered size; no layout shift.
- Engine scoring for 30 players under 2 s (history is precomputed in Neon).

---

## 17. Testing strategy

- **Unit:** points calculation per point type; each factor; thin-data rule; fallback steps; gate rules; Gemini schema validators; flag rule; replay.
- **Properties:** no-peeking (factors never see same-day or later matches); determinism; weights always sum to 1; captain is the top scorer.
- **Integration:** a full run on a recorded real match (snapshot fixtures in `/tests/fixtures`, recorded API responses, no live calls in CI).
- **End-to-end (Playwright, 390×844 and 1280×800):** the journeys listed in phase 6.
- **Gemini:** recorded responses for CI; one manual live smoke test per job before submission.

---

## 18. Submission checklist

- [ ] Public Vercel URL opens on a phone and shows this week's real matches.
- [ ] If no matches are scheduled on submission day, the empty state shows the next match date, and at least one recent match shows a full team sheet and scorecard.
- [ ] At least one real match run end to end: team built, explained, edited, results entered, scorecard shown.
- [ ] Learnings shows backtest history and the active rubric version (run 2).
- [ ] No call to any non-Gemini model anywhere.
- [ ] README: what it does, how to run, env vars, data sources, the Neon choice, limitations (provisional points before Cricsheet publishes; Dream11 can't be automated; Gemini can't be backtested).
- [ ] Public GitHub repo; no secrets committed.
- [ ] Components Map PNG included.

### Demo script (2 minutes, for examiners)
1. Open Upcoming: swipe left on one match, right on another.
2. Upload the Dream11 player-list screenshot; review; Build my team; watch the progress steps.
3. Team sheet reveal: tap the captain to show the reason, Gemini's sourced adjustment and factor bars.
4. Edit: swap a player to break the budget (meter turns red, Save disabled, fix hint), then fix it.
5. Open a finished match: scorecard with points ROI, efficiency, captain hit.
6. Learnings: show the accuracy chart and a suggestion with its history check; approve it; show the new rubric version.

---

## 19. Never do

- Call any model other than Gemini Flash from the app.
- Invent Dream11 values, player data, scores or news.
- Scrape or automate Dream11, ESPNcricinfo or Cricbuzz.
- Let Gemini pick players, set the captain, change weights or calculate scores.
- Save an invalid team.
- Change rubric weights without Aryan's approval.
- Duplicate `/engine` logic in `/backtest` or the frontend (the client-side gate mirror is for instant feedback only; the server is authoritative).
- Ship placeholder content.

---

## 20. Open items (confirm, don't guess)

- Gemini 3.5 Flash model ID; Google Search grounding allowance; structured-output and image-input options in the current SDK.
- CricketData.org: endpoints and fields are now confirmed from saved fixtures (see `SCORING_ENGINE.md` "Status"), including `playerImg`, `role` and `bowlingStyle`. Still open: whether `t20` career stats include T20Is, and free-tier coverage of the matches Aryan plays.
- Cricsheet register file and columns for full player names (engine fix-up 1).
- Dream11 points table and rules per format (we fill them from the app).
- How Python functions and Next.js share one Vercel project (or use two projects).
- Solver compatibility with Vercel's Python runtime.
- Bowling styles: CricketData.org squads include `bowlingStyle` for current players; historical coverage for pace vs spin pitch type still to be checked (run 2).
