"use client";
import { Camera } from "lucide-react";
import { useState } from "react";
import { api, RunView } from "@/lib/api";
import { screenshotForm } from "@/lib/images";
import { Button, ErrorNote, haptic, PlayerAvatar, useAuth, useSnack } from "./ui";

// After the match: Aryan's Dream11 points for his players (screenshot read by Gemini, or typed) and his rank.
export function ResultsEntry({ run, onSaved }: { run: RunView; onSaved: () => void }) {
  const team = (run.teams.aryan_final ?? run.teams.system)!.player_ids;
  const [vals, setVals] = useState<Record<string, string>>({});
  const [unsure, setUnsure] = useState<Set<string>>(new Set());
  const [rank, setRank] = useState("");
  const [via, setVia] = useState<"screenshot" | "typed">("typed");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const { ask } = useAuth();
  const snack = useSnack();

  const upload = async (files: FileList | null) => {
    if (!files?.length || !(await ask())) return;
    setBusy(true); setErr(null);
    const form = await screenshotForm(files);
    try {
      const r = await api(`/matches/${encodeURIComponent(run.match_id)}/screenshots/points`, { method: "POST", form });
      const v = { ...vals }, u = new Set<string>();
      let missed = 0;
      for (const x of r.rows) {
        if (x.player_id && team.includes(x.player_id)) { v[x.player_id] = x.points == null ? "" : String(x.points); if (x.unsure) u.add(x.player_id); }
        else missed++;
      }
      setVals(v); setUnsure(u); setVia("screenshot");
      if (r.rank) setRank(String(r.rank));
      setNote(missed ? `${missed} names on the screenshot aren't in your team; they were left out.` : null);
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  const complete = team.every((p) => vals[p] !== undefined && vals[p] !== "" && !isNaN(Number(vals[p])));
  const save = async () => {
    if (!(await ask())) return;
    setBusy(true); setErr(null);
    try {
      const r = await api(`/matches/${encodeURIComponent(run.match_id)}/results`, { method: "PUT",
        body: { rows: team.map((p) => ({ player_id: p, points: Number(vals[p]) })), rank: rank ? Number(rank) : null, entered_via: via } });
      haptic();
      snack({ text: r.mismatches.length ? `Saved. Our calculation differs for ${r.mismatches.length} players. Check the points table in Settings.` : "Results saved. Scorecard ready." });
      onSaved();
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <section className="space-y-4" aria-labelledby="h-res">
      <h2 id="h-res" className="num text-s20 font-bold">Enter results</h2>
      <label className={`flex cursor-pointer flex-col items-center gap-2 rounded-card border-2 border-dashed border-white/15 bg-surface px-4 py-6 text-center ${busy ? "opacity-60" : ""}`}>
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface2"><Camera size={22} strokeWidth={1.75} /></span>
        <span className="font-semibold">{busy ? "Working…" : "Upload Dream11 points screenshot"}</span>
        <span className="text-s12 text-muted">or type the points below</span>
        <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="sr-only" disabled={busy} onChange={(e) => upload(e.target.files)} />
      </label>
      {note && <p className="text-s12 text-muted">{note}</p>}
      <ul className="space-y-2">
        {team.map((pid) => {
          const p = run.players[pid];
          return (
            <li key={pid} className={`flex items-center gap-3 rounded-tile bg-surface p-2.5 pr-3 ${unsure.has(pid) ? "border-l-4 border-amber" : ""}`}>
              <PlayerAvatar name={p.name} url={p.image_url} colour={p.colour} size={36} />
              <span className="min-w-0 flex-1 truncate text-s14 font-semibold">{p.name}{unsure.has(pid) && <span className="font-normal text-amber"> · Check this</span>}</span>
              <input aria-label={`Points for ${p.name}`} inputMode="decimal" value={vals[pid] ?? ""} placeholder="Pts" onChange={(e) => { setVals({ ...vals, [pid]: e.target.value }); setVia("typed"); }}
                className="num min-h-[40px] w-16 rounded-input bg-surface2 px-2 text-right text-s16 font-bold placeholder:text-muted/60" />
            </li>
          );
        })}
      </ul>
      <label className="flex items-center justify-between gap-3 rounded-tile bg-surface p-3 text-s14">Your rank (optional)
        <input inputMode="numeric" value={rank} onChange={(e) => setRank(e.target.value.replace(/\D/g, ""))} className="num min-h-[40px] w-28 rounded-input bg-surface2 px-2 text-right text-s16 font-bold" />
      </label>
      {err && <ErrorNote>{err}</ErrorNote>}
      <Button className="w-full" disabled={!complete || busy} onClick={save}>Save results</Button>
    </section>
  );
}
