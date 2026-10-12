// Client-side mirror of engine/gate.py for instant meters only; the server's /gate is authoritative.
import type { Role, Rules } from "./api";

export const ROLES: Role[] = ["WK", "BAT", "AR", "BOWL"];
export const ROLE_NAMES: Record<Role, string> = { WK: "wicket-keepers", BAT: "batters", AR: "all-rounders", BOWL: "bowlers" };
type P = { role: Role; credits: number; team: string; name: string };

const fmt = (x: number) => String(Math.round(x * 100) / 100);

export function check(ids: string[], cap: string | null, vc: string | null, players: Record<string, P>, rules: Rules) {
  const fails: string[] = [];
  const uniq = Array.from(new Set(ids));
  if (uniq.length !== ids.length) fails.push("The same player is in the team twice: remove the duplicate.");
  if (uniq.length < rules.players) fails.push(`You have ${uniq.length} players: add ${rules.players - uniq.length} more.`);
  if (uniq.length > rules.players) fails.push(`You have ${uniq.length} players: remove ${uniq.length - rules.players}.`);
  const used = uniq.reduce((s, p) => s + (players[p]?.credits ?? 0), 0);
  if (used > rules.credit_budget + 1e-9) fails.push(`${fmt(used - rules.credit_budget)} credits over: swap a player for a cheaper one.`);
  const roles = Object.fromEntries(ROLES.map((r) => [r, uniq.filter((p) => players[p]?.role === r).length])) as Record<Role, number>;
  for (const r of ROLES) {
    const lim = rules.role_limits[r];
    if (roles[r] < lim.min) fails.push(`Only ${roles[r]} ${ROLE_NAMES[r]}: the minimum is ${lim.min}.`);
    else if (roles[r] > lim.max) fails.push(`${roles[r]} ${ROLE_NAMES[r]}: the maximum is ${lim.max}.`);
  }
  const sides: Record<string, number> = {};
  uniq.forEach((p) => { const t = players[p]?.team ?? "?"; sides[t] = (sides[t] ?? 0) + 1; });
  for (const [t, n] of Object.entries(sides)) if (n > rules.max_per_side) fails.push(`${n} players from ${t}: the maximum is ${rules.max_per_side}.`);
  if (!cap || !uniq.includes(cap)) fails.push("Choose a captain from your 11.");
  if (!vc || !uniq.includes(vc)) fails.push("Choose a vice-captain from your 11.");
  if (cap && cap === vc) fails.push("Choose a different vice-captain.");
  return { passed: fails.length === 0, fails, used, roles, sides };
}
