"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Match, Role } from "@/lib/api";
import { ROLES } from "@/lib/gate";
import { Button, Chip, ErrorNote, haptic, PlayerAvatar, Sheet, Skeleton } from "./ui";
import { BuildProgress } from "./BuildProgress";

type Row = { player_id: string; name: string; team: string; team_code: string; colour: string | null; image_url: string | null;
  role: Role | null; credits: number | null; via: "screenshot" | "typed" | "prefill"; unsure: boolean; from_last_match: boolean; out: boolean };
type Unmatched = { name_on_screen: string; team_code: string | null; role: Role | null; credits: number | null; unsure: boolean; suggestions: string[] };

export function SetupSheet({ match, onClose }: { match: Match; onClose: () => void }) {
  const [step, setStep] = useState<1 | 2>(1);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [budget, setBudget] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [unmatched, setUnmatched] = useState<Unmatched[]>([]);
  const [saving, setSaving] = useState(false);
  const router = useRouter();

  useEffect(() => {
    api(`/matches/${encodeURIComponent(match.id)}/prepare`, { method: "POST" }).then((r) => {
      setBudget(r.budget); setNote(r.note);
      setRows(r.players.map((p: any) => ({ ...p, via: p.from_last_match ? "prefill" : "typed", unsure: false, out: false })));
    }).catch((e) => setErr(e.message));
  }, [match.id]);

  const update = (id: string, patch: Partial<Row>) => setRows((rs) => rs && rs.map((r) => (r.player_id === id ? { ...r, ...patch } : r)));

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setReading(true); setErr(null);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const r = await api(`/matches/${encodeURIComponent(match.id)}/screenshots/player-list`, { method: "POST", form });
      const left: Unmatched[] = [];
      for (const x of r.rows) {
        if (x.player_id) update(x.player_id, { role: x.role, credits: x.credits, via: "screenshot", unsure: x.unsure, from_last_match: false, out: false });
        else left.push(x);
      }
      setUnmatched(left);
    } catch (e: any) { setErr(e.message); }
    setReading(false);
  };

  const confirmLink = async (u: Unmatched, pid: string) => {
    try {
      await api("/players/link", { method: "POST", body: { player_id: pid, name_on_screen: u.name_on_screen } });
      update(pid, { role: u.role, credits: u.credits, via: "screenshot", unsure: u.unsure, out: false });
      setUnmatched((l) => l.filter((x) => x !== u));
    } catch (e: any) { setErr(e.message); }
  };

  const active = rows?.filter((r) => !r.out) ?? [];
  const complete = active.length >= 11 && active.every((r) => r.role && r.credits != null && r.credits > 0);

  const save = async () => {
    setSaving(true); setErr(null);
    try {
      await api(`/matches/${encodeURIComponent(match.id)}/credits`, { method: "PUT", body: { rows: active.map((r) => ({ player_id: r.player_id, credits: r.credits, role: r.role, entered_via: r.via })) } });
      haptic(); setStep(2);
    } catch (e: any) { setErr(e.message); }
    setSaving(false);
  };

  const runType = match.xi_announced ? "post_toss" : "pre_toss";
  return (
    <Sheet open onClose={onClose} title={step === 1 ? "Add credits and roles from Dream11" : "Build my team"} wide>
      <p className="mb-3 text-s14 text-slate">{step} of 2 · {match.team_a?.code} vs {match.team_b?.code}</p>
      {err && <div className="mb-3"><ErrorNote>{err}</ErrorNote></div>}
      {step === 1 && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <label className={`inline-flex min-h-[44px] cursor-pointer items-center rounded-full bg-turf px-5 font-semibold text-white ${reading ? "opacity-50" : ""}`}>
              {reading ? "Reading screenshot…" : "Upload Dream11 screenshot"}
              <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="sr-only" disabled={reading} onChange={(e) => upload(e.target.files)} />
            </label>
            <span className="self-center text-s14 text-slate">or type them in the table below</span>
          </div>
          {note && <p className="text-s12 text-slate">{note}</p>}
          {unmatched.map((u) => (
            <div key={u.name_on_screen} className="rounded-sheet bg-floodlight/25 p-3 text-s14">
              <p>We couldn&apos;t match &lsquo;{u.name_on_screen}&rsquo;. {u.suggestions.length ? "Is this one of these?" : "Who is it?"}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {u.suggestions.map((pid) => {
                  const r = rows?.find((x) => x.player_id === pid);
                  return r && <Button key={pid} kind="quiet" onClick={() => confirmLink(u, pid)}>Yes, {r.name} ({r.team_code})</Button>;
                })}
                <select aria-label={`Choose the player for ${u.name_on_screen}`} className="min-h-[44px] rounded-input border border-fg/10 bg-surface px-2"
                  defaultValue="" onChange={(e) => e.target.value && confirmLink(u, e.target.value)}>
                  <option value="">Choose another…</option>
                  {rows?.map((r) => <option key={r.player_id} value={r.player_id}>{r.name} ({r.team_code})</option>)}
                </select>
              </div>
            </div>
          ))}
          {!rows ? <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div> : rows.length === 0 ? (
            <ErrorNote>No squad is available for this match yet. Try again closer to the start.</ErrorNote>
          ) : (
            <table className="w-full text-s14">
              <thead className="text-left text-s12 text-slate"><tr><th className="py-2">Player</th><th>Role</th><th>Credits</th><th><span className="sr-only">In list</span></th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.player_id} className={`border-t border-fg/10 ${r.unsure ? "bg-floodlight/25" : ""} ${r.out ? "opacity-40" : ""}`}>
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <PlayerAvatar name={r.name} url={r.image_url} colour={r.colour} size={32} />
                        <div><div>{r.name}</div><div className="text-s12 text-slate">{r.team_code}{r.unsure && " · Check this"}{r.from_last_match && " · from last match"}</div></div>
                      </div>
                    </td>
                    <td>
                      <select aria-label={`Role for ${r.name}`} value={r.role ?? ""} disabled={r.out} onChange={(e) => update(r.player_id, { role: (e.target.value || null) as Role, via: r.via === "screenshot" ? "screenshot" : "typed", unsure: false })}
                        className="min-h-[44px] rounded-input border border-fg/10 bg-surface px-1">
                        <option value="">–</option>{ROLES.map((x) => <option key={x}>{x}</option>)}
                      </select>
                    </td>
                    <td>
                      <input aria-label={`Credits for ${r.name}`} inputMode="decimal" disabled={r.out} value={r.credits ?? ""} className="num min-h-[44px] w-16 rounded-input border border-fg/10 bg-surface px-2 text-s16"
                        onChange={(e) => update(r.player_id, { credits: e.target.value === "" ? null : Number(e.target.value), via: r.via === "screenshot" ? "screenshot" : "typed", unsure: false })} />
                    </td>
                    <td>
                      <button className="min-h-[44px] px-2 text-s12 text-slate underline" onClick={() => update(r.player_id, { out: !r.out })}>{r.out ? "Add back" : "Not in Dream11"}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Button className="w-full" disabled={!complete || saving} onClick={save}>{saving ? "Saving…" : "Looks right"}</Button>
          {!complete && rows && rows.length > 0 && <p className="text-center text-s12 text-slate">Every player needs a role and credits (or mark him &ldquo;Not in Dream11&rdquo;).</p>}
        </div>
      )}
      {step === 2 && (
        <div className="space-y-4">
          <p className="text-s16">{active.length} players · {budget} credits budget · {runType === "pre_toss" ? <Chip tone="clay">Pre-toss (XI not announced)</Chip> : <Chip tone="turf">Post-toss (confirmed XI)</Chip>}</p>
          <BuildProgress matchId={match.id} runType={runType} onBack={() => setStep(1)}
            onDone={() => router.push(`/results/${encodeURIComponent(match.id)}?reveal=1`)} />
        </div>
      )}
    </Sheet>
  );
}
