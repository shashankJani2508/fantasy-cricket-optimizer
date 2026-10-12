"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorNote, pts, Skeleton } from "./ui";

type SC = {
  system_points: number | null; aryan_points: number | null; simple_points: number | null; perfect_points: number | null;
  points_roi: number | null; efficiency: number | null; captain_hit: boolean | null; captain_rank: number | null; captain_name: string | null;
  points_final: boolean; mismatches: number; predicted_vs_actual: { player_id: string; name: string; predicted: number | null; actual: number | null; real_miss: boolean }[];
  swaps: { out: string; in: string; out_points: number | null; in_points: number | null }[];
};
const ord = (n: number) => `${n}${["th", "st", "nd", "rd"][n % 100 > 10 && n % 100 < 14 ? 0 : n % 10 < 4 ? n % 10 : 0]}`;

export function Scorecard({ matchId }: { matchId: string }) {
  const [sc, setSc] = useState<SC | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<SC>(`/matches/${encodeURIComponent(matchId)}/scorecard`).then(setSc).catch((e) => setErr(e.message)); }, [matchId]);
  if (err) return <ErrorNote>{err}</ErrorNote>;
  if (!sc) return <Skeleton className="mt-6 h-64" />;
  const max = Math.max(1, ...sc.predicted_vs_actual.flatMap((r) => [r.predicted ?? 0, r.actual ?? 0]));
  const Big = ({ label, v }: { label: string; v: number | null }) => (
    <div className="flex-1 rounded-sheet bg-pavilion p-3 text-sightscreen"><div className="text-s12 opacity-80">{label}</div><div className="num text-s40 leading-none">{pts(v, 0)}</div></div>
  );
  return (
    <section className="mt-6 space-y-4" aria-labelledby="h-sc">
      <h2 id="h-sc" className="num text-s28">Scorecard</h2>
      {!sc.points_final && <p className="rounded-sheet bg-clay/50 p-3 text-s14">Approximate until full match data arrives (usually a few days).</p>}
      {sc.mismatches > 0 && <p className="rounded-sheet bg-floodlight/25 p-3 text-s14">⚠ Our calculation differs for {sc.mismatches} players. Check the points table in Settings.</p>}
      <div className="flex gap-2"><Big label="System's team" v={sc.system_points} /><Big label="Your final team" v={sc.aryan_points} /><Big label="Simple team" v={sc.simple_points} /></div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-sheet bg-surface p-3"><div className="text-s12 text-slate">Points ROI (system − simple)</div>
          <div className={`num text-s28 ${sc.points_roi == null ? "" : sc.points_roi >= 0 ? "text-turf" : "text-ball"}`}>{sc.points_roi == null ? "–" : `${sc.points_roi >= 0 ? "▲ +" : "▼ "}${pts(sc.points_roi, 0)}`}</div></div>
        <div className="rounded-sheet bg-surface p-3"><div className="text-s12 text-slate">Efficiency (system ÷ perfect {pts(sc.perfect_points, 0)})</div>
          <div className="num text-s28">{sc.efficiency == null ? "–" : `${Math.round(sc.efficiency * 100)}%`}</div>
          {sc.efficiency != null && <div className="h-1.5 rounded-full bg-slate/15"><div className="h-1.5 rounded-full bg-turf" style={{ width: `${Math.min(100, sc.efficiency * 100)}%` }} /></div>}</div>
        <div className="rounded-sheet bg-surface p-3"><div className="text-s12 text-slate">Captain hit</div>
          <div className="text-s16">{sc.captain_rank ? `Captain ${sc.captain_name ?? ""} was ${ord(sc.captain_rank)} top scorer` : "Captain's points not available"}</div></div>
      </div>
      {sc.swaps.length > 0 && (
        <div><h3 className="font-semibold">Your swaps</h3>
          {sc.swaps.map((s, i) => {
            const d = (s.in_points ?? 0) - (s.out_points ?? 0);
            return <p key={i} className="text-s14">You swapped {s.out} for {s.in}: {s.in} scored {pts(Math.abs(d), 0)} {d >= 0 ? "more" : "fewer"}.</p>;
          })}</div>
      )}
      <div>
        <h3 className="font-semibold">Predicted vs actual</h3>
        <p className="text-s12 text-slate"><span className="inline-block h-2 w-3 bg-clay" /> predicted <span className="ml-2 inline-block h-2 w-3 bg-turf" /> actual</p>
        <ul className="mt-2 space-y-2">
          {sc.predicted_vs_actual.map((r) => (
            <li key={r.player_id} className="text-s14">
              <div className="flex justify-between"><span>{r.name}{r.real_miss && <span className="ml-2 rounded-full bg-ball px-2 text-s12 text-white">Real miss</span>}</span>
                <span className="num text-s16">{pts(r.predicted, 0)} → {pts(r.actual, 0)}</span></div>
              <div className="h-1.5 rounded-full bg-clay" style={{ width: `${(Math.max(0, r.predicted ?? 0) / max) * 100}%` }} />
              <div className="mt-0.5 h-1.5 rounded-full bg-turf" style={{ width: `${(Math.max(0, r.actual ?? 0) / max) * 100}%` }} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
