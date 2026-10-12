"use client";
import { CalendarDays, ClipboardList, LineChart } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Welcome } from "./Welcome";

const TABS = [
  { href: "/upcoming", label: "Upcoming", Icon: CalendarDays },
  { href: "/results", label: "Results", Icon: ClipboardList },
  { href: "/learnings", label: "Learnings", Icon: LineChart },
];

// Phone-width column on every device (UI_REDESIGN.md section 3); floating glass pill tab bar.
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [waiting, setWaiting] = useState(0);
  useEffect(() => { api("/learnings").then((r) => setWaiting(r.inbox.length)).catch(() => {}); }, [path]);
  const link = (mobile: boolean) => TABS.map(({ href, label, Icon }) => {
    const on = path.startsWith(href);
    return mobile ? (
      <Link key={href} href={href} aria-current={on ? "page" : undefined}
        className={`relative flex min-h-[52px] flex-1 flex-col items-center justify-center gap-0.5 rounded-full text-s12 font-semibold transition ${on ? "text-ink" : "text-muted hover:text-ink"}`}>
        <Icon aria-hidden size={22} strokeWidth={1.75} /><span>{label}</span>
        {on && <span aria-hidden className="absolute bottom-1 h-1 w-1 rounded-full bg-red" />}
        {href === "/learnings" && waiting > 0 && <span className="num absolute right-[22%] top-1 min-w-5 rounded-full bg-red px-1.5 text-center text-[11px] font-bold text-white">{waiting}</span>}
      </Link>
    ) : (
      <Link key={href} href={href} aria-current={on ? "page" : undefined}
        className={`flex min-h-[48px] items-center gap-3 rounded-full px-4 font-semibold transition ${on ? "bg-white/10 text-ink" : "text-muted hover:bg-white/5 hover:text-ink"}`}>
        <Icon aria-hidden size={20} strokeWidth={1.75} />{label}
        {href === "/learnings" && waiting > 0 && <span className="num ml-auto rounded-full bg-red px-2 text-[11px] font-bold text-white">{waiting}</span>}
      </Link>
    );
  });
  return (
    <div className="min-h-screen md:flex">
      <Welcome />
      <nav aria-label="Main" className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col gap-1 border-r border-white/5 bg-black/20 p-5 backdrop-blur-xl md:flex">
        <div className="num mb-8 px-3 text-s26 font-extrabold">Match<span className="text-red">day</span></div>
        {link(false)}
      </nav>
      <main className="mx-auto w-full max-w-[440px] px-5 pb-32 pt-6 md:max-w-[1180px] md:px-10 md:pb-12 md:pt-10">{children}</main>
      <nav aria-label="Tabs" className="glass fixed inset-x-0 bottom-4 z-40 mx-auto flex w-[calc(100%-40px)] max-w-[400px] justify-around rounded-full px-2 py-1.5 shadow-card md:hidden">{link(true)}</nav>
    </div>
  );
}
