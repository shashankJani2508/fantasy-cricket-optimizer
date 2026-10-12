"use client";
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, Match } from "@/lib/api";
import { Button, Chip, countdown, ErrorNote, haptic, localTime, Skeleton, useAuth, useSnack } from "@/components/ui";
import { SetupSheet } from "@/components/SetupSheet";

type Card = Match & { rain_chance: number | null; choice: "play" | "skip" | null };
type Deck = { matches: Card[]; next_match: Match | null; stale_since: string | null };

export default function Upcoming() {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [setup, setSetup] = useState<Card | null>(null);
  const [showSkipped, setShowSkipped] = useState(false);
  const { ask } = useAuth();
  const snack = useSnack();
  const load = useCallback(() => api<Deck>("/matches/upcoming").then(setDeck).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const setChoice = (id: string, choice: Card["choice"]) =>
    setDeck((d) => d && { ...d, matches: d.matches.map((m) => (m.id === id ? { ...m, choice } : m)) });

  const choose = async (m: Card, choice: "play" | "skip") => {
    if (!(await ask())) return false;
    try {
      await api(`/matches/${m.id}/choice`, { method: "POST", body: { choice } });
    } catch (e: any) { snack({ text: e.message }); return false; }
    haptic();
    setChoice(m.id, choice);
    if (choice === "play") setSetup(m);
    else snack({ text: `Skipped ${code(m.team_a)} v ${code(m.team_b)}`, action: { label: "Undo", run: () => undo(m) } });
    return true;
  };
  const undo = async (m: Card) => {
    try { await api(`/matches/${m.id}/choice`, { method: "DELETE" }); setChoice(m.id, null); } catch (e: any) { snack({ text: e.message }); }
  };

  const open = deck?.matches.filter((m) => !m.choice) ?? [];
  const playing = deck?.matches.filter((m) => m.choice === "play") ?? [];
  const skipped = deck?.matches.filter((m) => m.choice === "skip") ?? [];

  return (
    <section aria-labelledby="h-up">
      <header className="mb-4 flex items-baseline justify-between gap-2">
        <h1 id="h-up" className="num text-s40">This week</h1>
        <div className="flex items-center gap-2">
          {deck?.stale_since && <Chip tone="clay">Showing saved fixtures from {localTime(deck.stale_since)}</Chip>}
          {deck && <span className="num text-s20 text-slate">{deck.matches.length} {deck.matches.length === 1 ? "match" : "matches"}</span>}
        </div>
      </header>
      {err && <ErrorNote>Couldn&apos;t load fixtures: {err}</ErrorNote>}
      {!deck && !err && <CardSkeleton />}
      {deck && deck.matches.length === 0 && (
        <div className="rounded-card bg-surface p-6 text-center">
          <p className="text-s20">No matches in the next 7 days.</p>
          {deck.next_match && <p className="mt-2 text-slate">Next match: {localTime(deck.next_match.start_time)}, {code(deck.next_match.team_a)} vs {code(deck.next_match.team_b)}.</p>}
          <Link href="/results" className="mt-4 inline-block font-semibold text-turf underline">See recent results</Link>
        </div>
      )}
      {deck && deck.matches.length > 0 && (
        <div className="mx-auto max-w-md">
          {open.length > 0 ? <SwipeDeck cards={open} onChoose={choose} /> : (
            <div className="rounded-card bg-surface p-6 text-center text-slate">You&apos;ve been through every match this week.</div>
          )}
          {playing.length > 0 && (
            <div className="mt-6 flex flex-wrap items-center gap-2">
              <span className="text-s14 text-slate">Playing:</span>
              {playing.map((m) => <Link key={m.id} href={`/results/${encodeURIComponent(m.id)}`}><Chip tone="turf">{code(m.team_a)} v {code(m.team_b)}</Chip></Link>)}
            </div>
          )}
          {skipped.length > 0 && (
            <div className="mt-4">
              <button className="min-h-[44px] text-s14 text-slate underline" onClick={() => setShowSkipped((v) => !v)} aria-expanded={showSkipped}>Skipped ({skipped.length})</button>
              {showSkipped && skipped.map((m) => (
                <div key={m.id} className="flex items-center justify-between border-b border-fg/10 py-2 text-s14">
                  <span>{code(m.team_a)} v {code(m.team_b)} · {localTime(m.start_time)}</span>
                  <button className="min-h-[44px] px-2 font-semibold text-turf" onClick={() => undo(m)}>Restore</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {setup && <SetupSheet match={setup} onClose={() => setSetup(null)} />}
    </section>
  );
}

const code = (t: Match["team_a"]) => t?.code ?? "TBC";

function SwipeDeck({ cards, onChoose }: { cards: Card[]; onChoose: (m: Card, c: "play" | "skip") => Promise<boolean> }) {
  const top = cards[0];
  const x = useMotionValue(0);
  const reduce = useReducedMotion();
  const rotate = useTransform(x, [-200, 200], [-12, 12]);
  const play = useTransform(x, [20, 120], [0, 1]);
  const skip = useTransform(x, [-120, -20], [1, 0]);
  const commit = useCallback(async (c: "play" | "skip") => {
    const to = c === "play" ? 600 : -600;
    if (reduce) x.set(to); else await animate(x, to, { duration: 0.2 });
    const ok = await onChoose(top, c);
    if (!ok) { x.set(0); return; }
    x.set(0);
  }, [onChoose, top, x, reduce]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea,[role=dialog]")) return;
      if (e.key === "ArrowRight") commit("play");
      if (e.key === "ArrowLeft") commit("skip");
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [commit]);
  return (
    <div>
      <div className="relative h-[330px]">
        {cards[1] && <div className="absolute inset-x-3 top-3 scale-[0.97]" aria-hidden><FixtureCard m={cards[1]} /></div>}
        <motion.div key={top.id} className="absolute inset-0 cursor-grab touch-pan-y active:cursor-grabbing" style={{ x, rotate }}
          drag="x" dragConstraints={{ left: 0, right: 0 }} dragElastic={0.9}
          onDragEnd={(_, i) => { if (i.offset.x > 120) commit("play"); else if (i.offset.x < -120) commit("skip"); }}>
          <FixtureCard m={top} />
          <motion.span style={{ opacity: play }} className="num pointer-events-none absolute left-6 top-6 -rotate-12 rounded-input border-4 border-turf px-3 text-s40 text-turf">Play</motion.span>
          <motion.span style={{ opacity: skip }} className="num pointer-events-none absolute right-6 top-6 rotate-12 rounded-input border-4 border-slate px-3 text-s40 text-slate">Skip</motion.span>
        </motion.div>
      </div>
      <div className="mt-4 flex justify-center gap-4">
        <Button kind="quiet" onClick={() => commit("skip")} aria-label={`Skip ${top.series ?? "this match"}`}>✕ Skip</Button>
        <Button onClick={() => commit("play")} aria-label={`Play ${top.series ?? "this match"}`}>✓ Play this match</Button>
      </div>
      <p className="mt-2 text-center text-s12 text-slate">Swipe, tap, or use the ← → keys.</p>
    </div>
  );
}

function FixtureCard({ m }: { m: Card }) {
  const stripe = (c: string | null | undefined) => ({ background: c ?? "rgb(var(--slate))" });
  return (
    <article className="relative h-[300px] select-none overflow-hidden rounded-card bg-surface p-6 shadow-md" aria-label={`${m.team_a?.name} vs ${m.team_b?.name}`}>
      <span className="absolute inset-y-0 left-0 w-2" style={stripe(m.team_a?.colour)} aria-hidden />
      <span className="absolute inset-y-0 right-0 w-2" style={stripe(m.team_b?.colour)} aria-hidden />
      <div className="num flex items-baseline gap-3 text-s40 leading-none">
        <span>{code(m.team_a)}</span><span className="text-s20 text-slate">vs</span><span>{code(m.team_b)}</span>
      </div>
      <p className="mt-3 text-s14 text-slate">{m.format}{m.series ? ` · ${m.series}` : ""}</p>
      <p className="mt-1 text-s16">{[m.venue, m.city].filter(Boolean).join(", ") || "Venue not announced"}</p>
      <p className="mt-3 text-s16">{localTime(m.start_time)}</p>
      <p className="num text-s20">{countdown(m.start_time)}</p>
      <p className="mt-3 text-s14 text-slate">
        {m.rain_chance == null ? "Rain forecast not available yet" : `☁ ${m.rain_chance}% rain`} · {m.xi_announced ? "XI announced" : "XI not yet"}
      </p>
    </article>
  );
}

function CardSkeleton() {
  return (
    <div className="mx-auto h-[300px] max-w-md rounded-card bg-surface p-6" aria-label="Loading fixtures">
      <div className="flex gap-3"><Skeleton className="h-10 w-20" /><Skeleton className="h-10 w-20" /></div>
      <Skeleton className="mt-4 h-4 w-2/3" /><Skeleton className="mt-3 h-4 w-1/2" /><Skeleton className="mt-6 h-6 w-1/3" />
    </div>
  );
}
