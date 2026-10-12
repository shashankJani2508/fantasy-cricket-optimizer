"use client";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PlayerAvatar, Skeleton } from "@/components/ui";

type C = { name: string; url: string; author: string; license: string; page: string };

export default function Credits() {
  const [rows, setRows] = useState<C[] | null>(null);
  useEffect(() => { api("/credits").then((r) => setRows(r.photos)).catch(() => setRows([])); }, []);
  return (
    <section className="space-y-5">
      <Link href="/learnings/settings" className="inline-flex h-11 w-11 items-center justify-center rounded-full glass" aria-label="Back to settings"><ChevronLeft size={22} /></Link>
      <h1 className="num text-s26 font-bold">Photo credits</h1>
      <p className="text-s14 text-muted">Player photos from Wikimedia Commons under free licences.</p>
      {!rows ? <Skeleton className="h-40 !rounded-card" /> : rows.length === 0 ? <p className="text-muted">No Wikimedia photos in use yet.</p> : (
        <ul className="grid gap-2 md:grid-cols-2">
          {rows.map((r) => (
            <li key={r.page} className="flex items-center gap-3 rounded-tile bg-surface p-3">
              <PlayerAvatar name={r.name} url={r.url} colour={null} size={44} />
              <div className="min-w-0 text-s14"><div className="font-semibold">{r.name}</div>
                <a href={r.page} target="_blank" rel="noreferrer noopener" className="text-muted underline-offset-2 hover:underline">{r.author} · {r.license}</a></div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
