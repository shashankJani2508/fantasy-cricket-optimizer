"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

// ---------- formatting ----------
export const pts = (x: number | null | undefined, d = 1) => (x == null ? "–" : (Math.round(x * 10 ** d) / 10 ** d).toString());
export function localTime(iso: string | null) {
  if (!iso) return "Time not announced";
  const t = new Date(iso);
  return t.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}
export function countdown(iso: string | null) {
  if (!iso) return "";
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "Started";
  const h = Math.floor(ms / 3.6e6), d = Math.floor(h / 24);
  return d > 0 ? `Starts in ${d}d ${h % 24}h` : `Starts in ${h}h ${Math.floor((ms % 3.6e6) / 6e4)}m`;
}
export const surname = (n: string) => n.split(" ").slice(-1)[0];
export const initials = (n: string) => n.split(" ").filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
export const haptic = () => { try { navigator.vibrate?.(10); } catch { /* not supported */ } };

// ---------- primitives ----------
export function Button({ kind = "primary", className = "", ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: "primary" | "quiet" | "danger" }) {
  const k = kind === "primary" ? "bg-turf text-white" : kind === "danger" ? "bg-ball text-white" : "border border-fg/10 text-fg bg-surface";
  return <button {...p} className={`min-h-[44px] rounded-full px-5 text-s16 font-semibold transition-opacity disabled:opacity-40 ${k} ${className}`} />;
}

export function Chip({ tone = "slate", children, className = "" }: { tone?: "turf" | "ball" | "floodlight" | "clay" | "slate" | "pavilion"; children: ReactNode; className?: string }) {
  const t = { turf: "bg-turf text-white", ball: "bg-ball text-white", floodlight: "bg-floodlight text-pavilion", clay: "bg-clay text-pavilion",
    slate: "bg-slate/15 text-fg", pavilion: "bg-pavilion text-sightscreen" }[tone];
  return <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-s12 font-semibold ${t} ${className}`}>{children}</span>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`shimmer rounded-input ${className}`} />;
}

export function Warning({ children }: { children: ReactNode }) {
  return <div role="note" className="flex gap-2 rounded-sheet bg-floodlight/25 p-3 text-s14"><span aria-hidden>⚠</span><div>{children}</div></div>;
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div role="alert" className="rounded-sheet border border-ball/40 bg-ball/10 p-3 text-s14 text-fg">{children}</div>;
}

export function PlayerAvatar({ name, url, colour, size = 56, badge }: { name: string; url: string | null; colour: string | null; size?: number; badge?: "C" | "VC" }) {
  const [broken, setBroken] = useState(false);
  const ring = colour ?? "rgb(var(--slate))";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <div className="h-full w-full overflow-hidden rounded-full" style={{ boxShadow: `0 0 0 3px ${ring}`, background: colour ?? "rgb(var(--slate))" }}>
        {url && !broken ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={name} width={size} height={size} loading="lazy" onError={() => setBroken(true)} className="h-full w-full object-cover" />
        ) : (
          <div aria-label={name} role="img" className="num flex h-full w-full items-center justify-center text-white" style={{ fontSize: size * 0.38 }}>{initials(name)}</div>
        )}
      </div>
      {badge && (
        <span className={`num absolute -right-1 -top-1 flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-s14 ${badge === "C" ? "bg-ball text-white" : "bg-floodlight text-pavilion"}`}
          aria-label={badge === "C" ? "Captain" : "Vice-captain"}>{badge}</span>
      )}
    </div>
  );
}

// ---------- bottom sheet ----------
export function Sheet({ open, onClose, title, children, wide = false }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center">
          <motion.div className="absolute inset-0 bg-pavilion/50" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div ref={ref} tabIndex={-1} role="dialog" aria-modal aria-label={title}
            className={`relative max-h-[92vh] w-full overflow-y-auto rounded-t-sheet bg-app p-4 pb-8 outline-none md:rounded-sheet ${wide ? "md:max-w-2xl" : "md:max-w-lg"}`}
            initial={reduce ? { opacity: 0 } : { y: "100%" }} animate={reduce ? { opacity: 1 } : { y: 0 }} exit={reduce ? { opacity: 0 } : { y: "100%" }}
            transition={{ type: "tween", duration: 0.22 }}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="num text-s28">{title}</h2>
              <button onClick={onClose} className="min-h-[44px] min-w-[44px] rounded-full text-s20" aria-label="Close">✕</button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

// ---------- snackbar ----------
type Snack = { text: string; action?: { label: string; run: () => void } };
const SnackCtx = createContext<(s: Snack) => void>(() => {});
export const useSnack = () => useContext(SnackCtx);

// ---------- passcode session ----------
const AuthCtx = createContext<{ aryan: boolean; ask: () => Promise<boolean> }>({ aryan: false, ask: async () => false });
export const useAuth = () => useContext(AuthCtx);

export function Providers({ children }: { children: ReactNode }) {
  const [snack, setSnack] = useState<Snack | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const show = useCallback((s: Snack) => {
    setSnack(s);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setSnack(null), 5000);
  }, []);
  const [aryan, setAryan] = useState(false);
  const [asking, setAsking] = useState<((ok: boolean) => void) | null>(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<{ aryan: boolean }>("/auth/me").then((r) => setAryan(r.aryan)).catch(() => {}); }, []);
  const ask = useCallback(() => (aryan ? Promise.resolve(true) : new Promise<boolean>((res) => { setErr(null); setCode(""); setAsking(() => res); })), [aryan]);
  const submit = async () => {
    try {
      await api("/auth/passcode", { method: "POST", body: { passcode: code } });
      setAryan(true); asking?.(true); setAsking(null);
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <AuthCtx.Provider value={{ aryan, ask }}>
      <SnackCtx.Provider value={show}>
        {children}
        <Sheet open={!!asking} onClose={() => { asking?.(false); setAsking(null); }} title="Enter passcode">
          <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-3">
            <p className="text-s14 text-slate">Visitors can look around. Changing anything needs Aryan&apos;s passcode.</p>
            <input type="password" autoFocus value={code} onChange={(e) => setCode(e.target.value)} aria-label="Passcode"
              className="min-h-[44px] w-full rounded-input border border-fg/10 bg-surface px-3 text-s16" />
            {err && <ErrorNote>{err}</ErrorNote>}
            <Button type="submit" disabled={!code} className="w-full">Unlock</Button>
          </form>
        </Sheet>
        <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex justify-center px-4 md:bottom-6">
          {snack && (
            <div className="pointer-events-auto flex items-center gap-4 rounded-sheet bg-pavilion px-4 py-3 text-s14 text-sightscreen shadow-lg">
              <span>{snack.text}</span>
              {snack.action && <button className="min-h-[44px] font-semibold text-floodlight" onClick={() => { snack.action!.run(); setSnack(null); }}>{snack.action.label}</button>}
            </div>
          )}
        </div>
      </SnackCtx.Provider>
    </AuthCtx.Provider>
  );
}
