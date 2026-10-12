"use client";
import { motion, useReducedMotion } from "framer-motion";
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

// The hero: the 11 on an oval ground in rows by Dream11 role, captain and VC badged; one reveal, captain last.
export function TeamSheet({ ids, cap, vc, players, reveal, onTap, mine = new Set<string>() }:
  { ids: string[]; cap: string; vc: string; players: Record<string, Player>; reveal: boolean; onTap: (p: Player) => void; mine?: Set<string> }) {
  const reduce = useReducedMotion();
  let order = 0;
  const rows = ROLES.map((r) => ({ role: r, list: ids.filter((p) => players[p]?.role === r).sort((a, b) => (players[b].expected ?? 0) - (players[a].expected ?? 0)) }));
  const delay = (pid: string) => (pid === cap ? 0.55 : Math.min(0.5, 0.06 * order++));
  return (
    <div className="relative mx-auto aspect-[4/5] w-full max-w-[520px] overflow-hidden rounded-[50%/42%] bg-turf p-4 sm:aspect-[5/5]">
      <div aria-hidden className="absolute left-1/2 top-[22%] h-[56%] w-[13%] -translate-x-1/2 rounded-md bg-clay/80" />
      <div className="relative flex h-full flex-col justify-around py-4">
        {rows.map(({ role, list }) => (
          <div key={role} className="flex items-center justify-center gap-2 sm:gap-4">
            <span className="w-10 shrink-0 text-right text-s12 font-semibold text-white/80">{role}</span>
            <div className="flex flex-wrap justify-center gap-2 sm:gap-4">
              {list.map((pid) => {
                const p = players[pid];
                const big = pid === cap || pid === vc;
                return (
                  <motion.button key={pid} onClick={() => onTap(p)} aria-label={`${p.name}${pid === cap ? ", captain" : pid === vc ? ", vice-captain" : ""}, ${pts(p.expected)} expected points`}
                    className="flex w-[64px] flex-col items-center text-white sm:w-[76px]"
                    initial={reveal ? (reduce ? { opacity: 0 } : { opacity: 0, y: -18, scale: 0.85 }) : false}
                    animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: reduce ? 0.3 : 0.14, delay: reveal && !reduce ? delay(pid) : 0 }}>
                    <PlayerAvatar name={p.name} url={p.image_url} colour={p.colour} size={big ? 54 : 46} badge={pid === cap ? "C" : pid === vc ? "VC" : undefined} />
                    <span className="mt-1 max-w-full truncate text-s12 font-semibold">{surname(p.name)}</span>
                    <span className="num text-s16 leading-none">{pts(p.expected)}</span>
                    {mine.has(pid) && <span className="mt-0.5 rounded-full bg-floodlight px-1.5 text-[10px] font-semibold text-pavilion">Your pick</span>}
                  </motion.button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PlayerSheet({ p, run, onClose, isCap, isVc }: { p: Player | null; run: RunView; onClose: () => void; isCap?: boolean; isVc?: boolean }) {
  if (!p) return null;
  const line = (isCap && p.explanations.captain) || (isVc && p.explanations.vice_captain) || p.explanations.player || p.explanations.bench;
  const max = Math.max(1, ...Object.values(p.factors ?? {}).map((v) => Math.abs(v)));
  return (
    <Sheet open onClose={onClose} title={p.name}>
      <div className="flex items-center gap-4">
        <PlayerAvatar name={p.name} url={p.image_url} colour={p.colour} size={72} badge={isCap ? "C" : isVc ? "VC" : undefined} />
        <div className="text-s14 text-slate">{p.team} · {p.role} · <span className="num text-s16 text-fg">{p.credits}</span> credits</div>
      </div>
      <div className="mt-4">
        <div className="num text-s40 leading-none">{pts(p.expected)}</div>
        <p className="text-s14 text-slate">
          Base {pts(p.base)}{p.change_pct ? ` → Gemini ${p.change_pct > 0 ? "+" : ""}${pts(p.change_pct, 0)}% → ${pts(p.expected)}` : ""} expected points
        </p>
      </div>
      {p.fallback_step && p.fallback_step > 1 && <Chip tone="clay" className="mt-3">{FALLBACK[p.fallback_step] ?? p.fallback_note}</Chip>}
      {line && (
        <section className="mt-4">
          <h3 className="font-semibold">{isCap ? "Why he's captain" : isVc ? "Why he's vice-captain" : "Why he's picked"}</h3>
          <p className="mt-1 whitespace-pre-line">{line.text}</p>
          {line.generic && <Chip tone="floodlight" className="mt-2">Generic reason: check it yourself</Chip>}
        </section>
      )}
      {p.adjustment && (
        <section className="mt-4 rounded-sheet bg-surface p-3">
          <h3 className="font-semibold">Gemini&apos;s adjustment: {p.adjustment.applied_pct > 0 ? "+" : ""}{pts(p.adjustment.applied_pct, 0)}%</h3>
          <p className="mt-1 text-s14">{p.adjustment.reason}</p>
          {p.adjustment.clipped && <p className="mt-1 text-s12 text-slate">Gemini asked for {pts(p.adjustment.requested_pct, 0)}%; limited to ±20%.</p>}
          {p.adjustment.source_url && <a href={p.adjustment.source_url} target="_blank" rel="noreferrer noopener" className="mt-2 inline-block min-h-[44px] font-semibold text-turf underline">Read source</a>}
        </section>
      )}
      {p.factors && Object.keys(p.factors).length > 0 && (
        <section className="mt-4">
          <h3 className="font-semibold">What the numbers say</h3>
          <ul className="mt-2 space-y-2">
            {run.factors.map((f) => {
              const v = p.factors![f] ?? 0, low = (p.trust?.[f] ?? 1) < 0.5;
              return (
                <li key={f} className="text-s14">
                  <div className="flex justify-between"><span>{FACTOR_NAMES[f] ?? f}{low && <span className="text-slate"> · few matches</span>}</span><span className="num text-s16">{pts(v)}</span></div>
                  <div className="h-2 rounded-full bg-slate/15"><div className={`h-2 rounded-full ${low ? "bg-clay" : "bg-turf"}`} style={{ width: `${(Math.abs(v) / max) * 100}%` }} /></div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </Sheet>
  );
}

export function BenchSheet({ open, onClose, bench, players, onTap }: { open: boolean; onClose: () => void; bench: BenchRow[]; players: Record<string, Player>; onTap: (p: Player) => void }) {
  return (
    <Sheet open={open} onClose={onClose} title={`Bench: ${bench.length} players`}>
      <ul className="divide-y divide-slate/20">
        {bench.map((b) => {
          const p = players[b.player_id];
          return p && (
            <li key={b.player_id}>
              <button className="flex w-full items-center gap-3 py-3 text-left" onClick={() => onTap(p)}>
                <PlayerAvatar name={p.name} url={p.image_url} colour={p.colour} size={44} />
                <div className="flex-1">
                  <div className="font-semibold">{p.name} <span className="text-s12 text-slate">{p.team_code} · {p.role}</span></div>
                  <div className="text-s14">{p.explanations.bench?.text ?? b.reason_detail}</div>
                </div>
                <span className="num text-s20">{pts(p.expected)}</span>
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
      <p className="text-s14 text-slate">The app can&apos;t submit to Dream11. Tick each player as you add him.</p>
      <div className="my-4 space-y-1">
        <p className="num text-s28"><span className="text-ball">C</span> {players[cap]?.name}</p>
        <p className="num text-s28"><span className="text-floodlight">VC</span> {players[vc]?.name}</p>
      </div>
      {(ROLES as Role[]).map((r) => {
        const list = ids.filter((p) => players[p]?.role === r);
        return list.length > 0 && (
          <fieldset key={r} className="mb-3">
            <legend className="text-s12 font-semibold text-slate">{r}</legend>
            {list.map((p) => (
              <label key={p} className="flex min-h-[44px] items-center gap-3">
                <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--turf))]" checked={ticked.has(p)} onChange={() => toggle(p)} />
                <span className={ticked.has(p) ? "text-slate line-through" : ""}>{players[p].name}</span>
                <span className="num ml-auto text-s16 text-slate">{players[p].credits} cr</span>
              </label>
            ))}
          </fieldset>
        );
      })}
      <p className="text-s14">{ticked.size} of {ids.length} added</p>
    </Sheet>
  );
}
