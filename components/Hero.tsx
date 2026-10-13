"use client";
import { useState } from "react";

// Top banner. Artwork is drawn in code (SVG); if /public/hero.jpg exists it is shown instead, only once it has loaded.
export function Hero({ onPlay }: { onPlay: () => void }) {
  const [photo, setPhoto] = useState(false);
  return (
    <section className="relative mb-6 overflow-hidden rounded-card bg-black shadow-card" aria-label="Welcome">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/hero.jpg" alt="" onLoad={() => setPhoto(true)} onError={() => setPhoto(false)}
        className={`absolute inset-y-0 right-0 h-full w-full object-cover object-right md:w-[70%] ${photo ? "" : "hidden"}`} />
      {!photo && <Art />}
      <div aria-hidden className="absolute inset-0 bg-gradient-to-r from-black via-black/75 to-transparent md:via-black/40" />
      <div className="relative flex min-h-[260px] flex-col justify-center gap-5 p-6 md:min-h-[340px] md:p-10">
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

function Art() {
  return (
    <svg aria-hidden viewBox="0 0 800 400" preserveAspectRatio="xMaxYMid slice" className="absolute inset-0 h-full w-full">
      <defs>
        <radialGradient id="glow" cx="72%" cy="50%" r="55%"><stop offset="0" stopColor="#E8172C" stopOpacity=".75" /><stop offset="1" stopColor="#000" stopOpacity="0" /></radialGradient>
        <linearGradient id="screen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ff3347" /><stop offset="1" stopColor="#7a0612" /></linearGradient>
        <linearGradient id="streak" x1="0" x2="1"><stop offset="0" stopColor="#E8172C" stopOpacity="0" /><stop offset=".6" stopColor="#ff4a5c" /><stop offset="1" stopColor="#fff" /></linearGradient>
        <linearGradient id="kit" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2f5fd6" /><stop offset="1" stopColor="#13306e" /></linearGradient>
      </defs>
      <rect width="800" height="400" fill="#000" />
      <rect width="800" height="400" fill="url(#glow)" />
      {[[330, 360, 760, 20], [380, 400, 800, 70], [300, 330, 700, -10], [470, 400, 800, 160], [420, 380, 780, 110]].map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="url(#streak)" strokeWidth={i % 2 ? 2 : 4} strokeLinecap="round" opacity={0.7 - i * 0.08} />
      ))}
      <text x="760" y="150" textAnchor="end" fontSize="120" fontWeight="900" fontStyle="italic" fill="none" stroke="#fff" strokeOpacity=".08" strokeWidth="2" fontFamily="sans-serif">PLAY</text>
      <g transform="rotate(12 600 200)">
        <rect x="520" y="40" width="170" height="320" rx="26" fill="#111" stroke="#444" strokeWidth="4" />
        <rect x="532" y="52" width="146" height="296" rx="18" fill="url(#screen)" />
        <rect x="582" y="60" width="46" height="10" rx="5" fill="#111" />
      </g>
      {/* batter silhouette bursting out of the phone */}
      <g transform="translate(560 95) scale(1.15)">
        <circle cx="40" cy="20" r="17" fill="#13306e" />
        <path d="M24 18 C26 2 54 2 57 18 L57 22 L24 22 Z" fill="#0d1d45" />
        <path d="M22 40 C30 30 52 30 60 40 L66 100 L16 100 Z" fill="url(#kit)" />
        <path d="M60 46 L96 10 L104 16 L70 58 Z" fill="url(#kit)" />
        <rect x="95" y="-58" width="12" height="80" rx="4" transform="rotate(18 101 -18)" fill="#e8c88a" />
        <path d="M22 46 L-14 22 L-20 30 L16 60 Z" fill="url(#kit)" />
        <circle cx="-18" cy="24" r="9" fill="#f5f6f8" />
        <path d="M18 100 L8 170 L24 172 L38 104 Z M48 104 L62 172 L78 168 L64 100 Z" fill="#0d1d45" />
      </g>
      {Array.from({ length: 26 }).map((_, i) => (
        <circle key={i} cx={470 + ((i * 53) % 300)} cy={60 + ((i * 97) % 300)} r={(i % 4) + 1.5} fill="#ff3347" opacity={0.35 + (i % 5) * 0.12} />
      ))}
    </svg>
  );
}
