# Backtest: Components Map and Mind Map

Companion to the backtest prompt. Purpose: produce **rubric v1** (factor weights per format group) from past matches, prove the factors beat a form-only baseline, and seed the Learnings tab with history. Pure data processing, no AI API. Runs once before launch, and again whenever weights are refreshed (e.g. a new season).

File paths below are a suggested structure; adjust if the repo already has conventions.

---

## 1. Components map

```mermaid
flowchart TD
    subgraph SRC["Sources"]
        CS["Cricsheet.org<br/>ball-by-ball JSON, all formats"]
        PT["config/dream11_points.yaml<br/>filled by us from the Dream11 app<br/>script refuses to run if any value is null"]
        CFG["config/backtest.yaml<br/>window 3y, warm-up 6m, thin-data 10,<br/>pitch min 5, split 70/30, rounding 0.05"]
    end

    subgraph PREP["Preparation"]
        DL["download.py<br/>download once, cache in /backtest/data"]
        PARSE["parse.py<br/>matches, innings, deliveries, players;<br/>map match types to T20 / ODI / Test x men / women"]
        EXC["exclusions<br/>drop reduced-overs, DLS, no-result matches;<br/>drop retired-hurt player rows"]
        PTS["engine/points.py (shared)<br/>actual Dream11 points per player per match:<br/>batting + bowling + fielding"]
    end

    subgraph FACT["Factor building (no peeking)"]
        F["engine/factors.py (shared with live app)<br/>form, venue, opponent, current_touch,<br/>opportunity, career, bat_first_or_chase, pitch_type"]
        THIN["thin-data rule<br/>trust = min(n/10, 1)<br/>value = trust x factor + (1 - trust) x form"]
        COLD["cold start<br/>fewer than 3 earlier matches: excluded, counted"]
    end

    subgraph FIT["Fitting, per format group"]
        SPLIT["chronological split<br/>older 70% fit, newer 30% test"]
        OPT["fit.py<br/>minimise mean absolute error,<br/>weights >= 0, sum to 1 (SLSQP)"]
        RND["round to 0.05, renormalise"]
        ABL["ablation<br/>factor not helping on test set -> weight 0"]
        BASE["baseline check<br/>full rubric vs form only, test MAE"]
    end

    subgraph OUT["Outputs"]
        N1[("Neon: bt_player_match_points")]
        N2[("Neon: bt_predictions<br/>factors, predicted, actual, error,<br/>is_real_miss, split")]
        N3[("Neon: rubric_versions<br/>v1 weights per group, MAEs,<br/>approved_by NULL")]
        REP["backtest_report.md<br/>coverage, mapping, exclusions, cold-start,<br/>MAE vs baseline, weights, dropped factors, limits"]
    end

    TEST["tests/test_no_peeking.py<br/>factors only see matches dated before the match"]

    CS --> DL --> PARSE --> EXC --> PTS
    PT --> PTS
    PTS --> N1
    PTS --> F
    CFG --> F
    F --> THIN --> COLD --> SPLIT
    SPLIT --> OPT --> RND --> ABL --> BASE
    BASE --> N2
    BASE --> N3
    BASE --> REP
    TEST -.guards.-> F
```

### Component table

| Component | Suggested file | Input | Output | Rules |
|---|---|---|---|---|
| Downloader | `backtest/download.py` | cricsheet.org | JSON files in `/backtest/data` | Download once; never re-download if present |
| Parser | `backtest/parse.py` | Cricsheet JSON | Matches, deliveries, players with format group and gender | Print the match-type mapping used |
| Exclusions | `backtest/parse.py` | Parsed matches | Clean match set | Drop reduced-overs, DLS, no-result; drop retired-hurt player rows; document detection rule |
| Points calculator | `engine/points.py` **(shared)** | Deliveries + `dream11_points.yaml` | Actual points per player per match (batting, bowling, fielding, total) | No values from memory; refuse to run on nulls; list point types Cricsheet cannot derive |
| Factor builder | `engine/factors.py` **(shared)** | Earlier matches only | 8 factor values per player per match | Same format group; definitions below; live app imports this module |
| Thin-data rule | `engine/factors.py` | Factor average + match count n | Blended value | trust = min(n/10, 1); n = 0 -> form; applies to venue, opponent, opportunity, bat_first_or_chase, pitch_type |
| Cold start | `backtest/run_backtest.py` | Player history | Included / excluded flag | Fewer than 3 earlier matches -> excluded and counted |
| Splitter | `backtest/fit.py` | Evaluated rows | Fit set, test set | Chronological 70/30; warm-up 6 months never evaluated |
| Weight fitter | `backtest/fit.py` | Fit set | Weights per group | Minimise MAE; weights >= 0, sum to 1; round to 0.05 |
| Ablation + baseline | `backtest/fit.py` | Test set | Final weights, MAEs | Drop factors that don't help; compare to form-only |
| Writer | `backtest/run_backtest.py` | All results | 3 Neon tables + report | `DATABASE_URL` from env, never hardcoded |
| No-peeking test | `tests/test_no_peeking.py` | Factor functions | Pass / fail | Factors receive only matches dated strictly before the match |

### Factor definitions (each = player's average Dream11 points in situation X, same format group, earlier matches only)

| Factor | Definition | Thin-data rule? |
|---|---|---|
| form | Last 10 matches; most recent 5 weighted double | No (it is the fallback) |
| venue | Average at this venue | Yes |
| opponent | Average against this opposing team | Yes |
| current_touch | Last 5 matches in other formats within 30 days; ratio = points / his average in that format; value = form x mean(ratio); none -> form | No |
| opportunity | Average in matches where batting band (1-3, 4-5, 6-7, 8+) and bowling band (none / under half quota / half or more) match his usual bands (most frequent in last 10) | Yes |
| career | Average over all earlier matches in the window | No |
| bat_first_or_chase | Average when his team batted first vs chased, matching this match's actual situation | Yes |
| pitch_type | Venue = batting- or bowling-friendly by average first-innings score vs format average (needs 5+ earlier matches, else unknown -> form); average at venues of same type | Yes |

---

## 2. Mind map

```mermaid
mindmap
  root((Backtest for rubric v1))
    Purpose
      Set starting weights per format group
      Prove factors beat form-only baseline
      Seed Learnings tab with history
      Learning loop improves weights after launch
    Data
      Cricsheet ball-by-ball JSON
      All formats, men and women separately
      Last 3 years
      First 6 months warm-up only
    Dream11 points
      Filled by us from the Dream11 app
      Never guessed
      Script refuses to run on missing values
      Report lists points Cricsheet cannot derive
    Factors
      Form, last 10, last 5 double
      Venue
      Opponent
      Current touch, other formats, last 30 days
      Opportunity, batting and bowling bands
      Career average
      Batting first or chasing
      Pitch type, batting or bowling friendly
    Rules
      No peeking, earlier matches only
      Thin data, full trust at 10 matches
      Cold start, fewer than 3 matches excluded
      Exclude reduced overs, DLS, no result
      Exclude retired hurt rows
    Fitting
      Chronological split 70 fit 30 test
      Minimise mean absolute error
      Weights non negative, sum to 1
      Round to 0.05
      Ablation drops useless factors
    Outputs
      Neon bt_player_match_points
      Neon bt_predictions
      Neon rubric_versions v1
      backtest_report.md
    Shared code
      engine points.py
      engine factors.py
      Live scoring engine imports the same modules
    Limits
      Gemini not tested, past news not recreatable
      Optimizer not tested, past credits unavailable
      Tests and women's groups may have thin data
      Bowlers injured mid match not detectable
```

---

## 3. Run order

1. Fill `config/dream11_points.yaml` from the Dream11 app (one section per format).
2. Set `DATABASE_URL` to the Neon connection string.
3. Claude Code shows its plan and the Cricsheet fields it will use; review, then approve.
4. Run `tests/test_no_peeking.py`; it must pass before any fitting.
5. Run the backtest.
6. Read `backtest_report.md`: the rubric must beat form-only on the test set; note any groups flagged as thin.
7. Rubric v1 is now in `rubric_versions`; the live scoring engine reads it and uses the same `engine/` modules.
