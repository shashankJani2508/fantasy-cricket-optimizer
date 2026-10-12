"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, Chip, ErrorNote, pts, Sheet, Skeleton, useAuth, useSnack } from "@/components/ui";

const FACTOR_NAMES: Record<string, string> = {
  form: "Form", venue: "Venue", opponent: "Opponent", current_touch: "Current touch", opportunity: "Opportunity",
  career: "Career", bat_first_or_chase: "Batting first or chasing", pitch_type: "Pitch type",
};
const GROUP_NAMES: Record<string, string> = { role: "Player role", batting_band: "Batting position", bat_first_chase: "Batting first vs chasing", pitch_venue: "Venue" };
type Version = { id: number; format_group: string; version: string; weights: Record<string, number>; source: string; parent_version_id: number | null;
  approved_by: string | null; approved_at: string | null; created_at: string | null; is_active: boolean; reliable: boolean; points_values_final: boolean };
type L = {
  series: { match_id: string; date: string; format_group: string; mae: number }[];
  summary: { matches_scored: number; points_roi: number | null; captain_hit_rate: number | null };
  backtest_mae: { format_group: string; mae: number }[]; inbox: any[]; groups: any[]; versions: Version[]; window: number;
};
const GROUPS = ["T20_men", "T20_women", "ODI_men", "ODI_women", "Test_men", "Test_women"];
const label = (g: string) => g.replace("_", " ").replace("men", "men").replace("women", "women");
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "");

export default function Learnings() {
  const [d, setD] = useState<L | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [group, setGroup] = useState("T20_men");
  const [open, setOpen] = useState<Version | null>(null);
  const load = useCallback(() => api<L>("/learnings").then(setD).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  if (err) return <ErrorNote>Couldn&apos;t load learnings: {err}</ErrorNote>;
  if (!d) return <div className="space-y-3"><Skeleton className="h-10 w-48" /><Skeleton className="h-48" /><Skeleton className="h-24" /></div>;
  const active = d.versions.find((v) => v.format_group === group && v.is_active);
  const pts_ = d.series.filter((s) => s.format_group === group);
  const bt = d.backtest_mae.find((b) => b.format_group === group);
  const byId = Object.fromEntries(d.versions.map((v) => [v.id, v]));
  return (
    <section aria-labelledby="h-l" className="space-y-8">
      <header className="flex items-baseline justify-between">
        <h1 id="h-l" className="num text-s40">Learnings</h1>
        <Link href="/learnings/settings" aria-label="Settings" className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full text-s20">⚙</Link>
      </header>

      <div>
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Format">
          {GROUPS.map((g) => <button key={g} role="tab" aria-selected={group === g} onClick={() => setGroup(g)}
            className={`min-h-[44px] rounded-full px-3 text-s14 ${group === g ? "bg-pavilion text-sightscreen" : "bg-surface"}`}>{label(g)}</button>)}
        </div>
        <h2 className="mt-4 font-semibold">Average prediction miss per match (points)</h2>
        <MissChart points={pts_} backtest={bt?.mae ?? null} />
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Fig k="Matches scored" v={String(d.summary.matches_scored)} />
          <Fig k="Points ROI to date" v={d.summary.points_roi == null ? "–" : `${d.summary.points_roi >= 0 ? "+" : ""}${pts(d.summary.points_roi, 0)}`} />
          <Fig k="Captain hit rate" v={d.summary.captain_hit_rate == null ? "–" : `${Math.round(d.summary.captain_hit_rate * 100)}%`} />
          <Fig k="Rubric" v={active ? `${active.version}${active.approved_at ? `, approved ${day(active.approved_at)}` : " (backtest)"}` : "–"} />
        </dl>
        {active && !active.points_values_final && <p className="mt-2 text-s12 text-slate">Weights are provisional: the Dream11 points values were not yet copied from the app.</p>}
      </div>

      <div>
        <h2 className="num text-s28">Waiting for you</h2>
        {d.inbox.length === 0 ? <p className="mt-2 text-slate">Nothing to review. The system flags a pattern after {d.window} matches of similar misses.</p>
          : <div className="mt-2 space-y-3">{d.inbox.map((s) => <Suggestion key={s.id} s={s} versions={d.versions} onDone={load} />)}</div>}
      </div>

      <div>
        <h2 className="num text-s28">Groups</h2>
        {d.groups.filter((g) => g.format_group === group).length === 0 ? <p className="mt-2 text-slate">No {label(group)} matches scored yet.</p> : (
          <ul className="mt-2 divide-y divide-slate/20">
            {d.groups.filter((g) => g.format_group === group).map((g) => (
              <li key={`${g.group_type}:${g.group_value}`} className="flex items-center justify-between py-2 text-s14">
                <span>{GROUP_NAMES[g.group_type]}: {g.group_value.replace("_", " ")}</span>
                {g.status === "flagged" ? <Chip tone="ball">Flagged</Chip> : g.window_matches < d.window ? <Chip>Watching ({g.window_matches} of {d.window} matches)</Chip> : <Chip tone="turf">Fine</Chip>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h2 className="num text-s28">Rubric history</h2>
        <ol className="mt-2 space-y-2">
          {d.versions.filter((v) => v.format_group === group).reverse().map((v) => {
            const parent = v.parent_version_id ? byId[v.parent_version_id] : null;
            const changes = parent ? Object.keys(v.weights).filter((k) => Math.abs(v.weights[k] - parent.weights[k]) > 1e-4) : [];
            return (
              <li key={v.id}>
                <button onClick={() => setOpen(v)} className="w-full rounded-sheet bg-surface p-3 text-left">
                  <div className="flex items-center justify-between"><span className="num text-s20">{v.version}</span>{v.is_active && <Chip tone="turf">Live</Chip>}</div>
                  <div className="text-s12 text-slate">{v.source === "backtest" ? "From the backtest" : `${v.source.replace("_", " ")}${v.approved_by ? ` by ${v.approved_by}` : ""}`} · {day(v.approved_at ?? v.created_at)}{!v.reliable && " · borrows weights (few matches)"}</div>
                  {changes.slice(0, 3).map((k) => <div key={k} className="text-s14">{FACTOR_NAMES[k]}: {parent!.weights[k].toFixed(2)} → {v.weights[k].toFixed(2)}</div>)}
                </button>
              </li>
            );
          })}
        </ol>
      </div>
      <Sheet open={!!open} onClose={() => setOpen(null)} title={`${open?.version ?? ""} weights`}>
        {open && <table className="w-full text-s14"><tbody>{Object.entries(open.weights).map(([k, w]) => (
          <tr key={k} className="border-b border-fg/10"><td className="py-2">{FACTOR_NAMES[k] ?? k}</td><td className="num text-right text-s16">{Number(w).toFixed(3)}</td></tr>))}</tbody></table>}
      </Sheet>
    </section>
  );
}

function Fig({ k, v }: { k: string; v: string }) {
  return <div className="rounded-sheet bg-surface p-3"><dt className="text-s12 text-slate">{k}</dt><dd className="num text-s20">{v}</dd></div>;
}

function MissChart({ points, backtest }: { points: { date: string; mae: number }[]; backtest: number | null }) {
  if (points.length === 0) return (
    <div className="mt-2 rounded-sheet bg-surface p-4 text-s14 text-slate">
      No matches scored in this format yet.{backtest != null && ` Backtest typical miss: ${pts(backtest)} points.`}
    </div>
  );
  const W = 600, H = 180, P = 28;
  const ys = points.map((p) => p.mae).concat(backtest ?? []);
  const max = Math.max(...ys) * 1.15, n = points.length;
  const x = (i: number) => P + (n === 1 ? (W - 2 * P) / 2 : (i * (W - 2 * P)) / (n - 1));
  const y = (v: number) => H - P - (v / max) * (H - 2 * P);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full rounded-sheet bg-surface" role="img" aria-label={`Average miss over ${n} matches, latest ${pts(points[n - 1].mae)} points`}>
      {backtest != null && <><line x1={P} x2={W - P} y1={y(backtest)} y2={y(backtest)} stroke="rgb(var(--clay))" strokeDasharray="4 4" strokeWidth={2} />
        <text x={W - P} y={y(backtest) - 6} textAnchor="end" fontSize="12" fill="rgb(var(--slate))">backtest {pts(backtest)}</text></>}
      <polyline fill="none" stroke="rgb(var(--turf))" strokeWidth={3} points={points.map((p, i) => `${x(i)},${y(p.mae)}`).join(" ")} />
      {points.map((p, i) => <circle key={i} cx={x(i)} cy={y(p.mae)} r={4} fill="rgb(var(--turf))"><title>{`${day(p.date)}: ${pts(p.mae)}`}</title></circle>)}
      <text x={P} y={H - 8} fontSize="12" fill="rgb(var(--slate))">{day(points[0].date)}</text>
      <text x={W - P} y={H - 8} fontSize="12" textAnchor="end" fill="rgb(var(--slate))">{day(points[n - 1].date)}</text>
    </svg>
  );
}

function Suggestion({ s, versions, onDone }: { s: any; versions: Version[]; onDone: () => void }) {
  const { ask } = useAuth();
  const snack = useSnack();
  const [edit, setEdit] = useState<Record<string, number> | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const decide = async (decision: string, version?: Record<string, number>) => {
    if (!(await ask())) return;
    setBusy(true); setErr(null);
    try {
      const r = await api(`/suggestions/${s.id}/decision`, { method: "POST", body: { decision, version } });
      snack({ text: decision === "reject" ? "Kept as it is." : r.new_version ? `Change approved. ${r.new_version} is live from the next match.` : "Change approved." });
      onDone();
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  const p = s.proposal, t = s.gemini_text ?? {};
  const cur = versions.find((v) => v.is_active && v.format_group.replace("-", "_") === (s.format_group ?? "").replace("-", "_"));
  return (
    <article className="rounded-sheet bg-surface p-4">
      {s.kind === "weight" && <>
        <p className="font-semibold">{t.pattern}</p>
        <p className="text-s12 text-slate">{t.evidence}</p>
        {p ? <>
          <p className="mt-2">{FACTOR_NAMES[p.factor] ?? p.factor}: <span className="num text-s20">{p.current_weight.toFixed(2)} → {p.proposed_weight.toFixed(2)}</span></p>
          <p className="text-s14">{t.why}</p>
          {s.history_check === "supported"
            ? <p className="mt-1 text-s14 text-turf">Supported by past matches: miss drops from {pts(s.mae_before)} to {pts(s.mae_after)}</p>
            : <p className="mt-1 text-s14 text-slate">Not supported by history{s.mae_before != null ? ` (miss ${pts(s.mae_before)} → ${pts(s.mae_after)})` : ""}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button disabled={busy} onClick={() => decide("approve")}>Approve change</Button>
            <Button kind="quiet" disabled={busy} onClick={() => setEdit({ ...p.weights_after })}>Edit</Button>
            <Button kind="quiet" disabled={busy} onClick={() => decide("reject")}>Reject</Button>
          </div>
        </> : <>
          <p className="mt-2 text-s14">Gemini suggests no change: {t.why}</p>
          <Button kind="quiet" className="mt-2" disabled={busy} onClick={() => decide("reject")}>Close</Button>
        </>}
      </>}
      {s.kind === "rollback" && <>
        <p className="font-semibold">Since the last change, predictions got worse. The previous version would have missed by {pts(s.mae_before - s.mae_after)} fewer points.</p>
        <div className="mt-3 flex gap-2"><Button disabled={busy} onClick={() => decide("approve")}>Roll back</Button><Button kind="quiet" disabled={busy} onClick={() => decide("reject")}>Keep {cur?.version ?? "current"}</Button></div>
      </>}
      {s.kind === "gemini_cap" && <>
        <p className="font-semibold">{t.pattern}</p>
        <div className="mt-3 flex gap-2"><Button disabled={busy} onClick={() => decide("approve")}>Lower limit to ±10%</Button><Button kind="quiet" disabled={busy} onClick={() => decide("reject")}>Keep ±20%</Button></div>
      </>}
      {err && <div className="mt-2"><ErrorNote>{err}</ErrorNote></div>}
      <Sheet open={!!edit} onClose={() => setEdit(null)} title="Edit weights">
        {edit && <div className="space-y-2">
          {Object.entries(edit).map(([k, w]) => {
            const before = p.weights_before[k], far = Math.abs(w - before) > 0.1 + 1e-9;
            return (
              <label key={k} className="flex items-center justify-between gap-2 text-s14">
                <span>{FACTOR_NAMES[k] ?? k}{far && <span className="text-ball"> · beyond ±0.10</span>}</span>
                <input type="number" step="0.01" min="0" max="1" value={w} onChange={(e) => setEdit({ ...edit, [k]: Number(e.target.value) })}
                  className="num min-h-[44px] w-24 rounded-input border border-fg/10 bg-surface px-2 text-s16" />
              </label>
            );
          })}
          <p className="text-s12 text-slate">Weights are rescaled to add up to 1 when saved.</p>
          <Button className="w-full" disabled={busy} onClick={() => { decide("edit", edit); setEdit(null); }}>Save my version</Button>
        </div>}
      </Sheet>
    </article>
  );
}
