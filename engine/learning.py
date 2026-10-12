"""Learning loop (docs/LEARNING_LOOP.md): results -> metrics -> patterns -> flags -> Gemini analyst ->
history replay -> Aryan decides -> new rubric version; plus rollback and Gemini-cap checks.
Gemini never learns and nothing changes weights without Aryan's decision."""
from pathlib import Path

from psycopg.types.json import Jsonb

from engine.factors import FACTORS
from engine.gate import load_rules
from engine.gemini import GeminiFailed
from engine.groups import from_any
from engine.optimizer import NoValidTeam, best_team
from engine.pipeline import aryan_list, log, save_team
from engine.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


# ---- pure helpers ----------------------------------------------------------------------------------------------
def renormalise(weights, factor, new):
    """Set one factor's weight and scale the others so all sum to 1."""
    new = min(max(float(new), 0.0), 1.0)
    rest = sum(float(w) for k, w in weights.items() if k != factor)
    out = {k: (new if k == factor else (float(w) * (1 - new) / rest if rest else (1 - new) / (len(weights) - 1)))
           for k, w in weights.items()}
    return {k: round(v, 6) for k, v in out.items()}


def team_total(ids, cap, vc, pts, cm, vm):
    return sum(pts.get(p, 0.0) for p in ids) + (cm - 1) * pts.get(cap, 0.0) + (vm - 1) * pts.get(vc, 0.0)


def evaluate(errors, threshold, min_misses, same_dir):
    """errors: prediction - actual for one group's window. -> dict for patterns (flagged or not)."""
    misses = [e for e in errors if abs(e) > threshold]
    over = sum(1 for e in misses if e > 0)
    n = len(misses)
    share = max(over, n - over) / n if n else 0.0
    return {"real_misses": n, "same_direction_pct": round(share, 3),
            "avg_error": round(sum(misses) / n, 2) if n else 0.0,
            "direction": ("over" if over >= n - over else "under") if n else None,
            "flagged": n >= min_misses and share >= same_dir}


def bat_band(pos):
    if pos is None:
        return "did_not_bat"
    return "top" if pos <= 3 else "middle" if pos <= 7 else "lower"


# ---- data access -----------------------------------------------------------------------------------------------
def match_run(store, mid):
    """The run whose team counts for the match: latest finished post-toss run, else latest pre-toss."""
    return store.one("""SELECT id::text FROM runs WHERE match_id = %s AND status = 'done'
                        ORDER BY (run_type = 'post_toss') DESC, started_at DESC LIMIT 1""", (mid,))


def actual_points(store, mid):
    pts = {p: float(v) for p, v in store.q("SELECT player_id, total_points FROM player_match_points WHERE match_id = %s",
                                           (mid,))}
    for p, v in store.q("SELECT player_id, aryan_points FROM results WHERE match_id = %s AND aryan_points IS NOT NULL",
                        (mid,)):
        pts.setdefault(p, float(v))
    return pts


def save_results(store, mid, rows, rank=None, via="screenshot"):
    """rows: [{player_id, points}]. calc_points from our calculator; mismatch never blocks saving."""
    calc = dict(store.q("SELECT player_id, total_points FROM player_match_points WHERE match_id = %s", (mid,)))
    mism = []
    for r in rows:
        c = calc.get(r["player_id"])
        bad = c is not None and r["points"] is not None and abs(float(c) - float(r["points"])) > 0.01
        if bad:
            mism.append(r["player_id"])
        store.q("""INSERT INTO results (match_id, player_id, aryan_points, aryan_rank, entered_via, calc_points, mismatch)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (match_id, player_id) DO UPDATE SET
                   aryan_points = EXCLUDED.aryan_points, aryan_rank = EXCLUDED.aryan_rank, calc_points = EXCLUDED.calc_points,
                   mismatch = EXCLUDED.mismatch, entered_at = now() RETURNING id""",
                (mid, r["player_id"], r["points"], rank, via, c, bad))
    log(store, "aryan", "results_saved", mid, {"players": len(rows), "rank": rank, "mismatches": mism})
    return mism


def _rules(group):
    return load_rules(ROOT / "config" / "dream11_rules.yaml", from_any(group).split("_")[0])


def compute_metrics(store, mid):
    rid = match_run(store, mid)
    if rid is None:
        return None
    group, rain = store.q("SELECT format_group, rain_affected FROM matches WHERE id = %s", (mid,))[0]
    rules = _rules(group)
    cm, vm = rules["captain_multiplier"], rules["vc_multiplier"]
    pts = actual_points(store, mid)
    teams = {k: (ids, c, v) for k, ids, c, v in store.q(
        """SELECT DISTINCT ON (kind) kind, player_ids, captain_id, vc_id FROM teams_picked t JOIN runs r ON r.id = t.run_id
           WHERE r.match_id = %s AND (t.run_id = %s OR kind = 'aryan_final') ORDER BY kind, t.id DESC""", (mid, rid))}
    tot = {k: team_total(*t, pts, cm, vm) for k, t in teams.items()}
    for k, t in tot.items():
        store.q("""UPDATE teams_picked SET total_actual = %s WHERE id = (SELECT t.id FROM teams_picked t JOIN runs r
                   ON r.id = t.run_id WHERE r.match_id = %s AND kind = %s ORDER BY t.id DESC LIMIT 1) RETURNING id""",
                (t, mid, k))
    lst = aryan_list(store, mid)
    hind = {p: {**v, "score": pts[p], "thin": False} for p, v in lst.items() if p in pts}
    perfect = None
    store.q("DELETE FROM teams_picked WHERE run_id = %s AND kind = 'perfect' RETURNING id", (rid,))
    try:
        team = best_team(hind, rules)
        save_team(store, rid, "perfect", team, hind, rules)
        perfect = team.total_expected
        store.q("UPDATE teams_picked SET total_actual = %s WHERE run_id = %s AND kind = 'perfect' RETURNING id",
                (perfect, rid))
    except NoValidTeam:
        pass
    top3 = sorted(pts, key=lambda p: -pts[p])[:3]
    cap = teams.get("system", (None, None, None))[1]
    ov = store.q("SELECT out_player_id, in_player_id FROM overrides WHERE match_id = %s AND out_player_id IS NOT NULL", (mid,))
    ov_rate = (sum(1 for o, i in ov if pts.get(i, 0) > pts.get(o, 0)) / len(ov)) if ov else None
    preds = {p: (b, a) for p, b, a in store.q("SELECT player_id, base_score, adjusted_score FROM predictions WHERE run_id = %s",
                                                (rid,))}
    helped = []
    for aid, p in store.q("SELECT id, player_id FROM gemini_adjustments WHERE run_id = %s", (rid,)):
        if p in pts and p in preds:
            h = abs(preds[p][1] - pts[p]) < abs(preds[p][0] - pts[p])
            helped.append(h)
            store.q("UPDATE gemini_adjustments SET helped = %s WHERE id = %s RETURNING id", (h, aid))
    errs = [abs(a - pts[p]) for p, (b, a) in preds.items() if p in pts and a is not None]
    final = store.one("""SELECT count(*) > 0 AND bool_and(source = 'cricsheet') FROM player_match_points
                         WHERE match_id = %s""", (mid,))
    sys_t = tot.get("system")
    m = {"system_points": sys_t, "aryan_points": tot.get("aryan_final"), "simple_points": tot.get("simple"),
         "perfect_points": perfect,
         "points_roi": (sys_t - tot["simple"]) if sys_t is not None and "simple" in tot else None,
         "efficiency": (sys_t / perfect) if sys_t is not None and perfect else None,
         "captain_hit": cap in top3 if cap else None, "override_hit_rate": ov_rate,
         "gemini_value": (sum(helped) / len(helped)) if helped else None,
         "mae": (sum(errs) / len(errs)) if errs else None, "points_final": bool(final),
         "excluded_from_learning": bool(rain)}
    cols = list(m)
    store.q(f"""INSERT INTO metrics (match_id, format_group, {', '.join(cols)}) VALUES (%s, %s, {', '.join(['%s'] * len(cols))})
                ON CONFLICT (match_id) DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in cols)}, computed_at = now()
                RETURNING id""", (mid, group, *m.values()))
    return m


def _active_row(store, group):
    for r in store.q("SELECT id, format_group, weights, test_mae, version, source, parent_version_id, approved_at "
                     "FROM rubric_versions WHERE is_active"):
        if from_any(r[1]) == from_any(group):
            return dict(zip(("id", "format_group", "weights", "test_mae", "version", "source", "parent", "approved_at"), r))
    return None


def _live_rows(store, group, since=None):
    """Stored factor values + actual points for finished matches in the group (counted matches only)."""
    rows = store.q("""SELECT r.match_id, p.player_id, p.factors, p.adjusted_score, pmp.total_points, c.dream11_role,
                             pmp.batting_position, v.name, (t.id = m.batting_first_team_id)
                        FROM metrics mt JOIN matches m ON m.id = mt.match_id
                        JOIN runs r ON r.id = (SELECT id FROM runs WHERE match_id = m.id AND status = 'done'
                                               ORDER BY (run_type = 'post_toss') DESC, started_at DESC LIMIT 1)
                        JOIN predictions p ON p.run_id = r.id
                        JOIN player_match_points pmp ON pmp.match_id = m.id AND pmp.player_id = p.player_id
                        LEFT JOIN credits c ON c.match_id = m.id AND c.player_id = p.player_id
                        LEFT JOIN venues v ON v.id = m.venue_id
                        LEFT JOIN match_xi x ON x.match_id = m.id AND x.player_id = p.player_id
                        LEFT JOIN teams t ON t.id = x.team_id
                       WHERE m.format_group = %s AND NOT mt.excluded_from_learning
                         AND (%s::timestamptz IS NULL OR m.start_time > %s)
                       ORDER BY m.start_time DESC""", (from_any(group), since, since))
    return rows


def replay(store, group, weights, since=None, backtest=True):
    """MAE of the weights on stored factor values: backtest test split (run 1 table) + live predictions."""
    total, n = 0.0, 0
    if backtest:
        expr = " + ".join(f"%s * coalesce({f}, 0)" for f in FACTORS)
        r = store.q(f"""SELECT sum(abs({expr} - actual)), count(*) FROM public.bt_predictions
                        WHERE split = 'test' AND format_group = %s""",
                    (*[float(weights[f]) for f in FACTORS], _row_group(store, group)))[0]
        total, n = float(r[0] or 0), int(r[1] or 0)
    for row in _live_rows(store, group, since):
        f = row[2] or {}
        if f:
            total += abs(sum(float(weights[k]) * float(f.get(k, 0)) for k in FACTORS) - float(row[4]))
            n += 1
    return (total / n) if n else None


def _row_group(store, group):
    row = _active_row(store, group)
    return row["format_group"] if row else group


def update_patterns(store, group):
    """Recompute patterns for the group's last N counted matches per group value. Returns newly flagged ids."""
    st = Settings(store)
    window, mult = st.int("flag_window_matches"), st.float("real_miss_mae_multiplier")
    row = _active_row(store, group)
    if row is None or row["test_mae"] is None:
        return []
    threshold = mult * float(row["test_mae"])
    per = {}
    for mid, pid, f, adj, act, role, pos, venue, bat_first in _live_rows(store, group):
        if adj is None:
            continue
        keys = [("role", role), ("batting_band", bat_band(pos)), ("pitch_venue", venue),
                ("bat_first_chase", None if bat_first is None else ("batting_first" if bat_first else "chasing"))]
        for k in keys:
            if k[1] is None:
                continue
            d = per.setdefault(k, {"matches": [], "errors": []})
            if mid not in d["matches"]:
                if len(d["matches"]) >= window:
                    continue
                d["matches"].append(mid)
            d["errors"].append(float(adj) - float(act))
    new = []
    for (gt, gv), d in per.items():
        ev = evaluate(d["errors"], threshold, st.int("flag_min_misses"), st.float("flag_same_direction"))
        old = store.q("SELECT id, status FROM patterns WHERE format_group = %s AND group_type = %s AND group_value = %s",
                      (from_any(group), gt, gv))
        status = "flagged" if ev["flagged"] else ("resolved" if old and old[0][1] == "resolved" else "watching")
        pid = store.one("""INSERT INTO patterns (format_group, group_type, group_value, window_matches, real_misses,
                           same_direction_pct, avg_error, direction, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (format_group, group_type, group_value) DO UPDATE SET
                           window_matches = EXCLUDED.window_matches, real_misses = EXCLUDED.real_misses,
                           same_direction_pct = EXCLUDED.same_direction_pct, avg_error = EXCLUDED.avg_error,
                           direction = EXCLUDED.direction, status = EXCLUDED.status, updated_at = now() RETURNING id""",
                        (from_any(group), gt, gv, len(d["matches"]), ev["real_misses"], ev["same_direction_pct"],
                         ev["avg_error"], ev["direction"], status))
        if ev["flagged"] and not (old and old[0][1] == "flagged"):
            new.append(pid)
    return new


def suggest(store, gemini, pattern_id):
    """Gemini analyst -> renormalise -> replay -> weight_suggestions (pending). None if Gemini failed."""
    p = dict(zip(("id", "format_group", "group_type", "group_value", "window_matches", "real_misses", "avg_error",
                  "direction"), store.q("""SELECT id, format_group, group_type, group_value, window_matches, real_misses,
                  avg_error, direction FROM patterns WHERE id = %s""", (pattern_id,))[0]))
    row = _active_row(store, p["format_group"])
    weights = {k: float(v) for k, v in row["weights"].items()}
    label = f"{p['format_group']} {p['group_type'].replace('_', ' ')} = {p['group_value']}"
    group = {**p, "label": label, "matches": p["window_matches"], "average_error_points": p["avg_error"],
             "error_direction": "we predicted too high" if p["direction"] == "over" else "we predicted too low"}
    try:
        out, _ = gemini.analyse(group, weights, Settings(store).float("max_weight_change"))
    except GeminiFailed:
        return None   # pattern stays flagged; retried after the next match
    proposal, check, before, after = None, None, None, None
    if out["proposal"]:
        pr = out["proposal"]
        new_w = renormalise(weights, pr["factor"], pr["proposed_weight"])
        before, after = replay(store, p["format_group"], weights), replay(store, p["format_group"], new_w)
        check = "supported" if before is not None and after is not None and after < before else "not_supported"
        proposal = {**pr, "weights_before": weights, "weights_after": new_w}
    text = {k: out.get(k) for k in ("pattern", "evidence", "why")}
    return store.one("""INSERT INTO weight_suggestions (kind, pattern_id, format_group, proposal, gemini_text,
                        history_check, history_mae_before, history_mae_after) VALUES ('weight', %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id""", (pattern_id, p["format_group"], Jsonb(proposal), Jsonb(text), check, before, after))


def _new_version(store, group, weights, source, approved_by="aryan"):
    row = _active_row(store, group)
    n = store.one("SELECT count(*) FROM rubric_versions WHERE format_group = %s", (row["format_group"],))
    store.q("UPDATE rubric_versions SET is_active = false WHERE id = %s RETURNING id", (row["id"],))
    return store.one("""INSERT INTO rubric_versions (version, format_group, weights, thin_data_threshold, test_mae,
                        baseline_mae, validation_mae, benchmark_50_50_mae, reliable, borrowed_from_group,
                        points_values_final, is_active, source, parent_version_id, approved_by, approved_at)
                        SELECT %s, format_group, %s, thin_data_threshold, test_mae, baseline_mae, validation_mae,
                               benchmark_50_50_mae, reliable, borrowed_from_group, points_values_final, true, %s, id, %s, now()
                          FROM rubric_versions WHERE id = %s RETURNING id""",
                     (f"v{n + 1}", Jsonb(weights), source, approved_by, row["id"]))


class DecisionError(Exception):
    pass


def decide(store, sid, decision, version=None):
    """decision: approve | edit | reject. edit takes version = full weights dict (renormalised to sum 1)."""
    r = store.q("SELECT kind, pattern_id, format_group, proposal, aryan_decision FROM weight_suggestions WHERE id = %s",
                (sid,))
    if not r:
        raise DecisionError("Suggestion not found")
    kind, pattern, group, proposal, state = r[0]
    if state != "pending":
        raise DecisionError("This suggestion was already decided")
    result, chosen = None, None
    if decision in ("approve", "edit"):
        if kind == "gemini_cap":
            store.q("UPDATE settings SET value = %s, updated_by = 'aryan', updated_at = now() WHERE key = 'gemini_cap_percent' "
                    "RETURNING key", (Jsonb(10),))
        else:
            if decision == "edit":
                if not version or set(version) != set(FACTORS) or any(float(v) < 0 for v in version.values()):
                    raise DecisionError("Give a weight (0 or more) for every factor")
                s = sum(float(v) for v in version.values())
                chosen = {k: round(float(v) / s, 6) for k, v in version.items()}
            elif proposal is None:
                raise DecisionError("Gemini proposed no change: reject to close it")
            else:
                chosen = proposal["weights_after"] if kind == "weight" else proposal["weights"]
            source = "aryan_edit" if decision == "edit" else ("rollback" if kind == "rollback" else "approved_change")
            result = _new_version(store, group, chosen, source)
    elif decision != "reject":
        raise DecisionError("Decision must be approve, edit or reject")
    state = {"approve": "approved", "edit": "edited", "reject": "rejected"}[decision]
    store.q("""UPDATE weight_suggestions SET aryan_decision = %s, aryan_version = %s, decided_at = now(),
               resulting_version_id = %s WHERE id = %s RETURNING id""",
            (state, Jsonb(chosen), str(result) if result else None, sid))
    if pattern:
        store.q("UPDATE patterns SET status = 'resolved', updated_at = now() WHERE id = %s RETURNING id", (pattern,))
    log(store, "aryan", f"suggestion_{state}", None, {"suggestion_id": sid, "kind": kind, "new_version_id": result})
    return result


def check_rollback(store, group):
    row = _active_row(store, group)
    if not row or row["source"] not in ("approved_change", "aryan_edit") or not row["parent"]:
        return None
    since = row["approved_at"]
    n = store.one("""SELECT count(*) FROM metrics mt JOIN matches m ON m.id = mt.match_id WHERE m.format_group = %s
                     AND NOT mt.excluded_from_learning AND m.start_time > %s""", (from_any(group), since))
    if n < Settings(store).int("rollback_window_matches"):
        return None
    if store.one("SELECT 1 FROM weight_suggestions WHERE kind = 'rollback' AND proposal->>'from_version_id' = %s",
                 (str(row["id"]),)):
        return None
    prev = store.one("SELECT weights FROM rubric_versions WHERE id = %s", (row["parent"],))
    cur_mae = replay(store, group, row["weights"], since=since, backtest=False)
    prev_mae = replay(store, group, prev, since=since, backtest=False)
    if cur_mae is None or prev_mae is None or prev_mae >= cur_mae:
        return None
    return store.one("""INSERT INTO weight_suggestions (kind, format_group, proposal, history_check, history_mae_before,
                        history_mae_after) VALUES ('rollback', %s, %s, 'supported', %s, %s) RETURNING id""",
                     (row["format_group"], Jsonb({"from_version_id": str(row["id"]), "to_version_id": str(row["parent"]),
                                                  "weights": prev}), cur_mae, prev_mae))


def check_gemini_cap(store):
    st = Settings(store)
    if st.float("gemini_cap_percent") <= 10:
        return None
    if store.one("SELECT 1 FROM weight_suggestions WHERE kind = 'gemini_cap' AND aryan_decision = 'pending'"):
        return None
    rows = store.q("""SELECT mt.match_id, bool_or(a.helped), count(*) FILTER (WHERE a.helped), count(*) FILTER (WHERE NOT a.helped)
                        FROM metrics mt JOIN runs r ON r.match_id = mt.match_id JOIN gemini_adjustments a ON a.run_id = r.id
                       WHERE a.helped IS NOT NULL GROUP BY mt.match_id, mt.computed_at ORDER BY mt.computed_at DESC LIMIT %s""",
                   (st.int("gemini_trust_window_matches"),))
    if len(rows) < st.int("gemini_trust_window_matches"):
        return None
    good, bad = sum(r[2] for r in rows), sum(r[3] for r in rows)
    if bad <= good:
        return None
    return store.one("""INSERT INTO weight_suggestions (kind, proposal, gemini_text) VALUES ('gemini_cap', %s, %s)
                        RETURNING id""", (Jsonb({"setting": "gemini_cap_percent", "from": st.float("gemini_cap_percent"),
                                                 "to": 10}),
                                          Jsonb({"pattern": f"Gemini's adjustments made {bad} of {good + bad} predictions "
                                                            f"worse over the last {len(rows)} matches"})))


def after_results(store, mid, gemini):
    """Everything that follows Aryan saving results (CLAUDE.md section 10 F and G)."""
    m = compute_metrics(store, mid)
    group = store.one("SELECT format_group FROM matches WHERE id = %s", (mid,))
    made = []
    if m and not m["excluded_from_learning"]:
        flagged = update_patterns(store, group)
        pending = [r[0] for r in store.q("""SELECT p.id FROM patterns p WHERE p.status = 'flagged' AND p.format_group = %s
                     AND NOT EXISTS (SELECT 1 FROM weight_suggestions w WHERE w.pattern_id = p.id
                                      AND w.aryan_decision = 'pending')""", (from_any(group),))]
        for pid in sorted(set(flagged) | set(pending)):
            made.append(suggest(store, gemini, pid))
        made += [check_rollback(store, group), check_gemini_cap(store)]
    return {"metrics": m, "suggestions": [s for s in made if s]}
