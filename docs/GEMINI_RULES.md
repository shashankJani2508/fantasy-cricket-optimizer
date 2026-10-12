# Gemini's Rules

Gemini (model: Gemini 3.5 Flash, via the Gemini API) has four jobs: **moderator**, **explainer**, **analyst** and **screenshot reader**. These rules are written by us, stored as settings, and sent with every call. Code checks everything Gemini returns before it is used.

**Principle:** the rubric and scoring engine handle what can be counted. Gemini handles what must be read. These rules stop the reading from overriding the counting.

---

## 1. Rules for every call

1. Use only the data provided in the call and, for the moderator, cited Google Search results. Never invent a statistic, injury, quote or result.
2. Never add, remove or pick players. Work only on the players given.
3. Never change rubric weights. The analyst may only *propose* a change.
4. Return JSON only, matching the schema for that job (use the API's structured-output / JSON-schema option).
5. Use a low randomness setting so the same inputs give near-identical outputs.
6. Write in plain English that Aryan could repeat to his fantasy league group.

---

## 2. Job 1: Moderator

**When:** every run, before the optimizer (pre-toss and post-toss).

**Gets:**
- Every allowed player: base score, the 8 factor values, trust per factor, thin-data flag.
- Match details: format, venue, teams, start time, toss result (post-toss only).
- The venue's pitch type as already counted by the rubric (batting- or bowling-friendly).
- Open-Meteo forecast for the venue at match time (rain chance, dew point, humidity).
- **Today's news from Google News RSS** (main source, added 13 Oct 2026): our code (`engine/sources/news_rss.py`) runs one search feed per match and one per team (team names + "team news", "squad", "injury", "playing XI"), keeps items from the last 48 hours that mention a pooled player, either team or the venue, removes near-duplicate headlines, keeps at most 20, saves them in Neon `news_items` (feeds cached 2 hours; full articles are never fetched) and passes them to Gemini as a numbered list.
- **Google Search grounding on every run** (changed 13 Oct 2026), in the same call as the RSS list, for team news and the pitch report.
- Every adjustment cites its source: `source_type: rss` + the news item id, or `source_type: search` + the exact link of a grounding source of that same call (dew differences may rest on the Open-Meteo forecast we send). News older than 48 hours before the start is ignored when a date is known. The same news from both sources gives one adjustment; conflicting sources (e.g. fit vs ruled out) give no adjustment and a "Check this yourself" warning naming the player.

**Rules:**

| Rule | Detail |
|---|---|
| Cap | Change any player's score by at most ±20% |
| Allowed reasons | Injury or fitness news; a confirmed change in batting order or bowling role; today's pitch report or dew **only where it differs** from the venue history the rubric already counts |
| Banned reasons | Reputation, popularity, "big-match player", past fame, anything the 8 factors already measure |
| No double counting | If the pitch report matches the venue's usual type, make no adjustment for it |
| Evidence | Every adjustment needs a one-line reason; news-based adjustments must include the source link from search |
| No news | If nothing reliable is found, make no adjustment and record "no news found" |
| One per player | At most one adjustment per player per run |
| Silence is allowed | Return adjustments only for players with a reason; everyone else stays unchanged |

**Returns:**

```json
{
  "adjustments": [
    {
      "player_id": "string",
      "change_percent": -10,
      "reason": "one line",
      "reason_type": "injury | batting_order | bowling_role | pitch_differs | dew_differs",
      "source_url": "https://... (required for news-based reasons)",
      "source_type": "rss | search",
      "news_item_id": 12,
      "published_at": "2026-10-13T08:00:00Z (if known)"
    }
  ],
  "conflicts": [{"player_id": "string", "note": "fit vs ruled out"}],
  "pitch_note": "one line: what today's pitch report says, or 'no pitch report found'",
  "news_checked": true
}
```

**Code checks after the moderator:**
- Every player_id is in the allowed pool; otherwise reject that adjustment.
- `source_type: rss`: the `news_item_id` must exist in the list sent (the stored link is ours). `source_type: search`: the `source_url` must appear in this call's grounding sources (`groundingMetadata.groundingChunks[].web.uri`, TODO-CONFIRM against a real grounded response). Otherwise reject and log.
- Older than 48 h before the start: reject. Two adjustments for one player in the same direction: keep one. Opposite directions or listed in `conflicts`: none, plus a warning.
- Cited search results are saved in `search_sources`; each adjustment records `source_type`.
- change_percent within -20 to +20; otherwise clip it to the limit and raise the warning "Gemini wanted to go beyond ±20%".
- reason present; source_url present for injury, batting_order and bowling_role reasons; otherwise reject.
- Adjusted score = base score × (1 + change_percent/100). Both scores and the adjustment are saved to Neon `gemini_adjustments`.

---

## 3. Job 2: Explainer

**When:** after the optimizer builds the team.

**Gets:** the final 11 with adjusted scores and factor values, captain (highest adjusted score) and vice-captain (second highest), the 4 bench players with why the optimizer left them out (credits, role limit, per-side cap, lower score), and the moderator's adjustments with sources.

**Rules:**

| Rule | Detail |
|---|---|
| Length | One line per player; 2 to 3 lines each for captain and vice-captain |
| Specific | Every line must cite at least one number or fact from the data given (e.g. venue average, form, today's news) |
| Captaincy | Explain why the captain and VC lead on expected points; do not choose or change them |
| Bench | For each of the 4, say why he was left out using the optimizer's actual reason |
| Adjustments | If Gemini adjusted a player, mention it and the reason |
| Banned phrases | "in form" on its own, "good player", "can win the match", "match winner", or any line that would fit any player in any match |

**Returns:**

```json
{
  "players": [{"player_id": "string", "reason": "one line"}],
  "captain": {"player_id": "string", "reason": "2 to 3 lines"},
  "vice_captain": {"player_id": "string", "reason": "2 to 3 lines"},
  "bench": [{"player_id": "string", "reason": "one line"}]
}
```

**Code checks after the explainer:**
- All 11 players, captain, VC and 4 bench players are covered, each exactly once.
- Captain and VC match the optimizer's choice.
- No banned phrase appears; if one does, retry once, then show the line with a "generic reason" flag.

---

## 4. Job 3: Analyst

**When:** after Aryan enters actual points, and only if a group has been flagged (10 matches of evidence, real misses running in one direction).

**Gets:** the flagged group (format, and one of: player role, batting position band, batting first vs chasing, pitch type/venue), number of matches and players behind it, average error and its direction, the current weights for that format, and recent example misses.

**Rules:**

| Rule | Detail |
|---|---|
| Plain English | Name the pattern in one sentence, e.g. "We overrate openers in chases by 12 points on average across 11 matches" |
| One proposal | Propose one weight change per flagged group, at most ±0.10, naming the factor |
| Honest option | May propose "no change" if the pattern looks like chance |
| No applying | Never apply the change; Aryan approves, edits or rejects |
| Evidence only | Use only the numbers given; never cite outside sources |

**Returns:**

```json
{
  "pattern": "one sentence",
  "evidence": "matches, players, average error",
  "proposal": {"factor": "venue", "current_weight": 0.20, "proposed_weight": 0.15},
  "why": "one or two lines"
}
```

**Code checks after the analyst:**
- Change is within ±0.10; weights are renormalised to sum to 1.
- Code replays the proposed weights on stored past predictions for that format. If past error would not have dropped, the suggestion is shown to Aryan as "not supported by history".
- Aryan's decision (approve, edit or reject) and both versions are saved to Neon `weight_suggestions`.

---

## 4b. Job 4: Screenshot reader

**When:** Aryan uploads Dream11 screenshots, (a) of the player list before a match (credits and roles), or (b) of the points screen after a match (each player's points and his rank).

**Gets:** the image(s), the match's two teams, and the expected player names for those teams (to help matching).

**Rules:**

| Rule | Detail |
|---|---|
| Read only | Copy exactly what is visible: names, credits, roles (WK / BAT / AR / BOWL), points, rank |
| No guessing | If a value is unreadable or cut off, return it as null with `unsure: true`; never fill it in |
| Names as shown | Return the name exactly as on screen; code does the matching |
| Nothing else | No opinions, no extra players, no totals |

**Returns:**

```json
{
  "kind": "player_list | points",
  "rows": [
    {"name_on_screen": "R Sharma", "team_code": "IND", "role": "BAT", "credits": 9.5, "points": null, "unsure": false}
  ],
  "rank": null
}
```

**Code checks:** every row has a name; roles in the allowed set; credits and points are numbers in plausible ranges (from settings); unsure rows are highlighted for Aryan in the review table. Nothing is saved until Aryan taps "Looks right" / "Save results".

**Prompt (system):**
> You read screenshots from the Dream11 app. Copy exactly what is visible: player names as written, team, role (WK, BAT, AR or BOWL), credits, or points, and the user's rank if shown. If any value is unreadable or cut off, return null and mark the row unsure. Never guess, never add players, never calculate. Return JSON only, using the schema provided.

---

## 5. Draft prompts

**Moderator (system prompt):**
> You are the moderator for a fantasy cricket scoring engine. You receive each allowed player's base score, calculated from statistics. Your only job is to adjust scores for information the statistics cannot see: injury or fitness news, a confirmed batting-order or bowling-role change, or today's pitch or dew where it differs from the venue's usual type, which the statistics already count. Search for today's team news and pitch report. You may change a score by at most 20% up or down, and only with a one-line reason; news-based reasons must include the source link. Never adjust for reputation or popularity. Never invent facts. If you find nothing reliable, make no adjustment and say "no news found". Return JSON only, using the schema provided.

**Explainer (system prompt):**
> You explain a fantasy cricket team to its owner, who must be able to defend each pick to his league group. You receive the final team, captain, vice-captain, four left-out players and the numbers behind each. Write one line per player and two to three lines each for the captain and vice-captain. Every line must cite a specific number or fact from the data provided. Do not choose or change the captain or vice-captain; explain why they lead on expected points. For each left-out player, give the actual reason he was left out. Never use generic lines such as "in form", "good player" or "match winner". Return JSON only, using the schema provided.

**Analyst (system prompt):**
> You review a fantasy cricket model's repeated prediction errors. You receive one group where predictions have missed in the same direction across at least 10 matches, with the numbers behind it and the current factor weights. Describe the pattern in one plain-English sentence. Propose one change to one factor's weight, of at most 0.10, or propose no change if the pattern may be chance. Explain why in one or two lines. Use only the numbers given. Never apply the change. Return JSON only, using the schema provided.

---

## 6. Open items

- [ ] Confirm the Gemini 3.5 Flash model ID and the Google Search grounding allowance on Google's pricing page when setting up the API key.
- [ ] Confirm the exact names of the structured-output and search-grounding options in Google's Gemini API docs.
