import { describe, expect, it } from "vitest";
import { check } from "../../lib/gate";
import { flagOf, matchArt } from "../../lib/teams";

const rules = { players: 11, credit_budget: 100, max_per_side: 7, captain_multiplier: 2, vc_multiplier: 1.5,
  role_limits: { WK: { min: 1, max: 7 }, BAT: { min: 1, max: 7 }, AR: { min: 1, max: 7 }, BOWL: { min: 1, max: 7 } } };
const roles = ["WK", "BAT", "BAT", "BAT", "AR", "AR", "BOWL", "BOWL", "BOWL", "BOWL", "BAT"] as const;
const players = Object.fromEntries(roles.map((r, i) => [`p${i}`, { role: r, credits: 9, team: i < 6 ? "A" : "B", name: `P${i}` }]));
const ids = Object.keys(players);

describe("client gate mirror", () => {
  it("passes a valid team", () => expect(check(ids, "p0", "p1", players, rules).passed).toBe(true));
  it("flags credits over budget with the fix", () => {
    const rich = { ...players, p10: { ...players.p10, credits: 12 } };
    expect(check(ids, "p0", "p1", rich, rules).fails[0]).toBe("2 credits over: swap a player for a cheaper one.");
  });
  it("needs a captain and a different vice-captain", () => {
    expect(check(ids, "p0", "p0", players, rules).fails).toContain("Choose a different vice-captain.");
  });
});

describe("team art", () => {
  it("maps countries to open-licence flags and franchises to none", () => {
    expect(flagOf("Pakistan")).toBe("/flags/pk.svg");
    expect(flagOf("Trinbago Knight Riders")).toBeNull();
  });
  it("blends both team colours", () => expect(String(matchArt("#111111", "#222222").backgroundImage)).toContain("#222222"));
});
