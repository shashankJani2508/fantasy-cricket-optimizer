"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Player, RunView } from "@/lib/api";
import { check, ROLES } from "@/lib/gate";
import { Button, ErrorNote, haptic, PlayerAvatar, pts, Sheet, useAuth, useSnack } from "./ui";
import { TeamSheet } from "./TeamSheet";

// "My final team": instant meters from the client mirror; the server gate is authoritative on save.
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
  const sig = (i: string[], c: string, v: string) => [...i].sort().join(",") + "|" + c + "|" + v;
  const [savedSig, setSavedSig] = useState<string | null>(run.teams.aryan_final ? sig(start.player_ids, start.captain_id, start.vc_id) : null);
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
      haptic(); snack({ text: "Your team is saved." }); setSavedSig(sig(ids, cap, vc)); onSaved();
    } catch (e: any) { setErr(e.message); }
    setSaving(false);
  };
  const over = g.used - run.rules.credit_budget;
  const codeOf = (team: string) => [run.match.team_a, run.match.team_b].find((t) => t?.name === team)?.code ?? team;

  return (
    <div>
      <div className="glass sticky top-3 z-30 mb-4 space-y-3 rounded-tile p-4 shadow-card" aria-label="Team rules">
        <div>
          <div className="mb-1.5 flex justify-between text-s12"><span className="text-muted">Credits</span>
            <span className={`num text-s14 font-bold ${over > 0 ? "text-red" : ""}`}>{pts(g.used)} / {run.rules.credit_budget}{over > 0 ? ` · ${pts(over, 2)} over` : ""}</span></div>
          <div className="h-2 rounded-full bg-surface2"><div className={`h-2 rounded-full transition-all ${over > 0 ? "bg-red" : "bg-green"}`} style={{ width: `${Math.min(100, (g.used / run.rules.credit_budget) * 100)}%` }} /></div>
        </div>
        <div className="flex flex-wrap gap-1.5 text-s12">
          {ROLES.map((r) => {
            const lim = run.rules.role_limits[r], n = g.roles[r], bad = n < lim.min || n > lim.max;
            return <span key={r} className={`rounded-full px-2.5 py-1 font-semibold ${bad ? "bg-red text-white" : "bg-surface2"}`}>{r} <span className="num">{n}</span> <span className="opacity-60">{lim.min}–{lim.max}</span></span>;
          })}
          {Object.entries(g.sides).map(([t, n]) => <span key={t} className={`rounded-full px-2.5 py-1 font-semibold ${n > run.rules.max_per_side ? "bg-red text-white" : "bg-surface2"}`}>{codeOf(t)} <span className="num">{n}</span></span>)}
          <span className="rounded-full px-1 py-1 text-muted">max {run.rules.max_per_side} a side</span>
        </div>
        <p className="text-s14">{g.passed ? <span className="text-green">Valid team · <span className="num font-bold">{pts(total)}</span> expected points</span> : <span className="text-red">{g.fails[0]}</span>}</p>
      </div>
      <TeamSheet ids={ids} cap={cap} vc={vc} players={P} reveal={false} onTap={setSel} mine={mine} caption="Tap a player to swap him or change captaincy" />
      <input maxLength={200} value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Why the change? (optional)" aria-label="Why the change? (optional)"
        className="mt-4 min-h-[48px] w-full rounded-full bg-surface2 px-5 text-s14 placeholder:text-muted" />
      {err && <div className="mt-3"><ErrorNote>{err}</ErrorNote></div>}
      {!g.passed && <p className="mt-4 text-center text-s12 text-muted">{g.fails[0]}</p>}
      <div className="mt-3 flex gap-2">
        {savedSig === sig(ids, cap, vc)
          ? <Button className="flex-1 !bg-red/40 !text-white/90 !shadow-none" disabled>Team saved ✓</Button>
          : <Button className="flex-1" disabled={!g.passed || saving} onClick={save}>{saving ? "Saving…" : "Save my team"}</Button>}
        <Button kind="quiet" onClick={() => { setIds(sys.player_ids); setCap(sys.captain_id); setVc(sys.vc_id); }}>Reset</Button>
      </div>

      <Sheet open={!!sel && !swapFor} onClose={() => setSel(null)} title={sel?.name ?? ""}>
        {sel && (
          <div className="space-y-3">
            <p className="text-s14 text-muted">{sel.team_code} · {sel.role} · <span className="num font-bold text-ink">{sel.credits}</span> cr · <span className="num font-bold text-ink">{pts(sel.expected)}</span> expected</p>
            <Button className="w-full" onClick={() => setSwapFor(sel)}>Swap</Button>
            <div className="flex gap-2">
              <Button kind="quiet" className="flex-1" disabled={cap === sel.player_id} onClick={() => { if (vc === sel.player_id) setVc(cap); setCap(sel.player_id); setSel(null); }}>Make captain</Button>
              <Button kind="quiet" className="flex-1" disabled={vc === sel.player_id} onClick={() => { if (cap === sel.player_id) setCap(vc); setVc(sel.player_id); setSel(null); }}>Make VC</Button>
            </div>
          </div>
        )}
      </Sheet>
      <Sheet open={!!swapFor} onClose={() => setSwapFor(null)} title={`Swap ${swapFor?.name ?? ""}`}>
        {swapFor && (candidates.length === 0 ? <p className="text-muted">No other players in the pool for this run.</p> : (
          <ul className="space-y-2">
            {candidates.map((c) => {
              const dc = c.credits - swapFor.credits, dp = (c.expected ?? 0) - (swapFor.expected ?? 0);
              return (
                <li key={c.player_id}>
                  <button className="flex min-h-[60px] w-full items-center gap-3 rounded-tile bg-surface p-3 text-left" onClick={() => swap(swapFor.player_id, c.player_id)}>
                    <PlayerAvatar name={c.name} url={c.image_url} colour={c.colour} size={40} />
                    <div className="min-w-0 flex-1"><div className="truncate font-semibold">{c.name}</div><div className="text-s12 text-muted">{c.team_code} · {c.role} · {c.credits} cr</div></div>
                    <span className="num text-right text-s14 font-bold"><span className={dc > 0 ? "text-red" : "text-green"}>{dc >= 0 ? "+" : ""}{pts(dc)} cr</span><br />
                      <span className={dp >= 0 ? "text-green" : "text-red"}>{dp >= 0 ? "+" : ""}{pts(dp)} pts</span></span>
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
