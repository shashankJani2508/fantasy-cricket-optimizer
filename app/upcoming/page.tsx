"use client";
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { Check, CloudRain, MapPin, Users, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Match } from "@/lib/api";
import { matchArt, ring } from "@/lib/teams";
import { Chip, countdown, ErrorNote, haptic, localTime, Skeleton, TeamBadge, useAuth, useSnack } from "@/components/ui";
import { SetupSheet } from "@/components/SetupSheet";

type Card = Match & { rain_chance: number | null; choice: "play" | "skip" | null };
type Deck = { matches: Card[]; next_match: Match | null; stale_since: string | null };
const code = (t: Match["team_a"]) => t?.code ?? "TBC";

export default function Upcoming() {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [setup, setSetup] = useState<Card | null>(null);
  const [topId, setTopId] = useState<string | null>(null);
  const [showSkipped, setShowSkipped] = useState(false);
  const { ask } = useAuth();
  const snack = useSnack();
  const load = useCallback(() => api<Deck>("/matches/upcoming").then(setDeck).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const setChoice = (id: string, choice: Card["choice"]) =>
    setDeck((d) => d && { ...d, matches: d.matches.map((m) => (m.id === id ? { ...m, choice } : m)) });
  const undo = async (m: Card) => {
    try { await api(`/matches/${encodeURIComponent(m.id)}/choice`, { method: "DELETE" }); setChoice(m.id, null); } catch (e: any) { snack({ text: e.message }); }
  };
  const choose = async (m: Card, choice: "play" | "skip") => {
    if (!(await ask())) return false;
    try { await api(`/matches/${encodeURIComponent(m.id)}/choice`, { method: "POST", body: { choice } }); }
    catch (e: any) { snack({ text: e.message }); return false; }
    haptic();
    setChoice(m.id, choice);
    if (choice === "play") setSetup(m);
    else snack({ text: `Skipped ${code(m.team_a)} v ${code(m.team_b)}`, action: { label: "Undo", run: () => undo(m) } });
    return true;
  };

  const open = useMemo(() => {
    const l = deck?.matches.filter((m) => !m.choice) ?? [];
    const i = l.findIndex((m) => m.id === topId);
    return i > 0 ? [l[i], ...l.slice(0, i), ...l.slice(i + 1)] : l;
  }, [deck, topId]);
  const skipped = deck?.matches.filter((m) => m.choice === "skip") ?? [];
  const n = deck?.matches.length ?? 0;

  return (
    <section aria-labelledby="h-up">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <h1 id="h-up" className="num text-s26 font-bold">This week</h1>
        <div className="flex flex-wrap items-center gap-2">
          {deck?.stale_since && <Chip tone="amber">Saved fixtures from {localTime(deck.stale_since)}</Chip>}
          {deck && <Chip tone="glass">{n} {n === 1 ? "match" : "matches"}</Chip>}
        </div>
      </header>
      {err && <ErrorNote>Couldn&apos;t load fixtures: {err}. Pull to refresh or try again in a minute.</ErrorNote>}
      {!deck && !err && <DeckSkeleton />}
      {deck && n === 0 && (
        <div className="noise relative overflow-hidden rounded-card p-6 shadow-card" style={matchArt(null, null)}>
          <p className="num relative text-s26 font-bold">No matches in the next 7 days</p>
          {deck.next_match && <p className="relative mt-2 text-muted">Next match: {localTime(deck.next_match.start_time)}, {code(deck.next_match.team_a)} vs {code(deck.next_match.team_b)}.</p>}
          <Link href="/results" className="relative mt-5 inline-flex min-h-[44px] items-center rounded-full glass px-5 font-semibold">See recent results ›</Link>
        </div>
      )}
      {deck && n > 0 && (
        <>
          <div className="no-scrollbar -mx-5 mb-5 flex gap-4 overflow-x-auto px-5" aria-label="Matches this week">
            {deck.matches.map((m) => (
              <button key={m.id} onClick={() => (m.choice === "play" ? location.assign(`/results/${encodeURIComponent(m.id)}`) : setTopId(m.id))}
                className="flex w-[72px] shrink-0 flex-col items-center gap-1.5" aria-label={`${code(m.team_a)} v ${code(m.team_b)}${m.choice === "play" ? ", playing" : ""}`}>
                <span className="relative rounded-full p-[3px]" style={{ background: ring(m.team_a?.colour, m.team_b?.colour) }}>
                  <span className="relative block h-[60px] w-[60px] overflow-hidden rounded-full border-2 border-bg">
                    <span className="absolute inset-0"><TeamBadge name={m.team_a?.name} code={m.team_a?.code} colour={m.team_a?.colour} size={56} /></span>
                    <span className="absolute inset-0" style={{ clipPath: "polygon(100% 0, 100% 100%, 0 100%)" }}><TeamBadge name={m.team_b?.name} code={m.team_b?.code} colour={m.team_b?.colour} size={56} /></span>
                  </span>
                  {m.choice === "play" && <span className="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-red"><Check size={12} strokeWidth={3} /></span>}
                </span>
                <span className="text-s12 font-semibold text-muted">{code(m.team_a)} v {code(m.team_b)}</span>
              </button>
            ))}
          </div>
          {open.length > 0 ? <SwipeDeck cards={open} onChoose={choose} /> : (
            <div className="rounded-card bg-surface p-6 text-center text-muted shadow-card">You&apos;ve been through every match this week. Your teams are in Results.</div>
          )}
          {skipped.length > 0 && (
            <div className="mt-6">
              <button className="min-h-[44px] text-s14 font-semibold text-muted" onClick={() => setShowSkipped((v) => !v)} aria-expanded={showSkipped}>Skipped ({skipped.length}) ›</button>
              {showSkipped && skipped.map((m) => (
                <div key={m.id} className="mt-2 flex items-center justify-between rounded-tile bg-surface px-4 py-2 text-s14">
                  <span>{code(m.team_a)} v {code(m.team_b)} · {localTime(m.start_time)}</span>
                  <button className="min-h-[44px] px-2 font-semibold text-orange" onClick={() => undo(m)}>Restore</button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      {setup && <SetupSheet match={setup} onClose={() => setSetup(null)} />}
    </section>
  );
}

function SwipeDeck({ cards, onChoose }: { cards: Card[]; onChoose: (m: Card, c: "play" | "skip") => Promise<boolean> }) {
  const top = cards[0];
  const x = useMotionValue(0);
  const reduce = useReducedMotion();
  const rotate = useTransform(x, [-220, 220], [-12, 12]);
  const play = useTransform(x, [20, 120], [0, 1]);
  const skip = useTransform(x, [-120, -20], [1, 0]);
  const nextScale = useTransform(x, [-200, 0, 200], [1, 0.95, 1]);
  const commit = useCallback(async (c: "play" | "skip") => {
    const to = c === "play" ? 700 : -700;
    if (reduce) x.set(to); else await animate(x, to, { type: "spring", stiffness: 260, damping: 30 });
    await onChoose(top, c);
    x.set(0);
  }, [onChoose, top, x, reduce]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea,select,[role=dialog]")) return;
      if (e.key === "ArrowRight") commit("play");
      if (e.key === "ArrowLeft") commit("skip");
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [commit]);
  return (
    <div>
      <div className="relative h-[min(68vh,520px)] min-h-[440px]">
        {cards[1] && <motion.div className="absolute inset-0" style={{ scale: nextScale }} aria-hidden><FixtureCard m={cards[1]} /></motion.div>}
        <motion.div key={top.id} className="absolute inset-0 cursor-grab touch-pan-y active:cursor-grabbing" style={{ x, rotate }}
          drag="x" dragConstraints={{ left: 0, right: 0 }} dragElastic={0.9}
          onDragEnd={(_, i) => { if (i.offset.x > 120) commit("play"); else if (i.offset.x < -120) commit("skip"); }}>
          <FixtureCard m={top} />
          <motion.span style={{ opacity: play }} className="num pointer-events-none absolute left-5 top-16 -rotate-12 rounded-tile border-4 border-green px-3 text-s34 font-extrabold text-green">PLAY</motion.span>
          <motion.span style={{ opacity: skip }} className="num pointer-events-none absolute right-5 top-16 rotate-12 rounded-tile border-4 border-muted px-3 text-s34 font-extrabold text-muted">SKIP</motion.span>
        </motion.div>
      </div>
      <div className="mt-6 flex items-center justify-center gap-8">
        <button onClick={() => commit("skip")} aria-label={`Skip ${code(top.team_a)} v ${code(top.team_b)}`}
          className="flex h-16 w-16 items-center justify-center rounded-full bg-surface2 text-muted shadow-card transition hover:text-ink"><X size={28} strokeWidth={2} /></button>
        <button onClick={() => commit("play")} aria-label={`Play this match: ${code(top.team_a)} v ${code(top.team_b)}`}
          className="flex h-20 w-20 items-center justify-center rounded-full bg-red text-white shadow-[0_14px_40px_rgba(232,23,44,0.45)]"><Check size={36} strokeWidth={2.5} /></button>
      </div>
      <p className="mt-3 text-center text-s12 text-muted">Swipe or use ← →</p>
    </div>
  );
}

function FixtureCard({ m }: { m: Card }) {
  const live = m.status === "live";
  return (
    <article className="noise relative flex h-full select-none flex-col overflow-hidden rounded-card p-5 shadow-card" style={matchArt(m.team_a?.colour, m.team_b?.colour)}
      aria-label={`${m.team_a?.name} vs ${m.team_b?.name}`}>
      <div className="relative flex items-center justify-between gap-2">
        <Chip tone="glass">{m.format === "T20" ? "T20" : m.format}</Chip>
        {live ? <Chip tone="red">LIVE</Chip> : <span className="num rounded-full bg-black/35 px-3 py-1 text-s12 font-bold text-orange">{countdown(m.start_time)}</span>}
      </div>
      <div className="relative flex flex-1 items-center justify-center gap-5">
        <Side t={m.team_a} />
        <span className="num text-[44px] font-extrabold italic text-orange drop-shadow">VS</span>
        <Side t={m.team_b} />
      </div>
      <div className="relative space-y-2">
        {m.series && <p className="truncate text-s14 font-semibold">{m.series}</p>}
        <p className="flex items-center gap-1.5 text-s14 text-muted"><MapPin size={14} strokeWidth={1.75} />{[m.venue, m.city].filter(Boolean).join(", ") || "Venue not announced"}</p>
        <p className="text-s14 text-ink/90">{localTime(m.start_time)}</p>
        <div className="flex flex-wrap gap-2 pt-1">
          <Chip tone="glass"><CloudRain size={13} strokeWidth={1.75} />{m.rain_chance == null ? "Rain n/a" : `${m.rain_chance}% rain`}</Chip>
          <Chip tone={m.xi_announced ? "green" : "glass"}><Users size={13} strokeWidth={1.75} />{m.xi_announced ? "XI announced" : "XI not yet"}</Chip>
        </div>
      </div>
    </article>
  );
}

function Side({ t }: { t: Match["team_a"] }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="rounded-full p-1" style={{ boxShadow: `0 0 40px ${t?.colour ?? "#3A3F52"}aa` }}><TeamBadge name={t?.name} code={t?.code} colour={t?.colour} size={84} /></div>
      <span className="num text-s26 font-bold">{code(t)}</span>
    </div>
  );
}

function DeckSkeleton() {
  return (
    <div aria-label="Loading fixtures">
      <div className="mb-5 flex gap-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[66px] w-[66px] !rounded-full" />)}</div>
      <div className="flex h-[440px] flex-col justify-between rounded-card bg-surface p-5">
        <Skeleton className="h-7 w-16 !rounded-full" />
        <div className="flex items-center justify-center gap-8"><Skeleton className="h-20 w-20 !rounded-full" /><Skeleton className="h-20 w-20 !rounded-full" /></div>
        <div className="space-y-2"><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/2" /></div>
      </div>
    </div>
  );
}
