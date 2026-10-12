# UI/UX Spec

**The UI is the product.** Aryan should be able to go from "which matches are on this week?" to "my team is ready" in a few swipes and taps, and trust every number on screen. Minimal screens, one clear action per screen, nothing decorative that doesn't carry meaning.

Built mobile-first (Aryan uses it on his phone before a match), fully usable on desktop.

---

## 1. Reference

- Visual reference: the Dribbble shot "Cricket World Cup Live Tracker Mobile App" (https://dribbble.com/shots/26784426-Cricket-World-Cup-Live-Tracker-Mobile-App). The page renders with JavaScript, so save a screenshot of the shot into `/design/reference/` and view it before designing.
- Use it for **mood and quality bar** (how a premium cricket mobile app feels): spacing, card hierarchy, how player imagery is used. **Do not copy its layout, colours or assets.** Our design system is defined below.
- Product feel: as quick and satisfying as a dating app's swipe deck, as trustworthy as a scoreboard.

---

## 2. Design system

### Concept: "Team sheet"

Everything in cricket that matters before a match is a sheet of paper: the fixture card, the team sheet pinned in the dressing room, the scoreboard. The app borrows those objects: a **fixture card** you swipe, a **team sheet** with player photos on a ground, a **scoreboard** for results. Each is a real cricket object, not a generic card.

**The one memorable element:** the team sheet in the Results tab, where the system's 11 appear as real player photos arranged on an oval ground, captain and vice-captain marked. Spend the boldness there; keep everything else quiet.

### Colour (named tokens)

| Token | Hex | Use |
|---|---|---|
| `sightscreen` | `#F3F5F1` | App background (cool white, like a sightscreen) |
| `pavilion` | `#16213A` | Primary text, tab bar, headers |
| `turf` | `#1E6B45` | "Play" (swipe right), confirmations, positive deltas, the ground on the team sheet |
| `ball` | `#B5172F` | Captain badge, errors, "over budget" |
| `floodlight` | `#E9B92A` | Vice-captain badge, warnings ("check this yourself") |
| `clay` | `#D9C9A3` | Provisional states, the pitch strip, subtle surfaces |
| `slate` | `#6B7385` | Secondary text, "Skip" (swipe left) |

Dark mode: swap `sightscreen` and `pavilion` roles (pavilion background, sightscreen text); keep turf, ball, floodlight, clay. Never use colour alone for meaning: captain = red **"C"** badge, vice-captain = yellow **"VC"** badge, warnings carry an icon and text.

Team colours: each team gets one colour (from a small `team_colours` setting we fill), used only as a thin stripe on fixture cards and as player ring colour on the team sheet. Do not use official team logos (they are trademarked); use short codes (IND, AUS, MI, CSK) in the team colour.

### Typography

| Role | Typeface | Notes |
|---|---|---|
| Numbers, scores, headlines | **Big Shoulders Display** (Google Fonts) | Condensed and tall like stadium scoreboards; used for points, credits, team codes, screen titles |
| Everything else | **Hanken Grotesk** (Google Fonts) | Clear at small sizes; body, labels, reasons |

Scale (mobile): 40 / 28 / 20 / 16 / 14 / 12 px. Points and credits always in Big Shoulders, tabular figures. Sentence case everywhere. No all-caps labels, no eyebrows above headings.

### Layout and motion

- Mobile: single column, 16 px side margins, bottom tab bar with 3 tabs. Desktop: left rail with the 3 tabs; content max width 1100 px; swipe deck centred.
- Corner radius by hierarchy: fixture card 24, sheets and panels 16, chips 999 (pill), inputs 12. Not one radius for everything.
- **Motion only answers actions:** card follows the finger and flies off on swipe; the team sheet's players settle onto the ground once when a team arrives (one orchestrated reveal, under 700 ms); bottom sheets slide up. No entrance animations on scroll. Respect "reduce motion": swipes become instant, the reveal becomes a fade.
- Haptic tick (where supported) on swipe commit and on save.

### Words

Plain verbs, sentence case, one job per element. Buttons say what happens: "Play this match", "Skip", "Build my team", "Save my team", "Approve change". Errors say what's wrong and how to fix it, never apologise. Empty screens invite the next action.

---

## 3. Navigation

Bottom tab bar (mobile) / left rail (desktop), 3 tabs, icon + label:

1. **Upcoming** (Upcoming Matches): swipe deck of this week's matches.
2. **Results**: teams the system built, and how they did.
3. **Learnings**: how the system is improving, and changes waiting for Aryan.

A small gear in the Learnings header opens **Settings** (Dream11 rules, points table, team colours, Gemini cap). Settings are set up by us and rarely touched by Aryan.

Badges on tabs: Results shows a dot when a team is ready, a toss refresh is available, or results are waiting to be entered. Learnings shows a count of suggestions waiting.

---

## 4. Upcoming tab: the swipe deck

### 4.1 Deck

```
┌──────────────────────────────┐
│ This week          5 matches │
│ ┌──────────────────────────┐ │
│ │▌IND  vs  AUS▐            │ │  ← team colour stripes on the edges
│ │  T20 · 2nd T20I           │ │
│ │  Wankhede, Mumbai         │ │
│ │  Sat 18 Oct · 7:00 pm     │ │
│ │  Starts in 2d 4h          │ │
│ │  ☁ 20% rain · XI not yet │ │
│ └──────────────────────────┘ │
│   ✕ Skip          ✓ Play     │  ← buttons mirror the swipe
│  Playing: IND v AUS, MI v CSK │  ← chips of matches already swiped right
└──────────────────────────────┘
```

- One fixture card at a time, the next card peeking underneath. Sorted by start time; only matches in the next 7 days (`matches` table, source CricketData.org).
- Card content: team codes (Big Shoulders, large) with team-colour stripes, format and series, venue and city, local date and time, countdown, rain chance (Open-Meteo), and XI status ("XI not yet" / "XI announced").
- **Swipe right = Play.** The card tilts and a turf-green "Play" stamp fades in as it moves right; on release past the threshold it flies off and the setup sheet (4.2) opens.
- **Swipe left = Skip.** Slate "Skip" stamp; the card flies off. A snackbar offers **Undo** for 5 seconds. Skipped matches can be restored from "Skipped (n)" at the bottom of the deck.
- Buttons below the card do the same thing (accessibility and desktop). Keyboard: ← skip, → play.
- Matches already chosen appear as chips under the deck ("Playing: ..."); tapping one opens its Results view.
- Saved to Neon `match_choices` (choice, time).

**States:**
- Loading: the card outline with the team-code positions shimmering (no spinner).
- Empty week: "No matches in the next 7 days. Next match: Tue 28 Oct, ENG vs NZ." plus a link to recent results.
- Data stale (API limit or outage): small clay chip on the deck header, "Showing saved fixtures from 9:40 am".
- View-only visitors can swipe through cards but the Play action shows "Enter passcode to play".

### 4.2 Setup sheet (after swipe right)

A bottom sheet over the deck, two steps, progress shown as "1 of 2", "2 of 2" (a real sequence).

**Step 1: Credits and roles**
- Title: "Add credits and roles from Dream11".
- Primary: **"Upload Dream11 screenshot"** (one or more images of the player list). Gemini Flash reads names, credits and roles (GEMINI_RULES.md, Job 4).
- Secondary: "Type them instead".
- Pre-fill: values from the last match with these teams are filled in and marked "from last match".
- Review table: player photo (small), name, team code, role chip (WK / BAT / AR / BOWL), credits. Every cell editable inline. Rows Gemini was unsure about are highlighted in floodlight with "Check this".
- Unmatched names: "We couldn't match 'R Sharma'. Is this Rohit Sharma (IND)?" with Yes / choose another. Saved once in `player_name_links`; never asked again.
- Button: **"Looks right"** (disabled until every player has a role and credits).

**Step 2: Build**
- Summary: "22 players · 100 credits budget · Pre-toss (XI not announced)".
- Button: **"Build my team"**.
- Then a live progress list with real steps, each ticking as it completes:
  1. Checking who can play
  2. Scoring players
  3. Reading today's news and pitch report
  4. Building the best valid team
  5. Writing the reasons
- On finish: the sheet closes and the app switches to **Results → this match** with the team sheet reveal.
- On failure: the step that failed turns red with what happened and what to do ("No valid team: only 2 wicket-keepers have credits. Check roles."). Button returns to Step 1.

---

## 5. Results tab

### 5.1 Match list

- Two segments at the top: **Upcoming** (teams built, match not yet played) and **Finished**.
- Each row: team codes, date, state chip:
  - `Provisional` (clay): built before the toss.
  - `Final` (turf): rebuilt after the toss.
  - `Toss done: refresh` (floodlight, tappable): XI announced; rebuild available.
  - `Enter results` (floodlight): match finished, Aryan's points not yet entered.
  - `Scored` (pavilion): results in, scorecard ready.
- Tap opens the match view.

### 5.2 Match view: the team sheet (hero)

```
┌──────────────────────────────┐
│ IND vs AUS     Final · T20   │
│ 812 pts expected · 99.5 cr   │
│ ┌──────────────────────────┐ │
│ │      (oval ground, turf)  │ │
│ │   WK   ◯                 │ │
│ │  BAT  ◯  ◯  ◯  ◯        │ │  ← real player photos in circles,
│ │   AR   ◯  ◯             │ │     ring in team colour
│ │ BOWL  ◯  ◯  ◯  ◯        │ │  ← C (red) and VC (yellow) badges
│ └──────────────────────────┘ │
│ [System's pick] [My final team]
│ ⚠ Check this yourself: rain  │
│   forecast 60%               │
│ Bench: 4 players ›           │
│ Copy to Dream11 ›            │
└──────────────────────────────┘
```

- **Oval ground** in turf with a clay pitch strip down the middle. Players sit in rows by Dream11 role (WK, BAT, AR, BOWL), like a team sheet.
- **Each player:** circular **real photo**, ring in his team's colour, surname below, expected points below that (Big Shoulders). Captain has a red **C** badge, vice-captain a yellow **VC** badge, both slightly larger.
- **Header:** match, `Provisional`/`Final` chip, total expected points (with C 2x and VC 1.5x), credits used out of budget.
- The 11 shown are **the system's selected team** for this match; the label "Picked by the system" sits under the ground on the System's pick subtab.
- **Reveal:** on first open after a build, players settle onto the ground row by row, captain last (one orchestrated moment, under 700 ms).

**Player photos (rules):**
- Source: CricketData.org's `playerImg` field (confirmed in squad and player info data), cached in `players.image_url`. Its generic placeholder (`https://h.cricapi.com/img/icon512.png`) means no photo: store null and show the initials avatar. Only use images supplied by our data provider under its terms; do not scrape other sites.
- Fallback when no image: initials on the team colour, same circle size, so the sheet never looks broken.
- Photos load lazily with a fixed-size placeholder (no layout shift).

**Warnings banner** ("Check this yourself"), floodlight, only when triggered: XI not confirmed, rain forecast, 3+ thin-data picks, Gemini wanted to go beyond ±20%. Each reason is listed in plain words.

### 5.3 Player detail (tap a player)

Bottom sheet:
- Photo, name, team, role, credits.
- **Expected points:** large number. Beneath: "Base 42 → Gemini −10% → 37.8".
- **Why he's picked:** Gemini's one line (2 to 3 lines for C and VC).
- **Gemini's adjustment** (if any): reason + source link ("Read source"), opens in a new tab.
- **What the numbers say:** 8 horizontal bars, one per factor (form, venue, opponent, current touch, opportunity, career, batting first or chasing, pitch type), each showing the factor value in points; bars with low trust are drawn in clay with "few matches" beside them.
- Thin-data chip if fallback step 2 to 4 was used: "Little history: estimate from other formats" (or the step's plain-English name).

### 5.4 Subtabs: System's pick | My final team

- **System's pick:** read-only team sheet as above.
- **My final team:** starts as a copy of the system's pick. Tap a player → "Swap" → list of eligible replacements sorted by expected points, each showing credits and the effect: "+3.5 cr · −6 pts". Tap the C or VC badge area to change captaincy.
- **Live validity meters** pinned at the top while editing:
  - Credits: bar fills toward the budget, turns ball-red when over ("1.5 over").
  - Roles: WK / BAT / AR / BOWL counters, each showing min–max; out-of-range counter turns red.
  - Per side: "IND 6 · AUS 5" with the cap.
- **Save my team** is disabled while invalid; the first failing rule is shown in one line with the fix ("1.5 credits over: swap a player for a cheaper one").
- Optional "Why the change?" text field (one line). Saved to `overrides`.
- Changed players show a small "Your pick" tag on the sheet.

### 5.5 Bench

- "Bench: 4 players" opens a sheet with 4 rows: photo, name, expected points, and the real reason ("Would put you 1.5 credits over", "Fits, but the team scores 6 points less").

### 5.6 Copy to Dream11

- A checklist screen for entering the team in the Dream11 app by hand: players grouped by role in the same order Dream11 shows them, each with a checkbox; captain and VC listed first in large type.
- Note at the top: "The app can't submit to Dream11. Tick each player as you add him."

### 5.7 Toss refresh

- When the XI is announced, the match row shows `Toss done: refresh`. The match view shows a floodlight banner: "XI announced. Rebuild with the confirmed players?" → **Rebuild team** → same progress list → reveal with `Final`.
- If Aryan has edits, ask: "Keep your edits where possible?" (players still in the XI are kept; the gate re-checks).

### 5.8 Enter results (after the match)

- Match row shows `Enter results`. Screen: **"Upload Dream11 points screenshot"** (Gemini Job 4 reads player points and Aryan's rank) or "Type them".
- Review table with editable cells; then **Save results**.
- If our calculator disagrees with Aryan's numbers for any player: a clear note, "Our calculation differs for 2 players. Check the points table in Settings." (logged; does not block saving).

### 5.9 Scorecard (after results)

The match view gains a **Scorecard** section, styled like a scoreboard:
- Big numbers: system's team points, Aryan's final team points, simple team points.
- **Points ROI:** system minus simple, with a turf ▲ or ball-red ▼.
- **Efficiency:** system ÷ perfect team, as a percentage with a thin bar.
- **Captain hit:** "Captain was 2nd top scorer" or "Captain finished 9th".
- **Your swaps:** for each override, "You swapped A for B: B scored 14 more" (or fewer).
- **Predicted vs actual:** list of the 11 with two bars each (predicted clay, actual turf); real misses marked.
- Note when actual points are still approximate: "Approximate until full match data arrives (usually a few days)."

---

## 6. Learnings tab

### 6.1 Top: how the system is doing

- Line chart: average prediction miss (points) per match over time, per format (filter chips: T20 / ODI / Test, men / women).
- Small figures: matches scored, points ROI to date, captain hit rate, current rubric version ("v3, approved 12 Oct").

### 6.2 Waiting for you (suggestions inbox)

Cards, newest first. Three kinds, same layout:

1. **Weight change** (from the Gemini analyst):
   - Pattern in one sentence: "We overrate openers when chasing by 12 points on average (11 matches)."
   - Proposal: "Batting first or chasing: 0.15 → 0.10".
   - History check: turf "Supported by past matches: miss drops from 18.2 to 16.9" or slate "Not supported by history".
   - Buttons: **Approve change** · **Edit** (number stepper, warning beyond ±0.10) · **Reject**.
2. **Rollback:** "Since v3, predictions got worse. v2 would have missed by 2.1 fewer points." Buttons: **Roll back to v2** · **Keep v3**.
3. **Gemini's limit:** "Over 20 matches, Gemini's changes made predictions worse 13 times." Buttons: **Lower limit to ±10%** · **Keep ±20%**.

Approve/reject use buttons, not swipes: these decisions change the model, so they need a deliberate tap. Each decision shows a snackbar ("Change approved. v4 is live from the next match.").

Empty state: "Nothing to review. The system flags a pattern after 10 matches of similar misses."

### 6.3 Groups

List of watched groups per format (player role, batting position band, batting first vs chasing, pitch type/venue), each with a status: "Watching (6 of 10 matches)", "Flagged", "Fine".

### 6.4 Rubric history

Timeline of versions: v1 (backtest), v2, v3... Each shows date, who approved, and the weight changes as before → after. Tap for the full weight table.

---

## 7. Settings (gear in Learnings)

- Dream11 rules per format (budget, role min/max, per-side cap, C/VC multipliers).
- Dream11 points table per format.
- Team colours.
- Gemini cap (±20% default).
- All values editable only with the passcode; every change logged.

---

## 8. Global states and quality floor

- **Loading:** skeletons shaped like the real content (fixture card outline, ground with empty circles). No full-screen spinners.
- **Errors:** inline, specific, with the fix. Never "Something went wrong".
- **Offline / API limit:** show cached data with the time it was saved.
- **View-only mode:** a small "View only" chip in the header; action buttons ask for the passcode.
- **Accessibility:** every swipe has a button and a keyboard equivalent; visible focus rings; colour never the only signal; contrast at least WCAG AA; tap targets at least 44 px; photos have alt text (player name).
- **Performance:** first screen interactive fast on a mid-range phone; images lazy-loaded and sized; no layout shift.
- **Responsive:** phone first; tablet and desktop get the left rail and wider panels, same flows.

---

## 9. Screen-to-data map (for building)

| Screen element | Data |
|---|---|
| Fixture cards | `matches`, `venues`, `teams`, Open-Meteo via `api_cache` |
| Setup review table | `credits`, `players`, `player_name_links` |
| Progress list | `runs.status` updates |
| Team sheet | `teams_picked`, `predictions`, `players.image_url` |
| Player detail | `predictions` (factors, trust, fallback), `gemini_adjustments`, `explanations` |
| Bench | `bench`, `explanations` |
| My final team | `overrides`, gate results |
| Results entry | `results` |
| Scorecard | `metrics`, `player_match_points` |
| Learnings | `metrics`, `patterns`, `weight_suggestions`, `rubric_versions` |

Table and column names: see `NEON_SCHEMA.md`.
