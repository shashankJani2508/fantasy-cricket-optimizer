"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "./ui";

const TABS = [
  { href: "/upcoming", label: "Upcoming", icon: "M4 6h16M4 12h16M4 18h10" },
  { href: "/results", label: "Results", icon: "M5 4h14v16H5zM9 8h6M9 12h6M9 16h3" },
  { href: "/learnings", label: "Learnings", icon: "M4 18l5-6 4 3 7-9" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { aryan } = useAuth();
  const [waiting, setWaiting] = useState(0);
  useEffect(() => { api("/learnings").then((r) => setWaiting(r.inbox.length)).catch(() => {}); }, [path]);
  const nav = (rail: boolean) => TABS.map((t) => {
    const on = path.startsWith(t.href);
    return (
      <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined}
        className={`relative flex min-h-[56px] flex-1 flex-col items-center justify-center gap-1 text-s12 md:flex-none md:flex-row md:justify-start md:gap-3 md:rounded-sheet md:px-4 md:text-s16 ${on ? "text-floodlight" : "text-sightscreen/80"}`}>
        <svg aria-hidden width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={t.icon} /></svg>
        <span>{t.label}</span>
        {t.href === "/learnings" && waiting > 0 && <span className="num absolute right-[28%] top-1 rounded-full bg-ball px-1.5 text-s12 text-white md:static" aria-label={`${waiting} waiting`}>{waiting}</span>}
        {rail && null}
      </Link>
    );
  });
  return (
    <div className="min-h-screen md:flex">
      <nav aria-label="Main" className="hidden w-56 shrink-0 flex-col gap-1 bg-pavilion p-4 md:flex">
        <div className="num mb-6 px-4 text-s28 text-sightscreen">Match day</div>
        {nav(true)}
        {!aryan && <span className="mt-auto px-4 text-s12 text-sightscreen/70">View only</span>}
      </nav>
      <main className="mx-auto w-full max-w-[1100px] px-4 pb-28 pt-4 md:pb-10">
        {!aryan && <div className="mb-2 flex justify-end md:hidden"><span className="rounded-full bg-slate/15 px-3 py-1 text-s12">View only</span></div>}
        {children}
      </main>
      <nav aria-label="Tabs" className="fixed inset-x-0 bottom-0 z-40 flex bg-pavilion pb-[env(safe-area-inset-bottom)] md:hidden">{nav(false)}</nav>
    </div>
  );
}
