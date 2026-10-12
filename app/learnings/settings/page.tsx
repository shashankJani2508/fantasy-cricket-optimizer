"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, ErrorNote, Skeleton, useAuth, useSnack } from "@/components/ui";

type S = { rules: Record<string, any>; points: Record<string, any>; teams: { id: string; name: string; code: string; colour: string | null }[]; gemini_cap_percent: number };

// Dream11 rules and points come from config/ (filled by us from the app); shown here with their source.
export default function Settings() {
  const [s, setS] = useState<S | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [colours, setColours] = useState<Record<string, string>>({});
  const [cap, setCap] = useState(20);
  const { ask } = useAuth();
  const snack = useSnack();
  useEffect(() => { api<S>("/settings").then((r) => { setS(r); setCap(r.gemini_cap_percent); }).catch((e) => setErr(e.message)); }, []);
  const save = async () => {
    if (!(await ask())) return;
    try { await api("/settings", { method: "PUT", body: { gemini_cap_percent: cap, team_colours: colours } }); snack({ text: "Settings saved." }); setErr(null); }
    catch (e: any) { setErr(e.message); }
  };
  if (!s) return err ? <ErrorNote>{err}</ErrorNote> : <Skeleton className="h-64" />;
  return (
    <section className="space-y-6">
      <Link href="/learnings" className="text-s14 text-slate underline">← Learnings</Link>
      <h1 className="num text-s40">Settings</h1>
      <div>
        <h2 className="num text-s28">Dream11 team rules</h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          {Object.entries(s.rules).map(([fmt, r]) => (
            <div key={fmt} className="rounded-sheet bg-surface p-3 text-s14">
              <div className="num text-s20">{fmt}</div>
              <div>{r.players} players · {r.credit_budget} credits</div>
              <div>Max {r.max_per_side} from one team · C {r.captain_multiplier}x · VC {r.vc_multiplier}x</div>
              <div>{Object.entries(r.role_limits).map(([k, v]: any) => `${k} ${v.min}–${v.max}`).join(" · ")}</div>
            </div>
          ))}
        </div>
        <p className="mt-1 text-s12 text-slate">From config/dream11_rules.yaml, copied from the Dream11 app.</p>
      </div>
      <div>
        <h2 className="num text-s28">Dream11 points table</h2>
        {Object.entries(s.points).filter(([, v]) => v && typeof v === "object").map(([fmt, table]: any) => (
          <details key={fmt} className="mt-2 rounded-sheet bg-surface p-3">
            <summary className="min-h-[44px] cursor-pointer font-semibold">{fmt}</summary>
            <pre className="overflow-x-auto text-s12">{JSON.stringify(table, null, 1)}</pre>
          </details>
        ))}
        <p className="mt-1 text-s12 text-slate">From config/dream11_points.yaml. Each value lists its source; values not yet copied from the app are provisional.</p>
      </div>
      <div>
        <h2 className="num text-s28">Gemini&apos;s limit</h2>
        <label className="mt-2 flex items-center gap-3">Change a score by at most ±
          <input type="number" min={0} max={20} value={cap} onChange={(e) => setCap(Number(e.target.value))} className="num min-h-[44px] w-20 rounded-input border border-fg/10 bg-surface px-2 text-s16" />%
        </label>
      </div>
      <div>
        <h2 className="num text-s28">Team colours</h2>
        {s.teams.length === 0 ? <p className="text-slate">No recent teams.</p> : s.teams.map((t) => (
          <label key={t.id} className="mt-2 flex items-center gap-3">
            <input type="color" value={colours[t.id] ?? t.colour ?? "#6B7385"} onChange={(e) => setColours({ ...colours, [t.id]: e.target.value.toUpperCase() })} className="h-11 w-11 rounded-input" aria-label={`Colour for ${t.name}`} />
            <span>{t.code} · {t.name}{!t.colour && !colours[t.id] && <span className="text-s12 text-slate"> (not set)</span>}</span>
          </label>
        ))}
      </div>
      {err && <ErrorNote>{err}</ErrorNote>}
      <Button onClick={save}>Save settings</Button>
    </section>
  );
}
