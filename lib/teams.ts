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

/** "Meghalaya vs Manipur, Plate, Ranji Trophy Plate 2026-27" -> title "Meghalaya vs Manipur", stage "Plate · Ranji Trophy Plate 2026-27". */
export function splitSeries(series?: string | null) {
  const parts = (series ?? "").split(", ");
  return { title: parts[0] ?? "", stage: parts.slice(1).join(" · ") };
}
/** CricketData.org writes "TBC" (to be confirmed) when the venue isn't announced. */
export function venueText(venue?: string | null, city?: string | null) {
  const v = [venue, city].filter((x) => x && !/^tbc$/i.test(x.trim())).join(", ");
  return v && !/^tbc/i.test(v) ? v : "Venue not announced yet";
}

/** Domestic match inside one country: a silk-like painted flag (drawn in CSS, no photos). India for now. */
export function homeArt(country?: string | null) {
  if (country !== "India") return null;
  return {
    backgroundImage: [
      "linear-gradient(to bottom, transparent 40%, rgba(10,11,16,0.92) 90%)",
      "repeating-linear-gradient(115deg, rgba(255,255,255,0.10) 0 40px, rgba(0,0,0,0.12) 40px 90px, rgba(255,255,255,0.06) 90px 140px)",
      "linear-gradient(to bottom, #FF9933 0%, #F7A44A 30%, #FFFFFF 34%, #F4F4F4 63%, #138808 67%, #0F6E07 100%)",
    ].join(","),
  } as React.CSSProperties;
}
