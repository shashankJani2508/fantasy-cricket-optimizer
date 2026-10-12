"use client";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api, ApiError, Player, RunView } from "@/lib/api";
import { BenchSheet, CopySheet, PlayerSheet, TeamSheet } from "@/components/TeamSheet";
import { Editor } from "@/components/Editor";
import { ResultsEntry } from "@/components/ResultsEntry";
import { Scorecard } from "@/components/Scorecard";
import { BuildProgress } from "@/components/BuildProgress";
import { SetupSheet } from "@/components/SetupSheet";
import { Button, Chip, ErrorNote, pts, Skeleton, useAuth, Warning } from "@/components/ui";

export default function Page() { return <Suspense fallback={<SheetSkeleton />}><MatchView /></Suspense>; }

function MatchView() {
  const { matchId } = useParams<{ matchId: string }>();
  const mid = decodeURIComponent(matchId);
  const reveal = useSearchParams().get("reveal") === "1";
  const [run, setRun] = useState<RunView | null>(null);
  const [err, setErr] = useState<{ status: number; msg: string } | null>(null);
  const [tab, setTab] = useState<"system" | "mine">("system");
  const [sel, setSel] = useState<Player | null>(null);
  const [bench, setBench] = useState(false);
  const [copy, setCopy] = useState(false);
  const [rebuild, setRebuild] = useState(false);
  const [setup, setSetup] = useState(false);
  const [scored, setScored] = useState<boolean | null>(null);
  const { aryan } = useAuth();

  const load = useCallback(async () => {
    try {
      const { run_id } = await api(`/matches/${encodeURIComponent(mid)}/latest-run`);
      setRun(await api<RunView>(`/runs/${run_id}`));
      api(`/matches/${encodeURIComponent(mid)}/scorecard`).then(() => setScored(true)).catch(() => setScored(false));
    } catch (e: any) { setErr({ status: e instanceof ApiError ? e.status : 0, msg: e.message }); }
  }, [mid]);
  useEffect(() => { load(); }, [load]);

  if (err?.status === 404) return (
    <div className="rounded-card bg-surface p-6">
      <p className="text-s20">No team built for this match yet.</p>
      <Button className="mt-4" onClick={() => setSetup(true)}>Add credits and build my team</Button>
      {setup && <MatchSetup mid={mid} onClose={() => setSetup(false)} />}
    </div>
  );
  if (err) return <ErrorNote>{err.msg}</ErrorNote>;
  if (!run) return <SheetSkeleton />;
  if (run.status !== "done") return (
    <div className="space-y-4">
      <h1 className="num text-s40">Team not ready</h1>
      {run.status === "failed" ? <ErrorNote>The build stopped at &ldquo;{run.failed_step}&rdquo;: {run.error_message}</ErrorNote> : <p>The build is still running.</p>}
      <BuildProgress matchId={mid} runType={run.run_type} onDone={() => { setRun(null); load(); }} label="Build again" />
    </div>
  );

  const m = run.match, sys = run.teams.system!, mine = run.teams.aryan_final;
  const shown = tab === "system" ? sys : (mine ?? sys);
  const finished = m.status === "finished" || (m.start_time != null && new Date(m.start_time).getTime() < Date.now() - 3 * 3.6e6);
  return (
    <article>
      <Link href="/results" className="text-s14 text-slate underline">← Results</Link>
      <header className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="num text-s40 leading-none">{m.team_a?.code} vs {m.team_b?.code}</h1>
        <div className="flex gap-2">{run.run_type === "post_toss" ? <Chip tone="turf">Final</Chip> : <Chip tone="clay">Provisional</Chip>}<Chip>{m.format}</Chip></div>
      </header>
      <p className="mt-1 text-s16"><span className="num text-s20">{pts(shown.total_expected, 0)}</span> pts expected · <span className="num text-s20">{pts(shown.credits_used)}</span> / {run.rules.credit_budget} cr</p>
      {m.xi_announced && run.run_type === "pre_toss" && !finished && (
        <div className="mt-3 rounded-sheet bg-floodlight/30 p-3">
          <p>XI announced. Rebuild with the confirmed players?</p>
          {mine && <p className="text-s14 text-slate">Your edits stay saved on the old team; re-check them after the rebuild.</p>}
          {rebuild ? <BuildProgress matchId={mid} runType="post_toss" onDone={() => { setRun(null); load(); }} label="Rebuild team" />
            : <Button className="mt-2" onClick={() => setRebuild(true)}>Rebuild team</Button>}
        </div>
      )}
      <div role="tablist" className="mt-4 flex gap-2">
        <button role="tab" aria-selected={tab === "system"} onClick={() => setTab("system")} className={`min-h-[44px] rounded-full px-4 ${tab === "system" ? "bg-pavilion text-sightscreen" : "bg-surface"}`}>System&apos;s pick</button>
        <button role="tab" aria-selected={tab === "mine"} onClick={() => setTab("mine")} className={`min-h-[44px] rounded-full px-4 ${tab === "mine" ? "bg-pavilion text-sightscreen" : "bg-surface"}`}>My final team</button>
      </div>
      <div className="mt-4">
        {tab === "system" || finished || !aryan ? (
          <>
            {tab === "mine" && !mine && <p className="mb-2 text-s14 text-slate">{aryan ? "You haven't changed the system's pick." : "Enter the passcode to edit."}</p>}
            <TeamSheet ids={shown.player_ids} cap={shown.captain_id} vc={shown.vc_id} players={run.players} reveal={reveal && tab === "system"} onTap={setSel}
              mine={new Set(tab === "mine" ? shown.player_ids.filter((p) => !sys.player_ids.includes(p)) : [])} />
            {tab === "system" && <p className="mt-2 text-center text-s12 text-slate">Picked by the system</p>}
          </>
        ) : <Editor run={run} onSaved={load} />}
      </div>
      {run.warnings.length > 0 && (
        <div className="mt-4"><Warning><strong>Check this yourself</strong><ul className="mt-1 list-disc pl-4">{run.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Warning></div>
      )}
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <Button kind="quiet" onClick={() => setBench(true)}>Bench: {run.bench.length} players ›</Button>
        <Button kind="quiet" onClick={() => setCopy(true)}>Copy to Dream11 ›</Button>
      </div>
      {finished && scored === false && aryan && <ResultsEntry run={run} onSaved={() => { setScored(true); load(); }} />}
      {finished && scored === false && !aryan && <p className="mt-6 text-s14 text-slate">Results not entered yet.</p>}
      {scored && <Scorecard matchId={mid} />}
      <PlayerSheet p={sel} run={run} onClose={() => setSel(null)} isCap={sel?.player_id === shown.captain_id} isVc={sel?.player_id === shown.vc_id} />
      <BenchSheet open={bench} onClose={() => setBench(false)} bench={run.bench} players={run.players} onTap={(p) => { setBench(false); setSel(p); }} />
      <CopySheet open={copy} onClose={() => setCopy(false)} ids={shown.player_ids} cap={shown.captain_id} vc={shown.vc_id} players={run.players} />
    </article>
  );
}

function MatchSetup({ mid, onClose }: { mid: string; onClose: () => void }) {
  const [m, setM] = useState<any>(null);
  useEffect(() => { api(`/matches/${encodeURIComponent(mid)}/prepare`, { method: "POST" }).then((r) => setM(r.match)).catch(() => onClose()); }, [mid, onClose]);
  return m ? <SetupSheet match={m} onClose={onClose} /> : null;
}

function SheetSkeleton() {
  return (
    <div aria-label="Loading team sheet">
      <Skeleton className="h-10 w-48" /><Skeleton className="mt-2 h-5 w-64" />
      <div className="mx-auto mt-4 flex aspect-[4/5] max-w-[520px] flex-col justify-around rounded-[50%/42%] bg-turf/40 p-8">
        {[1, 4, 2, 4].map((n, i) => <div key={i} className="flex justify-center gap-3">{Array.from({ length: n }).map((_, j) => <Skeleton key={j} className="h-12 w-12 !rounded-full" />)}</div>)}
      </div>
    </div>
  );
}
