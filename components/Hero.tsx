"use client";
import { useState } from "react";

// Top banner (original artwork in /public/hero.jpg, generated for this app). Falls back to a red glow if missing.
export function Hero({ onPlay }: { onPlay: () => void }) {
  const [img, setImg] = useState(true);
  return (
    <section className="relative mb-6 overflow-hidden rounded-card bg-black shadow-card" aria-label="Welcome">
      {img && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="/hero.jpg" alt="" onError={() => setImg(false)}
          className="absolute inset-y-0 right-0 h-full w-full object-cover object-right md:w-[70%]" />
      )}
      <div aria-hidden className="absolute inset-0 bg-gradient-to-r from-black via-black/80 to-transparent md:via-black/60" />
      {!img && <div aria-hidden className="absolute inset-0" style={{ background: "radial-gradient(60% 90% at 85% 50%, rgba(232,23,44,0.55), transparent 70%)" }} />}
      <div className="relative flex min-h-[240px] flex-col justify-center gap-5 p-6 md:min-h-[320px] md:p-10">
        <h2 className="num max-w-[16ch] text-[30px] font-extrabold italic leading-[1.05] md:text-[48px]">
          Your match day.<br />Your best eleven.
        </h2>
        <p className="max-w-[34ch] text-s14 text-ink/80">Pick a match, upload your Dream11 screenshots, and get a team you can defend in a minute.</p>
        <button onClick={onPlay} className="w-fit rounded-tile border border-white/25 bg-white/5 px-6 py-3 text-s16 font-bold backdrop-blur transition hover:bg-white/10">
          Let&apos;s play ›
        </button>
      </div>
    </section>
  );
}
