"use client";
import { ChevronLeft, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api, ApiError, Player, RunView } from "@/lib/api";
import { matchArt } from "@/lib/teams";
import { BenchRowButton, BenchSheet, CopySheet, PlayerSheet, TeamSheet } from "@/components/TeamSheet";
import { Editor } from "@/components/Editor";
import { ResultsEntry } from "@/components/ResultsEntry";
import { Scorecard } from "@/components/Scorecard";
import { BuildProgress } from "@/components/BuildProgress";
import { SetupSheet } from "@/components/SetupSheet";
import { Button, Chip, ErrorNote, PillTabs, pts, Skeleton, TeamBadge, useAuth, Warning } from "@/components/ui";

export default function Page() { return <Suspense fallback={<SheetSkeleton />}><MatchView /></Suspense>; }
type Tab = "system" | "mine" | "scorecard";

function MatchView() {
  const { matchId } = useParams<{ matchId: string }>();
  const mid = decodeURIComponent(matchId);
  const reveal = useSearchParams().get("reveal") === "1";
  const [run, setRun] = useState<RunView | null>(null);
  const [err, setErr] = useState<{ status: number; msg: string } | null>(null);
  const [tab, setTab] = useState<Tab>("system");
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

  const back = <Link href="/results" className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-full glass" aria-label="Back to results"><ChevronLeft size={22} /></Link>;
  if (err?.status === 404) return (
    <div>{back}
      <div className="rounded-card bg-surface p-6 shadow-card">
        <p className="num text-s20 font-bold">No team built for this match yet</p>
        <Button className="mt-5 w-full" onClick={() => setSetup(true)}>Add credits and build my team</Button>
      </div>
      {setup && <MatchSetup mid={mid} onClose={() => setSetup(false)} />}
    </div>
  );
  if (err) return <div>{back}<ErrorNote>{err.msg}</ErrorNote></div>;
  if (!run) return <SheetSkeleton />;
  if (run.status !== "done") return (
    <div className="space-y-4">{back}
      <h1 className="num text-s26 font-bold">Team not ready</h1>
      {run.status === "failed" ? <ErrorNote>The build stopped at &ldquo;{run.failed_step}&rdquo;: {run.error_message}</ErrorNote> : <p className="text-muted">The build is still running.</p>}
      <BuildProgress matchId={mid} runType={run.run_type} onDone={() => { setRun(null); load(); }} label="Build again" />
    </div>
  );

  const m = run.match, sys = run.teams.system!, mine = run.teams.aryan_final;
  const shown = tab === "mine" ? (mine ?? sys) : sys;
  const finished = m.status === "finished" || (m.start_time != null && new Date(m.start_time).getTime() < Date.now() - 3 * 3.6e6);
  const tabs: { key: Tab; label: string }[] = [{ key: "system", label: "System's pick" }, { key: "mine", label: "My final team" }];
  if (scored) tabs.push({ key: "scorecard", label: "Scorecard" });

  return (
    <article className="space-y-4">
      {back}
      <header className="noise relative overflow-hidden rounded-card p-5 shadow-card" style={matchArt(m.team_a?.colour, m.team_b?.colour)}>
        <div className="relative flex items-center justify-between">
          <Chip tone="glass">{m.format}</Chip>
          {run.run_type === "post_toss" ? <Chip tone="green">Final</Chip> : <Chip tone="amber">Provisional</Chip>}
        </div>
        <div className="relative my-4 flex items-center justify-center gap-5">
          <div className="flex flex-col items-center gap-1"><TeamBadge name={m.team_a?.name} code={m.team_a?.code} colour={m.team_a?.colour} size={52} /><span className="num font-bold">{m.team_a?.code}</span></div>
          <span className="num text-s34 font-extrabold italic text-orange">VS</span>
          <div className="flex flex-col items-center gap-1"><TeamBadge name={m.team_b?.name} code={m.team_b?.code} colour={m.team_b?.colour} size={52} /><span className="num font-bold">{m.team_b?.code}</span></div>
        </div>
        <div className="relative flex items-end justify-between">
          <div><div className="num text-s34 font-extrabold leading-none">{pts(shown.total_expected, 0)}</div><div className="text-s12 text-muted">expected points</div></div>
          <div className="text-right"><div className="num text-s20 font-bold leading-none">{pts(shown.credits_used)} <span className="text-s14 text-muted">/ {run.rules.credit_budget}</span></div><div className="text-s12 text-muted">credits</div></div>
        </div>
      </header>

      {m.xi_announced && run.run_type === "pre_toss" && !finished && (
        <div className="rounded-tile border border-amber/30 bg-amber/10 p-4">
          <p className="font-semibold">XI announced. Rebuild with the confirmed players?</p>
          {mine && <p className="mt-1 text-s14 text-muted">Your edits stay saved on the old team; check them after the rebuild.</p>}
          <div className="mt-3">{rebuild ? <BuildProgress matchId={mid} runType="post_toss" onDone={() => { setRun(null); load(); }} label="Rebuild team" />
            : <Button onClick={() => setRebuild(true)}>Rebuild team</Button>}</div>
        </div>
      )}

      <PillTabs label="Team views" tabs={tabs} value={tab} onChange={setTab} />

      {tab === "scorecard" ? <Scorecard matchId={mid} /> : tab === "mine" && aryan && !finished ? <Editor run={run} onSaved={load} /> : (
        <>
          {tab === "mine" && !mine && <p className="text-s14 text-muted">{finished ? "You kept the system's pick." : "Enter the passcode to edit."}</p>}
          <TeamSheet ids={shown.player_ids} cap={shown.captain_id} vc={shown.vc_id} players={run.players} reveal={reveal && tab === "system"} onTap={setSel}
            mine={new Set(tab === "mine" ? shown.player_ids.filter((p) => !sys.player_ids.includes(p)) : [])}
            caption={tab === "system" ? "Picked by the system" : "Your final team"} />
        </>
      )}

      {tab !== "scorecard" && run.warnings.length > 0 && (
        <Warning><strong className="font-semibold">Check this yourself</strong><ul className="mt-1 space-y-0.5 text-muted">{run.warnings.map((w) => <li key={w}>· {w}</li>)}</ul></Warning>
      )}
      {tab !== "scorecard" && (
        <div className="space-y-2">
          <BenchRowButton bench={run.bench} players={run.players} onOpen={() => setBench(true)} />
          <button onClick={() => setCopy(true)} className="flex min-h-[64px] w-full items-center gap-3 rounded-tile bg-surface px-4 py-3 text-left shadow-card">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface2"><ClipboardCheck size={18} strokeWidth={1.75} /></span>
            <span className="flex-1 font-semibold">Copy to Dream11</span><span className="text-s14 text-muted">›</span>
          </button>
        </div>
      )}
      {finished && scored === false && aryan && <ResultsEntry run={run} onSaved={() => { setScored(true); setTab("scorecard"); load(); }} />}
      {finished && scored === false && !aryan && <p className="text-s14 text-muted">Results not entered yet.</p>}

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
    <div aria-label="Loading team sheet" className="space-y-4">
      <Skeleton className="h-11 w-11 !rounded-full" />
      <Skeleton className="h-52 !rounded-card" />
      <div className="flex flex-col justify-around gap-6 rounded-card bg-surface p-6">
        {[1, 4, 3, 3].map((n, i) => <div key={i} className="flex justify-center gap-3">{Array.from({ length: n }).map((_, j) => <Skeleton key={j} className="h-12 w-12 !rounded-full" />)}</div>)}
      </div>
    </div>
  );
}
