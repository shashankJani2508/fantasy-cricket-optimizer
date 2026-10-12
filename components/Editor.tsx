"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Player, RunView } from "@/lib/api";
import { check, ROLES } from "@/lib/gate";
import { Button, ErrorNote, haptic, PlayerAvatar, pts, Sheet, useAuth, useSnack } from "./ui";
import { TeamSheet } from "./TeamSheet";

// "My final team": starts from the latest saved final team (or the system's pick); instant meters from the client
// mirror, authoritative check on save from the server gate.
export function Editor({ run, onSaved }: { run: RunView; onSaved: () => void }) {
  const sys = run.teams.system!;
  const start = run.teams.aryan_final ?? sys;
  const [ids, setIds] = useState<string[]>(start.player_ids);
  const [cap, setCap] = useState(start.captain_id);
  const [vc, setVc] = useState(start.vc_id);
  const [why, setWhy] = useState("");
  const [sel, setSel] = useState<Player | null>(null);
  const [swapFor, setSwapFor] = useState<Player | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { ask } = useAuth();
  const snack = useSnack();
  useEffect(() => { setIds(start.player_ids); setCap(start.captain_id); setVc(start.vc_id); }, [start]);

  const P = run.players;
  const g = useMemo(() => check(ids, cap, vc, P, run.rules), [ids, cap, vc, P, run.rules]);
  const mine = new Set(ids.filter((p) => !sys.player_ids.includes(p)));
  const total = ids.reduce((s, p) => s + (P[p]?.expected ?? 0), 0) + (run.rules.captain_multiplier - 1) * (P[cap]?.expected ?? 0) + (run.rules.vc_multiplier - 1) * (P[vc]?.expected ?? 0);
  const pool = new Set(run.pool.length ? run.pool : Object.keys(P));
  const candidates = swapFor ? Object.values(P).filter((p) => !ids.includes(p.player_id) && pool.has(p.player_id) && p.expected != null)
    .sort((a, b) => (b.expected ?? 0) - (a.expected ?? 0)) : [];

  const swap = (out: string, inn: string) => {
    setIds((l) => l.map((p) => (p === out ? inn : p)));
    if (cap === out) setCap(inn);
    if (vc === out) setVc(inn);
    setSwapFor(null); setSel(null);
  };
  const save = async () => {
    if (!(await ask())) return;
    setSaving(true); setErr(null);
    try {
      await api(`/runs/${run.run_id}/final-team`, { method: "PUT", body: { player_ids: ids, captain_id: cap, vc_id: vc, reason: why || null } });
      haptic(); snack({ text: "Your team is saved." }); onSaved();
    } catch (e: any) { setErr(e.message); }
    setSaving(false);
  };

  const over = g.used - run.rules.credit_budget;
  return (
    <div>
      <div className="sticky top-0 z-30 -mx-4 mb-3 space-y-2 bg-app px-4 py-2 shadow-sm" aria-label="Team rules">
        <div>
          <div className="flex justify-between text-s14"><span>Credits</span>
            <span className={`num text-s16 ${over > 0 ? "text-ball" : ""}`}>{pts(g.used)} / {run.rules.credit_budget}{over > 0 ? ` · ${pts(over, 2)} over` : ""}</span></div>
          <div className="h-2 rounded-full bg-slate/15"><div className={`h-2 rounded-full ${over > 0 ? "bg-ball" : "bg-turf"}`} style={{ width: `${Math.min(100, (g.used / run.rules.credit_budget) * 100)}%` }} /></div>
        </div>
        <div className="flex flex-wrap gap-2 text-s14">
          {ROLES.map((r) => {
            const lim = run.rules.role_limits[r], n = g.roles[r], bad = n < lim.min || n > lim.max;
            return <span key={r} className={`rounded-full px-2 py-1 ${bad ? "bg-ball text-white" : "bg-slate/15"}`}>{r} <span className="num">{n}</span> <span className="text-s12">({lim.min}–{lim.max})</span></span>;
          })}
          <span className="rounded-full bg-slate/15 px-2 py-1">
            {Object.entries(g.sides).map(([t, n]) => <span key={t} className={n > run.rules.max_per_side ? "text-ball" : ""}>{codeOf(run, t)} <span className="num">{n}</span> </span>)}
            <span className="text-s12">(max {run.rules.max_per_side})</span>
          </span>
        </div>
        <p className="text-s14">{g.passed ? <span className="text-turf">Valid team · {pts(total)} expected points</span> : <span className="text-ball">{g.fails[0]}</span>}</p>
      </div>
      <TeamSheet ids={ids} cap={cap} vc={vc} players={P} reveal={false} onTap={setSel} mine={mine} />
      <label className="mt-4 block text-s14">Why the change? (optional)
        <input maxLength={200} value={why} onChange={(e) => setWhy(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-input border border-fg/10 bg-surface px-3" />
      </label>
      {err && <div className="mt-3"><ErrorNote>{err}</ErrorNote></div>}
      <div className="mt-4 flex gap-3">
        <Button className="flex-1" disabled={!g.passed || saving} onClick={save}>{saving ? "Saving…" : "Save my team"}</Button>
        <Button kind="quiet" onClick={() => { setIds(sys.player_ids); setCap(sys.captain_id); setVc(sys.vc_id); }}>Reset to system&apos;s pick</Button>
      </div>

      <Sheet open={!!sel && !swapFor} onClose={() => setSel(null)} title={sel?.name ?? ""}>
        {sel && (
          <div className="space-y-3">
            <p className="text-s14 text-slate">{sel.team_code} · {sel.role} · {sel.credits} cr · <span className="num text-s16 text-fg">{pts(sel.expected)}</span> expected</p>
            <Button className="w-full" onClick={() => setSwapFor(sel)}>Swap</Button>
            <div className="flex gap-3">
              <Button kind="quiet" className="flex-1" disabled={cap === sel.player_id} onClick={() => { if (vc === sel.player_id) setVc(cap); setCap(sel.player_id); setSel(null); }}>Make captain</Button>
              <Button kind="quiet" className="flex-1" disabled={vc === sel.player_id} onClick={() => { if (cap === sel.player_id) setCap(vc); setVc(sel.player_id); setSel(null); }}>Make vice-captain</Button>
            </div>
          </div>
        )}
      </Sheet>
      <Sheet open={!!swapFor} onClose={() => setSwapFor(null)} title={`Swap ${swapFor?.name ?? ""}`}>
        {swapFor && (candidates.length === 0 ? <p className="text-slate">No other players in the pool for this run.</p> : (
          <ul className="divide-y divide-slate/20">
            {candidates.map((c) => {
              const dc = c.credits - swapFor.credits, dp = (c.expected ?? 0) - (swapFor.expected ?? 0);
              return (
                <li key={c.player_id}>
                  <button className="flex min-h-[56px] w-full items-center gap-3 py-2 text-left" onClick={() => swap(swapFor.player_id, c.player_id)}>
                    <PlayerAvatar name={c.name} url={c.image_url} colour={c.colour} size={40} />
                    <div className="flex-1"><div className="font-semibold">{c.name}</div><div className="text-s12 text-slate">{c.team_code} · {c.role} · {c.credits} cr</div></div>
                    <span className="text-s14">{dc >= 0 ? "+" : ""}{pts(dc)} cr · <span className={dp >= 0 ? "text-turf" : "text-ball"}>{dp >= 0 ? "+" : ""}{pts(dp)} pts</span></span>
                  </button>
                </li>
              );
            })}
          </ul>
        ))}
      </Sheet>
    </div>
  );
}

const codeOf = (run: RunView, team: string) => [run.match.team_a, run.match.team_b].find((t) => t?.name === team)?.code ?? team;
