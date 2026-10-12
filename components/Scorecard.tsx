"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Chip, ErrorNote, pts, Skeleton, Warning } from "./ui";

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
  if (!sc) return <Skeleton className="h-72 !rounded-card" />;
  const Big = ({ label, v }: { label: string; v: number | null }) => (
    <div className="flex-1 rounded-tile bg-surface2 p-3 text-center"><div className="num text-s26 font-extrabold leading-none">{pts(v, 0)}</div><div className="mt-1 text-[11px] text-muted">{label}</div></div>
  );
  return (
    <section className="space-y-4" aria-label="Scorecard">
      {!sc.points_final && <p className="rounded-tile bg-surface px-4 py-3 text-s12 text-muted">Approximate until full match data arrives (usually a few days).</p>}
      {sc.mismatches > 0 && <Warning>Our calculation differs for {sc.mismatches} players. Check the points table in Settings.</Warning>}
      <div className="rounded-card bg-surface p-4 shadow-card">
        <div className="flex gap-2"><Big label="System" v={sc.system_points} /><Big label="Your team" v={sc.aryan_points} /><Big label="Simple team" v={sc.simple_points} /></div>
        <div className="mt-3 flex flex-wrap gap-2">
          {sc.points_roi != null && <Chip tone={sc.points_roi >= 0 ? "green" : "red"}>{sc.points_roi >= 0 ? "▲ +" : "▼ "}{pts(sc.points_roi, 0)} points ROI</Chip>}
          {sc.efficiency != null && <Chip tone="glass">{Math.round(sc.efficiency * 100)}% of perfect ({pts(sc.perfect_points, 0)})</Chip>}
          <Chip tone="gold">{sc.captain_rank ? `Captain ${ord(sc.captain_rank)} top scorer` : "Captain's points n/a"}</Chip>
        </div>
      </div>
      <div className="overflow-hidden rounded-card bg-surface shadow-card">
        <div className="grid grid-cols-[1fr_52px_52px_52px] gap-1 px-4 pb-2 pt-4 text-[11px] font-semibold text-muted">
          <span>Player</span><span className="text-right">Pred</span><span className="text-right">Actual</span><span className="text-right">Diff</span>
        </div>
        {sc.predicted_vs_actual.map((r) => {
          const d = r.actual != null && r.predicted != null ? r.actual - r.predicted : null;
          return (
            <div key={r.player_id} className="grid grid-cols-[1fr_52px_52px_52px] items-center gap-1 border-t hairline px-4 py-2.5 text-s14">
              <span className="truncate">{r.name}{r.real_miss && <span className="ml-2 rounded-full bg-red/15 px-2 text-[11px] font-semibold text-red">Real miss</span>}</span>
              <span className="num text-right text-muted">{pts(r.predicted, 0)}</span>
              <span className="num text-right font-bold">{pts(r.actual, 0)}</span>
              <span className={`num text-right font-bold ${d == null ? "" : d >= 0 ? "text-green" : "text-red"}`}>{d == null ? "–" : `${d >= 0 ? "+" : ""}${pts(d, 0)}`}</span>
            </div>
          );
        })}
      </div>
      {sc.swaps.length > 0 && (
        <div className="rounded-card bg-surface p-4 shadow-card"><h3 className="mb-2 font-semibold">Your swaps</h3>
          {sc.swaps.map((s, i) => {
            const d = (s.in_points ?? 0) - (s.out_points ?? 0);
            return <p key={i} className="text-s14 text-muted">You swapped {s.out} for {s.in}: <span className={d >= 0 ? "text-green" : "text-red"}>{s.in} scored {pts(Math.abs(d), 0)} {d >= 0 ? "more" : "fewer"}</span>.</p>;
          })}
        </div>
      )}
    </section>
  );
}
