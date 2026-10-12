"use client";
import { Camera } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Match, Role } from "@/lib/api";
import { ROLES } from "@/lib/gate";
import { Button, Chip, ErrorNote, haptic, PlayerAvatar, Sheet, Skeleton } from "./ui";
import { BuildProgress } from "./BuildProgress";
import { screenshotForm } from "@/lib/images";

type Row = { player_id: string; name: string; team: string; team_code: string; colour: string | null; image_url: string | null;
  role: Role | null; credits: number | null; via: "screenshot" | "typed" | "prefill"; unsure: boolean; from_last_match: boolean; out: boolean };
type Unmatched = { name_on_screen: string; link_name: string; team_code: string | null; role: Role | null; credits: number | null; unsure: boolean; suggestions: string[] };

export function SetupSheet({ match, onClose }: { match: Match; onClose: (saved?: boolean) => void }) {
  const [step, setStep] = useState<1 | 2>(1);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [budget, setBudget] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [typing, setTyping] = useState(false);
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
    if (!files?.length || !rows) return;
    setReading(true); setErr(null);
    try {
      const r = await api(`/matches/${encodeURIComponent(match.id)}/screenshots/player-list`, { method: "POST", form: await screenshotForm(files) });
      // Everything after the upload is automatic: players not on the screenshots are left out, missing credits come
      // from the last match, names we can't place are skipped with a note (never a question).
      const read = new Map<string, any>(r.rows.filter((x: any) => x.player_id).map((x: any) => [x.player_id, x]));
      const next: Row[] = rows.map((row) => {
        const x = read.get(row.player_id);
        if (!x) return { ...row, out: true, unsure: false };
        const credits = x.credits ?? (row.from_last_match ? row.credits : null);
        const role = x.role ?? row.role;
        return { ...row, role, credits, via: "screenshot", unsure: false, from_last_match: x.credits == null && credits != null, out: credits == null || !role };
      });
      for (const x of read.values()) if (!rows.some((row) => row.player_id === x.player_id) && x.player && x.credits && x.role)
        next.push({ ...x.player, role: x.role, credits: x.credits, via: "screenshot", unsure: false, from_last_match: false, out: false });
      const skipped = r.rows.filter((x: any) => !x.player_id).map((x: any) => `${x.name_on_screen} (${x.skip_reason})`);
      const noCredits = next.filter((x) => x.out && read.has(x.player_id)).map((x) => `${x.name} (no credits on screenshot)`);
      setRows(next); setUnmatched([]); setTyping(true);
      setNote([...skipped, ...noCredits].length ? `Left out automatically: ${[...skipped, ...noCredits].join(", ")}.` : null);
    } catch (e: any) { setErr(e.message); }
    setReading(false);
  };
  const confirmLink = async (u: Unmatched, pid: string) => {
    try {
      await api("/players/link", { method: "POST", body: { player_id: pid, name_on_screen: u.link_name ?? u.name_on_screen } });
      update(pid, { role: u.role, credits: u.credits, via: "screenshot", unsure: u.unsure, out: false });
      setUnmatched((l) => l.filter((x) => x !== u));
    } catch (e: any) { setErr(e.message); }
  };

  const active = rows?.filter((r) => !r.out) ?? [];
  const complete = active.length >= 11 && active.every((r) => r.role && r.credits != null && r.credits > 0);
  const saveRows = async (list: Row[]) => {
    setSaving(true); setErr(null);
    try {
      await api(`/matches/${encodeURIComponent(match.id)}/credits`, { method: "PUT", body: { rows: list.map((r) => ({ player_id: r.player_id, credits: r.credits, role: r.role, entered_via: r.via })) } });
      haptic(); setStep(2);
    } catch (e: any) { setErr(e.message); }
    setSaving(false);
  };
  const save = () => saveRows(active);
  const runType = match.xi_announced ? "post_toss" : "pre_toss";

  return (
    <Sheet open onClose={() => onClose(step === 2)} title={step === 1 ? "Add credits and roles from Dream11" : "Build my team"}>
      <div className="mb-4 flex items-center gap-2" aria-label={`Step ${step} of 2`}>
        {[1, 2].map((s) => <span key={s} className={`h-1.5 rounded-full ${s === step ? "w-6 bg-red" : "w-1.5 bg-white/25"}`} />)}
        <span className="ml-1 text-s12 text-muted">{step} of 2 · {match.team_a?.code} vs {match.team_b?.code}</span>
      </div>
      {err && <div className="mb-3"><ErrorNote>{err}</ErrorNote></div>}
      {step === 1 && (
        <div className="space-y-4">
          <label className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-white/15 bg-surface px-4 py-7 text-center transition hover:border-white/30 ${reading ? "opacity-60" : ""}`}>
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface2"><Camera size={22} strokeWidth={1.75} /></span>
            <span className="font-semibold">{reading ? "Reading your screenshots…" : "Upload Dream11 screenshot"}</span>
            <span className="text-s12 text-muted">Add all your Dream11 screenshots at once (up to 15). The Preview screens show credits.</span>
            <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="sr-only" disabled={reading} onChange={(e) => upload(e.target.files)} />
          </label>
          {!typing && <button className="mx-auto block min-h-[44px] text-s14 font-semibold text-muted underline-offset-4 hover:underline" onClick={() => setTyping(true)}>Type instead</button>}
          {note && <p className="rounded-tile bg-surface px-4 py-3 text-s12 text-muted">{note}</p>}
          {unmatched.map((u) => (
            <div key={u.link_name ?? u.name_on_screen} className="rounded-tile border-l-4 border-amber bg-surface p-4 text-s14">
              <p>We couldn&apos;t match &lsquo;{u.name_on_screen}&rsquo;{u.role ? ` (${u.role})` : ""}. {u.suggestions.length ? "Is this one of these?" : "Who is it?"}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {u.suggestions.map((pid) => {
                  const r = rows?.find((x) => x.player_id === pid);
                  return r && <Button key={pid} kind="quiet" className="!min-h-[40px] !px-4 text-s14" onClick={() => confirmLink(u, pid)}>Yes, {r.name}</Button>;
                })}
                <select aria-label={`Choose the player for ${u.name_on_screen}`} className="min-h-[40px] rounded-full bg-surface2 px-3 text-s14"
                  defaultValue="" onChange={(e) => e.target.value && confirmLink(u, e.target.value)}>
                  <option value="">Choose another…</option>
                  {rows?.map((r) => <option key={r.player_id} value={r.player_id}>{r.name} ({r.team_code})</option>)}
                </select>
              </div>
            </div>
          ))}
          {(typing || active.some((r) => r.credits != null)) && (!rows ? <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div> : rows.length === 0 ? (
            <ErrorNote>No squad is available for this match yet. Try again closer to the start.</ErrorNote>
          ) : (
            <ul className="space-y-2">
              {rows.map((r) => (
                <li key={r.player_id} className={`flex items-center gap-3 rounded-tile bg-surface p-2.5 pr-3 ${r.unsure ? "border-l-4 border-amber" : ""} ${r.out ? "opacity-40" : ""}`}>
                  <PlayerAvatar name={r.name} url={r.image_url} colour={r.colour} size={36} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-s14 font-semibold">{r.name}</div>
                    <div className="flex items-center gap-1.5 text-s12 text-muted">
                      <span>{r.team_code}</span>
                      {r.unsure && <span className="text-amber">· Check this</span>}
                      {r.from_last_match && <span>· from last match</span>}
                      <button className="text-muted underline-offset-2 hover:underline" onClick={() => update(r.player_id, { out: !r.out })}>· {r.out ? "Add back" : "Not in list"}</button>
                    </div>
                  </div>
                  <select aria-label={`Role for ${r.name}`} value={r.role ?? ""} disabled={r.out}
                    onChange={(e) => update(r.player_id, { role: (e.target.value || null) as Role, via: r.via === "screenshot" ? "screenshot" : "typed", unsure: false })}
                    className="min-h-[40px] rounded-full bg-surface2 px-2 text-s12 font-semibold">
                    <option value="">Role</option>{ROLES.map((x) => <option key={x}>{x}</option>)}
                  </select>
                  <input aria-label={`Credits for ${r.name}`} inputMode="decimal" disabled={r.out} value={r.credits ?? ""} placeholder="Cr"
                    onChange={(e) => update(r.player_id, { credits: e.target.value === "" ? null : Number(e.target.value), via: r.via === "screenshot" ? "screenshot" : "typed", unsure: false })}
                    className="num min-h-[40px] w-14 rounded-input bg-surface2 px-2 text-right text-s16 font-bold placeholder:text-muted/60" />
                </li>
              ))}
            </ul>
          ))}
          <div className="sticky bottom-0 -mx-5 bg-gradient-to-t from-[#13151D] via-[#13151D] to-transparent px-5 pb-1 pt-4">
            {!complete && rows && rows.length > 0 && <p className="mb-2 text-center text-s12 text-muted">Every player needs a role and credits, or mark him &ldquo;Not in list&rdquo;.</p>}
            <Button className="w-full" disabled={!complete || saving} onClick={save}>{saving ? "Saving…" : "Looks right"}</Button>
          </div>
        </div>
      )}
      {step === 2 && (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <Chip tone="glass">{active.length} players</Chip><Chip tone="glass">{budget} credits budget</Chip>
            {runType === "pre_toss" ? <Chip tone="amber">Pre-toss (XI not announced)</Chip> : <Chip tone="green">Post-toss (confirmed XI)</Chip>}
          </div>
          <BuildProgress matchId={match.id} runType={runType} onBack={() => setStep(1)}
            onDone={() => router.push(`/results/${encodeURIComponent(match.id)}?reveal=1`)} />
        </div>
      )}
    </Sheet>
  );
}
