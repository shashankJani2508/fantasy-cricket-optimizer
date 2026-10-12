"use client";
import { Settings as Gear } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, Chip, ErrorNote, PillTabs, pts, Sheet, Skeleton, useAuth, useSnack } from "@/components/ui";

const FACTOR_NAMES: Record<string, string> = {
  form: "Form", venue: "Venue", opponent: "Opponent", current_touch: "Current touch", opportunity: "Opportunity",
  career: "Career", bat_first_or_chase: "Batting first or chasing", pitch_type: "Pitch type",
};
const GROUP_NAMES: Record<string, string> = { role: "Player role", batting_band: "Batting position", bat_first_chase: "Batting first vs chasing", pitch_venue: "Venue" };
const ART: Record<string, string> = { weight: "linear-gradient(135deg,#3A0E1C,#E8172C)", rollback: "linear-gradient(135deg,#1A1F4A,#FF7A1A)", gemini_cap: "linear-gradient(135deg,#1A1F4A,#2BB673)" };
type Version = { id: number; format_group: string; version: string; weights: Record<string, number>; source: string; parent_version_id: number | null;
  approved_by: string | null; approved_at: string | null; created_at: string | null; is_active: boolean; reliable: boolean; points_values_final: boolean };
type L = {
  series: { match_id: string; date: string; format_group: string; mae: number }[];
  summary: { matches_scored: number; points_roi: number | null; captain_hit_rate: number | null };
  backtest_mae: { format_group: string; mae: number }[]; inbox: any[]; groups: any[]; versions: Version[]; window: number;
};
const GROUPS = ["T20_men", "T20_women", "ODI_men", "ODI_women", "Test_men", "Test_women"] as const;
const label = (g: string) => g.replace("_", " ");
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "");

export default function Learnings() {
  const [d, setD] = useState<L | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [group, setGroup] = useState<(typeof GROUPS)[number]>("T20_men");
  const [open, setOpen] = useState<Version | null>(null);
  const load = useCallback(() => api<L>("/learnings").then(setD).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  if (err) return <ErrorNote>Couldn&apos;t load learnings: {err}</ErrorNote>;
  if (!d) return <div className="space-y-4"><Skeleton className="h-9 w-40" /><Skeleton className="h-56 !rounded-card" /><Skeleton className="h-64 !rounded-card" /></div>;
  const active = d.versions.find((v) => v.format_group === group && v.is_active);
  const series = d.series.filter((s) => s.format_group === group);
  const bt = d.backtest_mae.find((b) => b.format_group === group);
  const byId = Object.fromEntries(d.versions.map((v) => [v.id, v]));
  const groups = d.groups.filter((g) => g.format_group === group);
  return (
    <section aria-labelledby="h-l" className="space-y-7">
      <header className="flex items-center justify-between">
        <h1 id="h-l" className="num text-s26 font-bold">Learnings</h1>
        <Link href="/learnings/settings" aria-label="Settings" className="flex h-11 w-11 items-center justify-center rounded-full glass"><Gear size={20} strokeWidth={1.75} /></Link>
      </header>
      <PillTabs label="Format" value={group} onChange={setGroup} tabs={GROUPS.map((g) => ({ key: g, label: label(g) }))} />

      <div className="rounded-card bg-surface p-4 shadow-card">
        <h2 className="text-s14 font-semibold text-muted">Average miss per match (points)</h2>
        <MissChart points={series} backtest={bt?.mae ?? null} />
        <dl className="mt-4 grid grid-cols-2 gap-2">
          <Fig k="Matches scored" v={String(d.summary.matches_scored)} />
          <Fig k="Points ROI to date" v={d.summary.points_roi == null ? "–" : `${d.summary.points_roi >= 0 ? "+" : ""}${pts(d.summary.points_roi, 0)}`} />
          <Fig k="Captain hit rate" v={d.summary.captain_hit_rate == null ? "–" : `${Math.round(d.summary.captain_hit_rate * 100)}%`} />
          <Fig k="Rubric" v={active ? active.version : "–"} sub={active ? (active.approved_at ? `approved ${day(active.approved_at)}` : "from the backtest") : undefined} />
        </dl>
        {active && !active.points_values_final && <p className="mt-3 text-s12 text-muted">Weights are provisional: Dream11 points values not yet copied from the app.</p>}
      </div>

      <div>
        <h2 className="num mb-3 text-s20 font-bold">Waiting for you</h2>
        {d.inbox.length === 0 ? <p className="rounded-card bg-surface p-5 text-s14 text-muted shadow-card">Nothing to review. The system flags a pattern after {d.window} matches of similar misses.</p>
          : <div className="no-scrollbar -mx-5 flex snap-x gap-3 overflow-x-auto px-5 pb-2">{d.inbox.map((s) => <Suggestion key={s.id} s={s} versions={d.versions} onDone={load} />)}</div>}
      </div>

      <div>
        <h2 className="num mb-3 text-s20 font-bold">Groups</h2>
        {groups.length === 0 ? <p className="rounded-card bg-surface p-5 text-s14 text-muted shadow-card">No {label(group)} matches scored yet. Groups appear after your first results.</p> : (
          <ul className="overflow-hidden rounded-card bg-surface shadow-card">
            {groups.map((g) => (
              <li key={`${g.group_type}:${g.group_value}`} className="flex items-center justify-between gap-2 border-b hairline px-4 py-3 text-s14 last:border-0">
                <span className="min-w-0 truncate">{GROUP_NAMES[g.group_type]}: <span className="text-muted">{g.group_value.replace("_", " ")}</span></span>
                {g.status === "flagged" ? <Chip tone="red">Flagged</Chip> : g.window_matches < d.window ? <Chip tone="muted">Watching {g.window_matches}/{d.window}</Chip> : <Chip tone="green">Fine</Chip>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h2 className="num mb-3 text-s20 font-bold">Rubric history</h2>
        <ol className="relative ml-2 border-l border-white/10 pl-6">
          {d.versions.filter((v) => v.format_group === group).reverse().map((v) => {
            const parent = v.parent_version_id ? byId[v.parent_version_id] : null;
            const changes = parent ? Object.keys(v.weights).filter((k) => Math.abs(v.weights[k] - parent.weights[k]) > 1e-4) : [];
            return (
              <li key={v.id} className="relative mb-4">
                <span aria-hidden className={`absolute -left-[31px] top-4 h-3 w-3 rounded-full ${v.is_active ? "bg-orange shadow-[0_0_12px_#FF7A1A]" : "bg-muted/60"}`} />
                <button onClick={() => setOpen(v)} className="w-full rounded-tile bg-surface p-4 text-left shadow-card">
                  <div className="flex items-center justify-between"><span className="num text-s20 font-bold">{v.version}</span>{v.is_active && <Chip tone="green">Live</Chip>}</div>
                  <div className="text-s12 text-muted">{v.source === "backtest" ? "From the backtest" : `${v.source.replace("_", " ")}${v.approved_by ? ` by ${v.approved_by}` : ""}`} · {day(v.approved_at ?? v.created_at)}{!v.reliable && " · borrows weights (few matches)"}</div>
                  {changes.slice(0, 3).map((k) => <div key={k} className="mt-1 text-s14">{FACTOR_NAMES[k]}: <span className="num font-bold">{parent!.weights[k].toFixed(2)} → {v.weights[k].toFixed(2)}</span></div>)}
                </button>
              </li>
            );
          })}
        </ol>
      </div>
      <Sheet open={!!open} onClose={() => setOpen(null)} title={`${open?.version ?? ""} weights`}>
        {open && <ul className="overflow-hidden rounded-tile bg-surface">{Object.entries(open.weights).map(([k, w]) => (
          <li key={k} className="flex justify-between border-b hairline px-4 py-3 text-s14 last:border-0"><span>{FACTOR_NAMES[k] ?? k}</span><span className="num font-bold">{Number(w).toFixed(3)}</span></li>))}</ul>}
      </Sheet>
    </section>
  );
}

function Fig({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return <div className="rounded-tile bg-surface2 p-3"><dt className="text-[11px] text-muted">{k}</dt><dd className="num text-s20 font-bold">{v}</dd>{sub && <dd className="text-[11px] text-muted">{sub}</dd>}</div>;
}

function MissChart({ points, backtest }: { points: { date: string; mae: number }[]; backtest: number | null }) {
  if (points.length === 0) return (
    <p className="mt-3 text-s14 text-muted">No matches scored in this format yet.{backtest != null && <> Backtest typical miss: <span className="num font-bold text-ink">{pts(backtest)}</span> points.</>}</p>
  );
  const W = 360, H = 160, P = 16, n = points.length;
  const max = Math.max(...points.map((p) => p.mae).concat(backtest ?? 0)) * 1.2;
  const x = (i: number) => P + (n === 1 ? (W - 2 * P) / 2 : (i * (W - 2 * P)) / (n - 1));
  const y = (v: number) => H - P - (v / max) * (H - 2 * P);
  const path = points.map((p, i) => {
    if (i === 0) return `M${x(0)},${y(p.mae)}`;
    const cx = (x(i - 1) + x(i)) / 2;
    return `C${cx},${y(points[i - 1].mae)} ${cx},${y(p.mae)} ${x(i)},${y(p.mae)}`;
  }).join(" ");
  const last = points[n - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label={`Average miss over ${n} matches, latest ${pts(last.mae)} points`}>
      {[0.25, 0.5, 0.75].map((f) => <line key={f} x1={P} x2={W - P} y1={H * f} y2={H * f} stroke="rgba(255,255,255,0.06)" />)}
      {backtest != null && <><line x1={P} x2={W - P} y1={y(backtest)} y2={y(backtest)} stroke="#9AA0AE" strokeDasharray="4 5" />
        <text x={W - P} y={y(backtest) - 6} textAnchor="end" fontSize="11" fill="#9AA0AE">backtest {pts(backtest)}</text></>}
      <path d={path} fill="none" stroke="#F5F6F8" strokeWidth={2.5} strokeLinecap="round" />
      <circle cx={x(n - 1)} cy={y(last.mae)} r={5} fill="#FF7A1A"><title>{`${day(last.date)}: ${pts(last.mae)}`}</title></circle>
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
  const title = s.kind === "weight" ? "Weight change" : s.kind === "rollback" ? "Rollback" : "Gemini's limit";
  return (
    <article className="flex w-[290px] shrink-0 snap-start flex-col overflow-hidden rounded-card bg-surface shadow-card">
      <div className="noise relative h-24 p-4" style={{ background: ART[s.kind] }}>
        <Chip tone="glass" className="relative">{title}</Chip>
        {s.format_group && <p className="relative mt-2 text-s12 text-ink/80">{label(String(s.format_group).replace("-male", "_men").replace("-female", "_women"))}</p>}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        {s.kind === "weight" && <>
          <p className="font-semibold leading-snug">{t.pattern}</p>
          <p className="text-s12 text-muted">{t.evidence}</p>
          {p ? <>
            <p className="text-s14">{FACTOR_NAMES[p.factor] ?? p.factor}</p>
            <p className="num text-s26 font-extrabold">{p.current_weight.toFixed(2)} → {p.proposed_weight.toFixed(2)}</p>
            <p className="text-s12 text-muted">{t.why}</p>
            {s.history_check === "supported" ? <Chip tone="green">Supported: miss {pts(s.mae_before)} → {pts(s.mae_after)}</Chip> : <Chip tone="muted">Not supported by history</Chip>}
          </> : <p className="text-s14 text-muted">Gemini suggests no change: {t.why}</p>}
        </>}
        {s.kind === "rollback" && <p className="font-semibold leading-snug">Since the last change, predictions got worse. The previous version would have missed by <span className="num">{pts(s.mae_before - s.mae_after)}</span> fewer points.</p>}
        {s.kind === "gemini_cap" && <p className="font-semibold leading-snug">{t.pattern}</p>}
        {err && <ErrorNote>{err}</ErrorNote>}
        <div className="mt-auto flex flex-wrap gap-2 pt-2">
          {s.kind === "weight" && p && <>
            <Button className="!min-h-[44px] !px-5 text-s14" disabled={busy} onClick={() => decide("approve")}>Approve</Button>
            <Button kind="quiet" className="!min-h-[44px] !px-4 text-s14" disabled={busy} onClick={() => setEdit({ ...p.weights_after })}>Edit</Button>
            <Button kind="quiet" className="!min-h-[44px] !px-4 text-s14" disabled={busy} onClick={() => decide("reject")}>Reject</Button></>}
          {s.kind === "weight" && !p && <Button kind="quiet" className="!min-h-[44px] text-s14" disabled={busy} onClick={() => decide("reject")}>Close</Button>}
          {s.kind === "rollback" && <><Button className="!min-h-[44px] !px-5 text-s14" disabled={busy} onClick={() => decide("approve")}>Roll back</Button>
            <Button kind="quiet" className="!min-h-[44px] !px-4 text-s14" disabled={busy} onClick={() => decide("reject")}>Keep {cur?.version ?? "current"}</Button></>}
          {s.kind === "gemini_cap" && <><Button className="!min-h-[44px] !px-5 text-s14" disabled={busy} onClick={() => decide("approve")}>Lower to ±10%</Button>
            <Button kind="quiet" className="!min-h-[44px] !px-4 text-s14" disabled={busy} onClick={() => decide("reject")}>Keep ±20%</Button></>}
        </div>
      </div>
      <Sheet open={!!edit} onClose={() => setEdit(null)} title="Edit weights">
        {edit && <div className="space-y-2">
          {Object.entries(edit).map(([k, w]) => {
            const far = Math.abs(w - p.weights_before[k]) > 0.1 + 1e-9;
            return (
              <label key={k} className="flex items-center justify-between gap-2 rounded-tile bg-surface px-4 py-2 text-s14">
                <span>{FACTOR_NAMES[k] ?? k}{far && <span className="text-red"> · beyond ±0.10</span>}</span>
                <input type="number" step="0.01" min="0" max="1" value={w} onChange={(e) => setEdit({ ...edit, [k]: Number(e.target.value) })}
                  className="num min-h-[40px] w-20 rounded-input bg-surface2 px-2 text-right font-bold" />
              </label>
            );
          })}
          <p className="text-s12 text-muted">Weights are rescaled to add up to 1 when saved.</p>
          <Button className="w-full" disabled={busy} onClick={() => { decide("edit", edit); setEdit(null); }}>Save my version</Button>
        </div>}
      </Sheet>
    </article>
  );
}
