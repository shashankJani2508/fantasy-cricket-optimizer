"use client";

// Top banner: original artwork made in Canva for this app (/public/hero.jpg).
export function Hero({ onPlay }: { onPlay: () => void }) {
  return (
    <section className="relative mb-6 overflow-hidden rounded-card bg-black shadow-card" aria-label="Welcome">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/hero.jpg" alt="" className="absolute inset-y-0 right-0 h-full w-full object-cover object-right md:w-[75%]" />
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
