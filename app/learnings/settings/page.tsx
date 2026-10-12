"use client";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, ErrorNote, Skeleton, TeamBadge, useAuth, useSnack } from "@/components/ui";

type S = { rules: Record<string, any>; points: Record<string, any>; teams: { id: string; name: string; code: string; colour: string | null }[]; gemini_cap_percent: number };

// Dream11 rules and points come from config/ (filled from the app); shown here with their source.
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
  const back = <Link href="/learnings" className="inline-flex h-11 w-11 items-center justify-center rounded-full glass" aria-label="Back to learnings"><ChevronLeft size={22} /></Link>;
  if (!s) return <div className="space-y-4">{back}{err ? <ErrorNote>{err}</ErrorNote> : <Skeleton className="h-64 !rounded-card" />}</div>;
  const teams = s.teams.filter((t) => t.colour || colours[t.id]).concat(s.teams.filter((t) => !t.colour && !colours[t.id]));
  return (
    <section className="space-y-6">
      {back}
      <h1 className="num text-s26 font-bold">Settings</h1>
      <div>
        <h2 className="num mb-3 text-s20 font-bold">Dream11 team rules</h2>
        <div className="space-y-2">
          {Object.entries(s.rules).map(([fmt, r]) => (
            <div key={fmt} className="rounded-tile bg-surface p-4 text-s14 shadow-card">
              <div className="num text-s20 font-bold">{fmt}</div>
              <p className="text-muted">{r.players} players · {r.credit_budget} credits · max {r.max_per_side} from one team · C {r.captain_multiplier}x · VC {r.vc_multiplier}x</p>
              <p className="text-muted">{Object.entries(r.role_limits).map(([k, v]: any) => `${k} ${v.min}–${v.max}`).join(" · ")}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 text-s12 text-muted">From config/dream11_rules.yaml, copied from the Dream11 app.</p>
      </div>
      <div>
        <h2 className="num mb-3 text-s20 font-bold">Dream11 points table</h2>
        {Object.entries(s.points).filter(([, v]) => v && typeof v === "object").map(([fmt, table]: any) => (
          <details key={fmt} className="mb-2 rounded-tile bg-surface p-4 shadow-card">
            <summary className="min-h-[32px] cursor-pointer font-semibold">{fmt}</summary>
            <pre className="mt-2 overflow-x-auto text-s12 text-muted">{JSON.stringify(table, null, 1)}</pre>
          </details>
        ))}
        <p className="text-s12 text-muted">From config/dream11_points.yaml; values not yet copied from the app are provisional.</p>
      </div>
      <div>
        <h2 className="num mb-3 text-s20 font-bold">Gemini&apos;s limit</h2>
        <label className="flex items-center justify-between gap-3 rounded-tile bg-surface p-4 shadow-card">Change a score by at most ±
          <span className="flex items-center gap-2"><input type="number" min={0} max={20} value={cap} onChange={(e) => setCap(Number(e.target.value))} className="num min-h-[40px] w-16 rounded-input bg-surface2 px-2 text-right font-bold" />%</span>
        </label>
      </div>
      <div>
        <h2 className="num mb-3 text-s20 font-bold">Team colours</h2>
        <p className="mb-2 text-s12 text-muted">Defaults come from config/team_colours.yaml; set one here to override it.</p>
        <ul className="max-h-[420px] overflow-y-auto rounded-card bg-surface shadow-card">
          {teams.map((t) => (
            <li key={t.id} className="flex items-center gap-3 border-b hairline px-4 py-2 last:border-0">
              <TeamBadge name={t.name} code={t.code} colour={colours[t.id] ?? t.colour} size={32} />
              <span className="min-w-0 flex-1 truncate text-s14">{t.name}{!t.colour && !colours[t.id] && <span className="text-muted"> · not set</span>}</span>
              <input type="color" value={colours[t.id] ?? t.colour ?? "#3A3F52"} onChange={(e) => setColours({ ...colours, [t.id]: e.target.value.toUpperCase() })}
                className="h-10 w-10 cursor-pointer rounded-full bg-transparent" aria-label={`Colour for ${t.name}`} />
            </li>
          ))}
        </ul>
      </div>
      {err && <ErrorNote>{err}</ErrorNote>}
      <Button className="w-full" onClick={save}>Save settings</Button>
    </section>
  );
}
