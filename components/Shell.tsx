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
  return (
    <div className="mx-auto min-h-screen w-full max-w-[440px] md:my-6 md:min-h-[calc(100vh-48px)] md:overflow-hidden md:rounded-[40px] md:border md:border-white/10 md:bg-bg/40 md:shadow-card">
      <Welcome />
      <main className="px-5 pb-32 pt-6">{children}</main>
      <nav aria-label="Tabs" className="fixed inset-x-0 bottom-4 z-40 mx-auto flex w-[calc(100%-40px)] max-w-[400px] justify-around rounded-full glass px-2 py-1.5 shadow-card">
        {TABS.map(({ href, label, Icon }) => {
          const on = path.startsWith(href);
          return (
            <Link key={href} href={href} aria-current={on ? "page" : undefined}
              className={`relative flex min-h-[52px] flex-1 flex-col items-center justify-center gap-0.5 rounded-full text-s12 font-semibold transition ${on ? "text-ink" : "text-muted hover:text-ink"}`}>
              <Icon aria-hidden size={22} strokeWidth={1.75} />
              <span>{label}</span>
              {on && <span aria-hidden className="absolute bottom-1 h-1 w-1 rounded-full bg-red" />}
              {href === "/learnings" && waiting > 0 && (
                <span className="num absolute right-[22%] top-1 min-w-5 rounded-full bg-red px-1.5 text-center text-[11px] font-bold text-white" aria-label={`${waiting} waiting`}>{waiting}</span>
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
