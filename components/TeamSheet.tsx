"use client";
import { motion, useReducedMotion } from "framer-motion";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import type { BenchRow, Player, Role, RunView } from "@/lib/api";
import { ROLES } from "@/lib/gate";
import { Chip, PlayerAvatar, pts, Sheet, surname } from "./ui";

const FACTOR_NAMES: Record<string, string> = {
  form: "Form", venue: "Venue", opponent: "Opponent", current_touch: "Current touch", opportunity: "Opportunity",
  career: "Career", bat_first_or_chase: "Batting first or chasing", pitch_type: "Pitch type",
};
const FALLBACK: Record<number, string> = {
  2: "Little history: estimate from other formats", 3: "Little history: estimate from his career numbers", 4: "No history: debutant average",
};

// The hero: the 11 on a dark-green oval with a floodlight vignette, rows by Dream11 role; one reveal, captain last.
export function TeamSheet({ ids, cap, vc, players, reveal, onTap, mine = new Set<string>(), caption }:
  { ids: string[]; cap: string; vc: string; players: Record<string, Player>; reveal: boolean; onTap: (p: Player) => void; mine?: Set<string>; caption?: string }) {
  const reduce = useReducedMotion();
  const rows = ROLES.map((r) => ({ role: r, list: ids.filter((p) => players[p]?.role === r).sort((a, b) => (players[b].expected ?? 0) - (players[a].expected ?? 0)) }));
  const rowDelay = (ri: number) => ri * 0.12;
  return (
    <div className="rounded-card bg-surface p-3 shadow-card">
      <div className="relative overflow-hidden rounded-[48%/38%] px-2 py-6"
        style={{ background: "radial-gradient(80% 60% at 50% 0%, rgba(255,255,255,0.16), transparent 60%), radial-gradient(120% 90% at 50% 50%, #17603A 0%, #0F4229 55%, #0A2A1B 100%)" }}>
        <div aria-hidden className="absolute left-1/2 top-[18%] h-[64%] w-[16%] -translate-x-1/2 rounded-lg bg-[#D9C9A3]/25" />
        <div aria-hidden className="absolute inset-3 rounded-[48%/38%] border border-white/10" />
        <div className="relative flex flex-col gap-5">
          {rows.map(({ role, list }, ri) => (
            <div key={role} className="flex items-center gap-1">
              <span className="w-9 shrink-0 text-[11px] font-semibold text-white/55">{role}</span>
              <div className="flex flex-1 flex-wrap justify-center gap-x-2 gap-y-3">
                {list.map((pid) => {
                  const p = players[pid];
                  const isC = pid === cap, isV = pid === vc;
                  const d = isC ? 0.5 : rowDelay(ri);
                  return (
                    <motion.button key={pid} onClick={() => onTap(p)} aria-label={`${p.name}${isC ? ", captain" : isV ? ", vice-captain" : ""}, ${pts(p.expected)} expected points`}
                      className="flex w-[66px] flex-col items-center text-white"
                      initial={reveal ? (reduce ? { opacity: 0 } : { opacity: 0, scale: 0.6 }) : false}
                      animate={reveal && isC && !reduce ? { opacity: 1, scale: [0.6, 1.12, 1] } : { opacity: 1, scale: 1 }}
                      transition={{ duration: reduce ? 0.25 : isC ? 0.18 : 0.16, delay: reveal && !reduce ? d : 0 }}>
                      <PlayerAvatar name={p.name} url={p.image_url} colour={p.colour} size={isC || isV ? 58 : 52} badge={isC ? "C" : isV ? "VC" : undefined} />
                      <span className="mt-1.5 max-w-full truncate text-s12 font-medium">{surname(p.name)}</span>
                      <span className="num text-s14 font-bold leading-none">{pts(p.expected)}</span>
                      {mine.has(pid) && <span className="mt-1 rounded-full bg-orange px-1.5 text-[10px] font-bold text-bg">Your pick</span>}
                    </motion.button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
      {caption && <p className="mt-3 text-center text-s12 text-muted">{caption}</p>}
    </div>
  );
}

export function PlayerSheet({ p, run, onClose, isCap, isVc }: { p: Player | null; run: RunView; onClose: () => void; isCap?: boolean; isVc?: boolean }) {
  if (!p) return null;
  const line = (isCap && p.explanations.captain) || (isVc && p.explanations.vice_captain) || p.explanations.player || p.explanations.bench;
  const max = Math.max(1, ...Object.values(p.factors ?? {}).map((v) => Math.abs(v)));
  return (
    <Sheet open onClose={onClose} title="Player">
      <div className="flex items-center gap-4">
        <PlayerAvatar name={p.name} url={p.image_url} colour={p.colour} size={96} badge={isCap ? "C" : isVc ? "VC" : undefined} />
        <div className="min-w-0">
          <h3 className="num text-[22px] font-bold leading-tight">{p.name}</h3>
          <div className="mt-2 flex flex-wrap gap-1.5"><Chip tone="glass">{p.team_code}</Chip><Chip tone="glass">{p.role}</Chip><Chip tone="muted"><span className="num font-bold text-ink">{p.credits}</span> cr</Chip></div>
        </div>
      </div>
      <div className="mt-6">
        <div className="num text-s34 font-extrabold leading-none">{pts(p.expected)} <span className="text-s14 font-semibold text-muted">expected pts</span></div>
        <p className="mt-1 text-s14 text-muted">Base {pts(p.base)}{p.change_pct ? ` → Gemini ${p.change_pct > 0 ? "+" : ""}${pts(p.change_pct, 0)}% → ${pts(p.expected)}` : ""}</p>
      </div>
      {p.fallback_step && p.fallback_step > 1 && <Chip tone="amber" className="mt-3">{FALLBACK[p.fallback_step] ?? p.fallback_note}</Chip>}
      {line && (
        <section className="mt-5">
          <h4 className="text-s14 font-semibold text-muted">{isCap ? "Why he's captain" : isVc ? "Why he's vice-captain" : "Why he's picked"}</h4>
          <p className="mt-1.5 whitespace-pre-line leading-relaxed">{line.text}</p>
          {line.generic && <Chip tone="amber" className="mt-2">Generic reason: check it yourself</Chip>}
        </section>
      )}
      {p.adjustment && (
        <section className="mt-5 rounded-tile bg-surface p-4">
          <h4 className="font-semibold">Gemini&apos;s adjustment <span className={p.adjustment.applied_pct > 0 ? "text-green" : "text-red"}>{p.adjustment.applied_pct > 0 ? "+" : ""}{pts(p.adjustment.applied_pct, 0)}%</span></h4>
          <p className="mt-1 text-s14 text-muted">{p.adjustment.reason}</p>
          {p.adjustment.clipped && <p className="mt-1 text-s12 text-muted">Gemini asked for {pts(p.adjustment.requested_pct, 0)}%; limited to ±20%.</p>}
          {p.adjustment.source_url && <a href={p.adjustment.source_url} target="_blank" rel="noreferrer noopener" className="mt-2 inline-flex min-h-[44px] items-center gap-1 font-semibold text-orange">Read source <ExternalLink size={14} /></a>}
        </section>
      )}
      {p.factors && Object.keys(p.factors).length > 0 && (
        <section className="mt-5">
          <h4 className="text-s14 font-semibold text-muted">What the numbers say</h4>
          <ul className="mt-3 space-y-3">
            {run.factors.map((f) => {
              const v = p.factors![f] ?? 0, low = (p.trust?.[f] ?? 1) < 0.5;
              return (
                <li key={f} className="text-s14">
                  <div className="mb-1 flex justify-between"><span>{FACTOR_NAMES[f] ?? f}{low && <span className="text-muted"> · few matches</span>}</span><span className="num font-bold">{pts(v)}</span></div>
                  <div className="h-1.5 rounded-full bg-surface2"><div className={`h-1.5 rounded-full ${low ? "bg-muted/60" : "bg-ink"}`} style={{ width: `${(Math.abs(v) / max) * 100}%` }} /></div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </Sheet>
  );
}

export function BenchRowButton({ bench, players, onOpen }: { bench: BenchRow[]; players: Record<string, Player>; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="flex min-h-[64px] w-full items-center gap-3 rounded-tile bg-surface px-4 py-3 text-left shadow-card">
      <span className="flex -space-x-3">{bench.map((b) => players[b.player_id] && (
        <span key={b.player_id} className="rounded-full border-2 border-surface"><PlayerAvatar name={players[b.player_id].name} url={players[b.player_id].image_url} colour={players[b.player_id].colour} size={32} /></span>))}</span>
      <span className="flex-1 font-semibold">Bench</span><span className="text-s14 text-muted">{bench.length} left out ›</span>
    </button>
  );
}

export function BenchSheet({ open, onClose, bench, players, onTap }: { open: boolean; onClose: () => void; bench: BenchRow[]; players: Record<string, Player>; onTap: (p: Player) => void }) {
  return (
    <Sheet open={open} onClose={onClose} title={`Bench: ${bench.length} players`}>
      <ul className="space-y-2">
        {bench.map((b) => {
          const p = players[b.player_id];
          return p && (
            <li key={b.player_id}>
              <button className="flex w-full items-center gap-3 rounded-tile bg-surface p-3 text-left" onClick={() => onTap(p)}>
                <PlayerAvatar name={p.name} url={p.image_url} colour={p.colour} size={44} />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{p.name} <span className="text-s12 font-normal text-muted">{p.team_code} · {p.role}</span></div>
                  <div className="text-s14 text-muted">{p.explanations.bench?.text ?? b.reason_detail}</div>
                </div>
                <span className="num text-s20 font-bold">{pts(p.expected)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </Sheet>
  );
}

export function CopySheet({ open, onClose, ids, cap, vc, players }: { open: boolean; onClose: () => void; ids: string[]; cap: string; vc: string; players: Record<string, Player> }) {
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const toggle = (id: string) => setTicked((t) => { const n = new Set(t); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  return (
    <Sheet open={open} onClose={onClose} title="Copy to Dream11">
      <p className="text-s14 text-muted">The app can&apos;t submit to Dream11. Tick each player as you add him.</p>
      <div className="my-5 space-y-2">
        <p className="num flex items-center gap-3 text-s26 font-bold"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-gold text-s14 text-bg">C</span>{players[cap]?.name}</p>
        <p className="num flex items-center gap-3 text-s26 font-bold"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-silver text-s12 text-bg">VC</span>{players[vc]?.name}</p>
      </div>
      {(ROLES as Role[]).map((r) => {
        const list = ids.filter((p) => players[p]?.role === r);
        return list.length > 0 && (
          <fieldset key={r} className="mb-4">
            <legend className="mb-1 text-s12 font-semibold text-muted">{r}</legend>
            {list.map((p) => (
              <label key={p} className="flex min-h-[48px] items-center gap-3 border-b hairline">
                <input type="checkbox" className="h-5 w-5 accent-[#2BB673]" checked={ticked.has(p)} onChange={() => toggle(p)} />
                <span className={ticked.has(p) ? "text-muted line-through" : ""}>{players[p].name}</span>
                <span className="num ml-auto font-bold text-muted">{players[p].credits} cr</span>
              </label>
            ))}
          </fieldset>
        );
      })}
      <p className="text-s14 text-muted"><span className="num font-bold text-ink">{ticked.size}</span> of {ids.length} added</p>
    </Sheet>
  );
}
