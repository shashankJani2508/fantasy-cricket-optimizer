"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import { Button } from "./ui";

const SLIDES = [
  { title: "Your match day, sorted", body: "Swipe through this week's matches.", a: "#0B7A3E", b: "#1E3F8F" },
  { title: "A team you can defend", body: "Every pick comes with a reason.", a: "#E8172C", b: "#3A0E1C" },
  { title: "Gets sharper every match", body: "It learns from your results.", a: "#FF7A1A", b: "#1A1F4A" },
];
const KEY = "matchday.welcomed";

// First visit only: three slides with generated cricket artwork (shapes and gradients, no photos).
export function Welcome() {
  const [show, setShow] = useState(false);
  const [i, setI] = useState(0);
  const reduce = useReducedMotion();
  useEffect(() => { try { setShow(!localStorage.getItem(KEY)); } catch { /* storage blocked: skip */ } }, []);
  const done = () => { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } setShow(false); };
  if (!show) return null;
  const s = SLIDES[i];
  return (
    <div className="fixed inset-0 z-[70] flex justify-center bg-bg" role="dialog" aria-label="Welcome">
      <div className="relative flex h-full w-full max-w-[440px] flex-col">
        <button onClick={done} className="absolute right-5 top-5 z-10 min-h-[44px] rounded-full glass px-4 text-s14 font-semibold">Skip</button>
        <AnimatePresence mode="wait">
          <motion.div key={i} className="noise relative flex-1 overflow-hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.3 }}
            style={{ backgroundImage: `radial-gradient(90% 50% at 50% 10%, rgba(255,255,255,0.35), transparent 60%), linear-gradient(to bottom, transparent 40%, #0A0B10 92%), linear-gradient(150deg, ${s.a}, ${s.b})` }}>
            <Art index={i} />
          </motion.div>
        </AnimatePresence>
        <div className="px-6 pb-10 text-center">
          <h1 className="num text-[28px] font-bold leading-tight">{s.title}</h1>
          <p className="mt-2 text-s14 text-muted">{s.body}</p>
          <div className="my-6 flex justify-center gap-2" aria-label={`Slide ${i + 1} of 3`}>
            {SLIDES.map((_, j) => <span key={j} className={`h-1.5 rounded-full transition-all ${j === i ? "w-6 bg-red" : "w-1.5 bg-white/30"}`} />)}
          </div>
          <Button className="w-full" onClick={() => (i < 2 ? setI(i + 1) : done())}>{i < 2 ? "Continue" : "Get started"}</Button>
        </div>
      </div>
    </div>
  );
}

function Art({ index }: { index: number }) {
  // Generic cricket shapes: stumps and bails, a ball with seam, an oval ground.
  return (
    <svg viewBox="0 0 300 300" className="absolute inset-x-0 top-[12%] mx-auto w-[78%] opacity-90" aria-hidden>
      {index === 0 && <g fill="none" stroke="#fff" strokeWidth="6" strokeLinecap="round">
        <line x1="120" y1="80" x2="120" y2="240" /><line x1="150" y1="80" x2="150" y2="240" /><line x1="180" y1="80" x2="180" y2="240" />
        <line x1="112" y1="72" x2="148" y2="72" /><line x1="152" y1="72" x2="188" y2="72" /></g>}
      {index === 1 && <g><circle cx="150" cy="150" r="90" fill="#B5172F" stroke="#fff" strokeOpacity=".5" strokeWidth="3" />
        <path d="M95 85 Q150 150 95 215 M205 85 Q150 150 205 215" stroke="#fff" strokeWidth="4" strokeDasharray="6 8" fill="none" /></g>}
      {index === 2 && <g fill="none" stroke="#fff"><ellipse cx="150" cy="150" rx="120" ry="95" strokeWidth="5" />
        <rect x="138" y="100" width="24" height="100" rx="4" fill="#D9C9A3" fillOpacity=".7" stroke="none" />
        <polyline points="40,250 100,215 150,228 210,180 262,190" strokeWidth="6" strokeLinecap="round" stroke="#FF7A1A" /></g>}
    </svg>
  );
}
