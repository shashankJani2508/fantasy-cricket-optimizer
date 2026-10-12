// Thin client for the Python API (CLAUDE.md section 11). Errors carry the server's plain-English message.
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const init: RequestInit = { method: opts.method ?? "GET", credentials: "same-origin" };
  if (opts.form) init.body = opts.form;
  else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    init.headers = { "Content-Type": "application/json" };
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, "No connection. Check your internet and try again.");
  }
  if (!res.ok) {
    let msg = `The server answered ${res.status}.`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = "Some values are not valid: " + j.detail.map((d: any) => d.msg).join("; ");
    } catch { /* keep default */ }
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

export type Team = { id: string; name: string; code: string; colour: string | null } | null;
export type Match = {
  id: string; format: string; format_group: string; series: string | null; start_time: string | null;
  status: string; xi_announced: boolean; team_a: Team; team_b: Team; venue: string | null; city: string | null;
};
export type Role = "WK" | "BAT" | "AR" | "BOWL";
export type Rules = {
  players: number; credit_budget: number; max_per_side: number;
  role_limits: Record<Role, { min: number; max: number }>; captain_multiplier: number; vc_multiplier: number;
};
export type Player = {
  player_id: string; name: string; team: string; team_code: string; colour: string | null; role: Role; credits: number;
  image_url: string | null; base: number | null; expected: number | null; change_pct: number | null;
  factors: Record<string, number> | null; trust: Record<string, number> | null; thin: boolean | null;
  fallback_step: number | null; fallback_note: string | null;
  adjustment: { applied_pct: number; requested_pct: number; clipped: boolean; reason: string; source_url: string | null } | null;
  explanations: Partial<Record<"player" | "captain" | "vice_captain" | "bench", { text: string; generic: boolean }>>;
};
export type PickedTeam = { player_ids: string[]; captain_id: string; vc_id: string; total_expected: number; total_actual: number | null; credits_used: number };
export type BenchRow = { player_id: string; rank: number; reason_code: string; reason_detail: string; points_cost: number | null };
export type RunStatus = {
  run_id: string; match_id: string; status: string; failed_step: string | null; error_message: string | null;
  warnings: string[]; run_type: string; data_stale: boolean; steps: { key: string; label: string }[];
};
export type RunView = RunStatus & {
  match: Match; players: Record<string, Player>; teams: Partial<Record<"system" | "aryan_final" | "simple" | "perfect", PickedTeam>>;
  bench: BenchRow[]; factors: string[]; pool: string[]; pool_type: Record<string, string>; rules: Rules;
};
