"use client";
import { motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";
import { useState } from "react";
import { api, RunStatus } from "@/lib/api";
import { Button, ErrorNote, haptic } from "./ui";

const STEPS = [
  ["checking", "Checking who can play"], ["scoring", "Scoring players"], ["moderating", "Reading today's news and pitch report"],
  ["optimizing", "Building the best valid team"], ["explaining", "Writing the reasons"],
] as const;

// Starts a run and advances it one real step per request; each step ticks when the server reports it finished.
export function BuildProgress({ matchId, runType, onDone, onBack, label = "Build my team" }:
  { matchId: string; runType: string; onDone: (runId: string) => void; onBack?: () => void; label?: string }) {
  const [run, setRun] = useState<RunStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const reduce = useReducedMotion();

  const go = async () => {
    setBusy(true); setErr(null);
    try {
      let rid = run?.status === "failed" ? null : run?.run_id;
      if (!rid) rid = (await api(`/matches/${encodeURIComponent(matchId)}/runs`, { method: "POST", body: { run_type: runType } })).run_id as string;
      let st: RunStatus = await api(`/runs/${rid}`);
      setRun(st);
      while (st.status !== "done" && st.status !== "failed") {
        st = await api(`/runs/${rid}/advance`, { method: "POST" });
        setRun(st);
      }
      if (st.status === "done") { haptic(); onDone(rid); }
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };

  const idx = run ? STEPS.findIndex(([k]) => k === (run.status === "failed" ? run.failed_step : run.status)) : -1;
  return (
    <div className="space-y-4">
      {(!run || run.status === "failed" || err) && <Button className="w-full" onClick={go} disabled={busy}>{run?.status === "failed" ? "Try again" : label}</Button>}
      {run && (
        <ol className="space-y-1 rounded-card bg-surface p-3" aria-live="polite">
          {STEPS.map(([k, l], i) => {
            const done = run.status === "done" || i < idx;
            const failed = run.status === "failed" && i === idx;
            const now = !done && !failed && i === idx;
            return (
              <li key={k} className="flex items-start gap-3 rounded-tile p-2">
                <span aria-hidden className={`relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${done ? "bg-green" : failed ? "bg-red" : "bg-surface2"}`}>
                  {now && <span className="spin-slow absolute inset-0 rounded-full border-2 border-transparent border-t-orange" />}
                  {done ? <motion.span initial={reduce ? false : { scale: 0 }} animate={{ scale: 1 }}><Check size={16} strokeWidth={3} /></motion.span>
                    : failed ? <span className="font-bold">!</span> : <span className="num text-s12 text-muted">{i + 1}</span>}
                </span>
                <div className="pt-1">
                  <span className={done ? "text-ink" : now ? "font-semibold text-ink" : "text-muted"}>{l}</span>
                  <span className="sr-only">{done ? " done" : failed ? " failed" : now ? " in progress" : ""}</span>
                  {failed && <p className="mt-1 text-s14 text-red">{run.error_message}</p>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {err && <ErrorNote>{err}</ErrorNote>}
      {run?.status === "failed" && onBack && <Button kind="quiet" className="w-full" onClick={onBack}>Back to credits and roles</Button>}
    </div>
  );
}
