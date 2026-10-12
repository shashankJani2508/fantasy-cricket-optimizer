"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Match } from "@/lib/api";
import { Chip, ErrorNote, localTime, Skeleton } from "@/components/ui";

type Row = Match & { run_id: string; run_status: string; state: string; finished: boolean };
const TONE: Record<string, "clay" | "turf" | "floodlight" | "pavilion"> = {
  Provisional: "clay", Final: "turf", "Toss done: refresh": "floodlight", "Enter results": "floodlight", Scored: "pavilion",
};

export default function Results() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [seg, setSeg] = useState<"upcoming" | "finished">("upcoming");
  useEffect(() => { api("/results/matches").then((r) => setRows(r.matches)).catch((e) => setErr(e.message)); }, []);
  const list = rows?.filter((r) => (seg === "finished") === r.finished) ?? [];
  return (
    <section aria-labelledby="h-res">
      <h1 id="h-res" className="num mb-4 text-s40">Results</h1>
      <div role="tablist" className="mb-4 flex gap-2">
        {(["upcoming", "finished"] as const).map((s) => (
          <button key={s} role="tab" aria-selected={seg === s} onClick={() => setSeg(s)}
            className={`min-h-[44px] rounded-full px-4 ${seg === s ? "bg-pavilion text-sightscreen" : "bg-surface"}`}>{s === "upcoming" ? "Upcoming" : "Finished"}</button>
        ))}
      </div>
      {err && <ErrorNote>Couldn&apos;t load your matches: {err}</ErrorNote>}
      {!rows && !err && <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>}
      {rows && list.length === 0 && (
        <div className="rounded-card bg-surface p-6 text-center">
          <p>{seg === "upcoming" ? "No teams built yet." : "No finished matches yet."}</p>
          {seg === "upcoming" && <Link href="/upcoming" className="mt-3 inline-block font-semibold text-turf underline">Swipe right on a match to build a team</Link>}
        </div>
      )}
      <ul className="space-y-2">
        {list.map((r) => (
          <li key={r.id}>
            <Link href={`/results/${encodeURIComponent(r.id)}`} className="flex min-h-[64px] items-center justify-between gap-3 rounded-sheet bg-surface p-4">
              <div>
                <div className="num text-s20">{r.team_a?.code} vs {r.team_b?.code}</div>
                <div className="text-s12 text-slate">{localTime(r.start_time)} · {r.format}</div>
              </div>
              {r.run_status === "failed" ? <Chip tone="ball">Build failed</Chip> : r.run_status !== "done" ? <Chip>Building</Chip> : <Chip tone={TONE[r.state] ?? "slate"}>{r.state}</Chip>}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
