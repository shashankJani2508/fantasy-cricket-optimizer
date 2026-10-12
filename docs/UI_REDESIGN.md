# UI Redesign: match the reference

**This file replaces the visual design in `UI_UX.md` section 2** (colours, type, look). The flows, screens, states and words in `UI_UX.md` stay the same. Where they disagree on how something looks, this file wins.

**Reference:** `design/reference/dribbble-reference.png` (Dribbble: "Cricket App UX Exploration, ICC Men's World Cup 2023", https://dribbble.com/shots/22764793-Cricket-App-UX-Exploration-ICC-Men-s-World-Cup-2023). Open the image and study it before writing any code. The goal is that a screenshot of our app could sit next to it and look like the same family of product.

---

## 1. What makes the reference great (copy these qualities, not its assets)

1. **Dark and cinematic.** Near-black backgrounds with deep colour glows (maroon, navy, violet). Light comes from the content, not the background.
2. **Image-led.** Big player imagery and match artwork dominate; text sits on top of images under dark gradient overlays.
3. **One loud accent.** A saturated red for the primary action (Continue, Live, Book Ticket). Everything else is white, grey or image.
4. **Bold numbers.** Scores, overs and stats are large, bold and white; labels are small and grey.
5. **Rounded, layered cards.** Large radii (24 to 32 px), cards slightly lighter than the background, soft shadows, glassy overlays.
6. **Pill controls.** Buttons, tabs (Live / Scorecard / Commentary) and badges are pills.
7. **Story circles.** A horizontal row of circular match avatars with gradient rings, like Instagram stories.
8. **Phone-first.** Designed as a phone app; nothing looks stretched.

Do not copy: its photographs, illustrations, ICC branding, team logos or layout pixel-for-pixel. We recreate the **quality and style** with our own content.

---

## 2. Design tokens (replace the old palette)

| Token | Value | Use |
|---|---|---|
| `bg` | `#0A0B10` | App background |
| `bg-glow-1` | `#3A0E1C` (maroon) | Radial glow, top-left of screens |
| `bg-glow-2` | `#1A1F4A` (deep navy-violet) | Radial glow, bottom-right |
| `surface` | `#15171F` | Cards |
| `surface-2` | `#1F2230` | Raised elements, inputs, inactive pills |
| `glass` | `rgba(255,255,255,0.06)` + `backdrop-filter: blur(16px)` + 1 px border `rgba(255,255,255,0.08)` | Sheets, overlays on images |
| `text` | `#F5F6F8` | Primary text and numbers |
| `muted` | `#9AA0AE` | Labels, secondary text |
| `red` | `#E8172C` | **Primary action only**: Play this match, Build my team, Save, Continue; LIVE pill |
| `orange` | `#FF7A1A` | "VS", countdowns, highlights |
| `gold` | `#F5B700` | Captain badge "C" |
| `silver` | `#D6DCE6` | Vice-captain badge "VC" |
| `green` | `#2BB673` | Positive deltas, "Supported by history", success |
| `amber` | `#FFB020` | Warnings ("check this yourself") |

Team colours (`team_colours` setting, **must be filled**; grey stripes mean it's empty): used for card gradients, story rings and player-photo rings.

**Gradients:**
- Screen background: `bg` with two large soft radial glows (`bg-glow-1` top-left, `bg-glow-2` bottom-right), very low opacity.
- Image overlay: transparent → `bg` at 90% from 40% height to bottom, so text on images is always readable.
- Match card art: a diagonal split blend of the two teams' colours with soft brush-like noise, plus a stadium-floodlight glow (CSS radial gradients and an SVG noise texture; no stock photos).
- Story ring: conic gradient of the two teams' colours.

**Type:**
- Headings and numbers: **Outfit** (Google Fonts), weights 600 to 800. Scores and points always tabular figures.
- Body: **Plus Jakarta Sans** (Google Fonts), 400 to 600.
- Sizes (mobile): 34 / 26 / 20 / 16 / 14 / 12. Large bold white numbers, small grey labels.

**Shape and depth:** cards radius 28; sheets 32 (top corners); pills full; avatars circular. Shadow: `0 20px 40px rgba(0,0,0,0.45)`. Spacing on an 8 px grid; 20 px screen margins.

**Icons:** one consistent outline set (e.g. Lucide), 1.75 px stroke, white or muted.

---

## 3. Layout on every device

- **Phone:** full-screen app, bottom tab bar (glass, floating, pill-shaped, 3 tabs with icon + label; active tab in white with a red dot).
- **Tablet and desktop:** the app sits in a **centred phone-width column (max 440 px)** on top of the dark glowing background, like the device mockups in the reference. No stretched layouts, no empty half-screens. Optional: a soft-focus enlarged version of the current match artwork behind the column.

---

## 4. Imagery rules

- **Player photos** (`engine/photos.py`, `python -m engine.cli photos --squads`): 1) CricketData.org `playerImg` unless it is the generic placeholder (`https://h.cricapi.com/img/icon512.png`); 2) else Wikimedia Commons via Wikidata, accepted only when the name matches exactly, the occupation is cricketer, the country matches and exactly one candidate remains, and the licence is public domain, CC0, CC BY or CC BY-SA; 3) else no photo. The player sheet shows "Photo: author, licence" linking to the Commons page, and Settings → Credits lists every Wikimedia photo used.
- **No photo:** initials in Outfit on a team-colour gradient circle, same size, same ring, so it never looks broken.
- **Photos on cards:** circular crops with a 2 px team-colour ring and a soft glow; on hero cards, the two highest-scoring players' photos overlap slightly, larger, with a dark gradient beneath.
- **Countries:** flag icons from an open-licence flag set (e.g. the `flag-icons` package), shown in circles. **Franchise teams** (IPL, BBL…): a monogram (short code) on the team colour. Never use official team or league logos.
- **No stock or copyrighted photos** besides provider player images. Atmosphere comes from gradients, glows and noise textures.

---

## 5. Screen by screen

### 5.0 Welcome (first visit only)

Three swipeable slides like the reference's onboarding: full-height artwork (team-colour gradients, glow, our generic cricket illustration built from shapes), title in Outfit 28 bold, one line of body, page dots, red **Continue** pill at the bottom.
1. "Your match day, sorted" — Swipe through this week's matches.
2. "A team you can defend" — Every pick comes with a reason.
3. "Gets sharper every match" — It learns from your results.
Stored in local preference so it shows once; "Skip" top-right.

### 5.1 Upcoming

- **Header:** "This week" (Outfit 26 bold) and a count chip ("5 matches") that never overflows; on small widths it wraps under the title.
- **Story row:** horizontal scroll of circular match avatars (two flags or monograms split diagonally inside the circle), team-colour conic ring, label "PAK v SL" beneath. Tapping one jumps the deck to that match. Matches already chosen get a small red check.
- **Swipe card (hero):** ~70% of the screen height, radius 28, the match-card art (team-colour diagonal blend + floodlight glow). On top:
  - Top row: format pill ("T20I"), status pill (red **LIVE** if live; otherwise orange countdown "Starts in 23h 46m").
  - Middle: two large flag/monogram circles with team codes beneath, a big orange **VS** between them; if photos exist, the top player of each side appears as an overlapping circular photo above the flags.
  - Bottom (on the dark overlay): series name (one line, truncated), venue, local date and time, and small chips: rain chance, "XI not yet" / "XI announced".
  - While dragging: card tilts up to 12°; a green "PLAY" or grey "SKIP" stamp fades in on the corner.
- **Below the card:** two circular buttons like a dating app: grey ✕ (Skip) and large red ✓ (Play), with a small hint "Swipe or use ← →".
- **Empty week:** a single designed card: "No matches in the next 7 days" + next match date + link to Results.

### 5.2 Setup sheet (after swipe right)

A glass bottom sheet with a drag handle; step dots "1 of 2".
- Step 1: big upload area (dashed rounded rectangle, camera icon) "Upload Dream11 screenshot"; secondary text button "Type instead". The review table is a list of dark rows: photo, name, team monogram, role pill (WK / BAT / AR / BOWL in `surface-2`), credits in Outfit bold on the right. Unsure rows have an amber left bar and "Check this". Red **Looks right** pill pinned at the bottom.
- Step 2: summary chips, then red **Build my team**. Progress: five rows with circular step icons that fill and tick in sequence (animated), labels in Plus Jakarta Sans.

### 5.3 Results: team sheet (the hero moment)

- **Top:** match header like the reference's match coverage card: two flags with codes, orange VS, status pill (`Provisional` amber / `Final` green), expected total points in Outfit 34 bold, credits used "99.5 / 100".
- **Pill tabs** (like Live / Scorecard / Commentary): **System's pick · My final team · Scorecard** (Scorecard appears after results).
- **The ground:** a dark-green oval with a soft floodlight vignette and a pale pitch strip, inside a rounded card. Players in rows by role (WK, BAT, AR, BOWL; small muted row labels at left). Each player: 56 px circular photo with team-colour ring and glow, surname below (Plus Jakarta 12), expected points below that (Outfit 14 bold). Captain: gold "C" badge and a gold ring; vice-captain: silver "VC". "Picked by the system" caption beneath.
- **Reveal:** players fade and scale in row by row (WK → BOWL), captain last with a short gold pulse; under 700 ms total; respects reduced motion.
- **Below the ground:** amber warning card if needed; "Bench" row (four small overlapping photos + "4 left out ›"); "Copy to Dream11 ›" row.

### 5.4 Player detail

Glass sheet: large photo (96 px) with ring, name (Outfit 22), team and role pills, credits. Expected points huge (Outfit 34) with "Base 42 → Gemini −10% → 37.8" beneath in muted text. Reason in body text. Gemini adjustment as a small card with a link "Read source ↗". Factor bars: thin rounded bars on `surface-2`, filled white (low-trust ones in muted with "few matches").

### 5.5 My final team (editing)

Same ground; tapping a player opens a replacement list (dark rows with photo, name, credits, points, and the effect "+3.5 cr · −6 pts" in green/red). Sticky glass meter bar at the top: credits progress bar (turns red when over), role counters as small pills, per-side counter. Red **Save my team** pill; disabled state is `surface-2` with the fix hint above it.

### 5.6 Scorecard

Styled like the reference's batters/bowlers tables: dark card, column headers small and muted (Pred · Actual · Diff), player rows with small photo, numbers right-aligned in Outfit. Top summary: three big numbers (System · Your team · Simple team) and chips for Points ROI (green ▲ / red ▼), Efficiency, Captain hit.

### 5.7 Learnings

- Accuracy chart: dark card, smooth line in white with an orange end dot, muted grid.
- **Suggestions** as a horizontal carousel of tall cards (like the reference's "Trending Now"): gradient header art (format colours), pattern sentence, "0.15 → 0.10" in Outfit bold, history check chip, and pill buttons **Approve** (red) · Edit · Reject.
- Rubric history as a vertical timeline with glowing dots.

---

## 6. Motion

- Swipe deck: card follows the finger with spring physics; tilt; flies off; next card scales up from 0.95.
- Story row: active ring rotates slowly while a run is in progress.
- Sheets slide up with a spring; backgrounds dim.
- One orchestrated reveal on the team sheet. No other entrance animations.
- Respect `prefers-reduced-motion`.

---

## 7. Quality bar (check every screen against these)

- [ ] Side by side with the reference image, it looks like the same quality of product.
- [ ] Dark background with glows; no flat white screens anywhere.
- [ ] Red used only for the main action and LIVE.
- [ ] Every match card has team-colour art; no grey stripes (fill `team_colours`).
- [ ] Every player appears as a photo or a designed initials avatar; no broken images.
- [ ] Numbers big and bold; labels small and muted.
- [ ] Nothing overflows or truncates badly at 360, 390 and 430 px widths ("1 match" chip included).
- [ ] Desktop shows the centred phone column on the glowing background, not a stretched layout.
- [ ] Contrast meets WCAG AA on dark (muted text on `surface` included).
- [ ] Every swipe has a button and keyboard alternative.
