// Country flags (open-licence flag-icons set, copied to /public/flags) by team name; franchises get a monogram.
const FLAGS: Record<string, string> = {
  Pakistan: "pk", "Sri Lanka": "lk", India: "in", Australia: "au", England: "gb-eng", "New Zealand": "nz",
  "South Africa": "za", Bangladesh: "bd", Afghanistan: "af", Zimbabwe: "zw", Ireland: "ie", "United Arab Emirates": "ae",
  "United States of America": "us", Nepal: "np", Netherlands: "nl", Oman: "om", Namibia: "na", Scotland: "gb-sct",
  Canada: "ca", Kuwait: "kw", "Hong Kong": "hk",
};
export const flagOf = (name?: string | null) => (name && FLAGS[name] ? `/flags/${FLAGS[name]}.svg` : null);
export const NEUTRAL = "#3A3F52";
export const colourOf = (c?: string | null) => c ?? NEUTRAL;

/** Match art: diagonal blend of both team colours + floodlight glow (UI_REDESIGN.md section 2). */
export function matchArt(a?: string | null, b?: string | null) {
  const ca = colourOf(a), cb = colourOf(b);
  return {
    backgroundImage: [
      "radial-gradient(120% 70% at 50% -10%, rgba(255,255,255,0.28), transparent 55%)",
      "linear-gradient(to bottom, transparent 35%, rgba(10,11,16,0.92) 88%)",
      `linear-gradient(118deg, ${ca} 0%, ${ca}CC 38%, ${cb}CC 62%, ${cb} 100%)`,
    ].join(","),
  } as React.CSSProperties;
}
export const ring = (a?: string | null, b?: string | null) =>
  `conic-gradient(from 210deg, ${colourOf(a)}, ${colourOf(b)}, ${colourOf(a)})`;
