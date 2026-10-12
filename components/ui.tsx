"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { colourOf, flagOf } from "@/lib/teams";

// ---------- formatting ----------
export const pts = (x: number | null | undefined, d = 1) => (x == null ? "–" : (Math.round(x * 10 ** d) / 10 ** d).toString());
export function localTime(iso: string | null) {
  if (!iso) return "Time not announced";
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
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
type BtnKind = "primary" | "quiet" | "ghost";
export function Button({ kind = "primary", className = "", ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: BtnKind }) {
  const k = kind === "primary" ? "bg-red text-white shadow-[0_10px_30px_rgba(232,23,44,0.35)] disabled:bg-surface2 disabled:text-muted disabled:shadow-none"
    : kind === "quiet" ? "bg-surface2 text-ink hover:bg-[#272B3C]" : "text-ink underline-offset-4 hover:underline";
  return <button {...p} className={`min-h-[48px] rounded-full px-6 text-s16 font-semibold transition disabled:cursor-not-allowed ${k} ${className}`} />;
}

export type Tone = "red" | "green" | "amber" | "orange" | "muted" | "glass" | "gold";
export function Chip({ tone = "glass", children, className = "" }: { tone?: Tone; children: ReactNode; className?: string }) {
  const t = { red: "bg-red text-white", green: "bg-green/15 text-green", amber: "bg-amber/15 text-amber", orange: "bg-orange/15 text-orange",
    muted: "bg-surface2 text-muted", glass: "glass text-ink", gold: "bg-gold/15 text-gold" }[tone];
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-3 py-1 text-s12 font-semibold ${t} ${className}`}>{children}</span>;
}

export function PillTabs<T extends string>({ tabs, value, onChange, label }: { tabs: { key: T; label: string }[]; value: T; onChange: (k: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="no-scrollbar flex gap-2 overflow-x-auto">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={value === t.key} onClick={() => onChange(t.key)}
          className={`min-h-[44px] shrink-0 rounded-full px-5 text-s14 font-semibold transition ${value === t.key ? "bg-ink text-bg" : "bg-surface2 text-muted hover:text-ink"}`}>{t.label}</button>
      ))}
    </div>
  );
}

export function Card({ children, className = "", ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div {...p} className={`rounded-card bg-surface shadow-card ${className}`}>{children}</div>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`shimmer rounded-input ${className}`} />;
}

export function Warning({ children }: { children: ReactNode }) {
  return (
    <div role="note" className="flex gap-3 rounded-tile border border-amber/30 bg-amber/10 p-4 text-s14 text-ink">
      <AlertTriangle aria-hidden size={20} strokeWidth={1.75} className="mt-0.5 shrink-0 text-amber" /><div>{children}</div>
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div role="alert" className="rounded-tile border border-red/40 bg-red/10 p-4 text-s14 text-ink">{children}</div>;
}

/** Country flag in a circle, or a monogram on the team colour for franchises (never official logos). */
export function TeamBadge({ name, code, colour, size = 56 }: { name?: string | null; code?: string | null; colour?: string | null; size?: number }) {
  const flag = flagOf(name);
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full ring-2 ring-white/20"
      style={{ width: size, height: size, background: `radial-gradient(circle at 30% 25%, ${colourOf(colour)}, #0A0B10 130%)` }}>
      {flag ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={flag} alt={`${name} flag`} width={size} height={size} className="h-full w-full object-cover" />
      ) : <span className="num font-bold text-white" style={{ fontSize: size * 0.3 }}>{code ?? "?"}</span>}
    </span>
  );
}

export function PlayerAvatar({ name, url, colour, size = 56, badge }: { name: string; url: string | null; colour: string | null; size?: number; badge?: "C" | "VC" }) {
  const [broken, setBroken] = useState(false);
  const c = colourOf(colour);
  const ringColour = badge === "C" ? "#F5B700" : badge === "VC" ? "#D6DCE6" : c;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <div className="h-full w-full overflow-hidden rounded-full"
        style={{ boxShadow: `0 0 0 2px ${ringColour}, 0 0 18px ${ringColour}66`, background: `linear-gradient(145deg, ${c}, #15171F)` }}>
        {url && !broken ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={name} width={size} height={size} loading="lazy" onError={() => setBroken(true)} className="h-full w-full object-cover" />
        ) : (
          <div aria-label={name} role="img" className="num flex h-full w-full items-center justify-center font-bold text-white" style={{ fontSize: size * 0.36 }}>{initials(name)}</div>
        )}
      </div>
      {badge && (
        <span className={`num absolute -right-1.5 -top-1.5 flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-s12 font-extrabold text-bg shadow-card ${badge === "C" ? "bg-gold" : "bg-silver"}`}
          aria-label={badge === "C" ? "Captain" : "Vice-captain"}>{badge}</span>
      )}
    </div>
  );
}

// ---------- glass bottom sheet ----------
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
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
        <div className="fixed inset-0 z-50 flex items-end justify-center">
          <motion.div className="absolute inset-0 bg-black/60" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div ref={ref} tabIndex={-1} role="dialog" aria-modal aria-label={title}
            className="relative max-h-[92vh] w-full max-w-[440px] overflow-y-auto rounded-t-sheet border-x border-t border-white/10 bg-[#13151D]/95 px-5 pb-10 pt-3 outline-none backdrop-blur-xl"
            initial={reduce ? { opacity: 0 } : { y: "100%" }} animate={reduce ? { opacity: 1 } : { y: 0 }} exit={reduce ? { opacity: 0 } : { y: "100%" }}
            transition={reduce ? { duration: 0.15 } : { type: "spring", damping: 30, stiffness: 300 }}>
            <div aria-hidden className="mx-auto mb-4 h-1.5 w-12 rounded-full bg-white/20" />
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="num text-s20 font-bold">{title}</h2>
              <button onClick={onClose} className="flex h-11 w-11 items-center justify-center rounded-full bg-surface2 text-muted" aria-label="Close">✕</button>
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

// ---------- passcode session (only when the server has a passcode set) ----------
const AuthCtx = createContext<{ aryan: boolean; ask: () => Promise<boolean> }>({ aryan: true, ask: async () => true });
export const useAuth = () => useContext(AuthCtx);

export function Providers({ children }: { children: ReactNode }) {
  const [snack, setSnack] = useState<Snack | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const show = useCallback((s: Snack) => {
    setSnack(s);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setSnack(null), 5000);
  }, []);
  const [aryan, setAryan] = useState(true);
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
            <p className="text-s14 text-muted">Changing anything needs the passcode.</p>
            <input type="password" autoFocus value={code} onChange={(e) => setCode(e.target.value)} aria-label="Passcode"
              className="min-h-[48px] w-full rounded-input bg-surface2 px-4 text-s16 text-ink" />
            {err && <ErrorNote>{err}</ErrorNote>}
            <Button type="submit" disabled={!code} className="w-full">Unlock</Button>
          </form>
        </Sheet>
        <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-28 z-[60] flex justify-center px-5">
          {snack && (
            <div className="glass pointer-events-auto flex max-w-[400px] items-center gap-4 rounded-full px-5 py-3 text-s14 text-ink shadow-card">
              <span>{snack.text}</span>
              {snack.action && <button className="min-h-[44px] font-bold text-orange" onClick={() => { snack.action!.run(); setSnack(null); }}>{snack.action.label}</button>}
            </div>
          )}
        </div>
      </SnackCtx.Provider>
    </AuthCtx.Provider>
  );
}
