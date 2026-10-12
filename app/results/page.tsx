"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Match } from "@/lib/api";
import { matchArt } from "@/lib/teams";
import { Chip, ErrorNote, localTime, PillTabs, Skeleton, TeamBadge, Tone } from "@/components/ui";

type Row = Match & { run_id: string; run_status: string; state: string; finished: boolean };
const TONE: Record<string, Tone> = { Provisional: "amber", Final: "green", "Toss done: refresh": "orange", "Enter results": "orange", Scored: "glass" };

export default function Results() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [seg, setSeg] = useState<"upcoming" | "finished">("upcoming");
  useEffect(() => { api("/results/matches").then((r) => setRows(r.matches)).catch((e) => setErr(e.message)); }, []);
  const list = rows?.filter((r) => (seg === "finished") === r.finished) ?? [];
  return (
    <section aria-labelledby="h-res" className="space-y-5">
      <h1 id="h-res" className="num text-s26 font-bold">Results</h1>
      <PillTabs label="Match list" value={seg} onChange={setSeg} tabs={[{ key: "upcoming", label: "Upcoming" }, { key: "finished", label: "Finished" }]} />
      {err && <ErrorNote>Couldn&apos;t load your matches: {err}</ErrorNote>}
      {!rows && !err && <div className="space-y-3">{[0, 1].map((i) => <Skeleton key={i} className="h-32 !rounded-card" />)}</div>}
      {rows && list.length === 0 && (
        <div className="rounded-card bg-surface p-6 text-center shadow-card">
          <p className="num text-s20 font-bold">{seg === "upcoming" ? "No teams built yet" : "No finished matches yet"}</p>
          {seg === "upcoming" && <Link href="/upcoming" className="mt-4 inline-flex min-h-[44px] items-center rounded-full bg-red px-5 font-semibold">Pick a match to play</Link>}
        </div>
      )}
      <ul className="space-y-3">
        {list.map((r) => (
          <li key={r.id}>
            <Link href={`/results/${encodeURIComponent(r.id)}`} className="noise relative block overflow-hidden rounded-card p-4 shadow-card" style={matchArt(r.team_a?.colour, r.team_b?.colour)}>
              <div className="relative flex items-center justify-between gap-2">
                <span className="text-s12 text-ink/80">{localTime(r.start_time)} · {r.format}</span>
                {r.run_status === "failed" ? <Chip tone="red">Build failed</Chip> : r.run_status !== "done" ? <Chip tone="glass">Building</Chip> : <Chip tone={TONE[r.state] ?? "glass"}>{r.state}</Chip>}
              </div>
              <div className="relative mt-3 flex items-center gap-3">
                <TeamBadge name={r.team_a?.name} code={r.team_a?.code} colour={r.team_a?.colour} size={40} />
                <span className="num text-s20 font-bold">{r.team_a?.code}</span>
                <span className="num font-extrabold italic text-orange">VS</span>
                <span className="num text-s20 font-bold">{r.team_b?.code}</span>
                <TeamBadge name={r.team_b?.name} code={r.team_b?.code} colour={r.team_b?.colour} size={40} />
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
