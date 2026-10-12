import type { Config } from "tailwindcss";

// Colour tokens from docs/UI_UX.md section 2, as CSS variables (dark mode swaps sightscreen and pavilion).
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sightscreen: v("sightscreen"), pavilion: v("pavilion"), turf: v("turf"), ball: v("ball"),
        floodlight: v("floodlight"), clay: v("clay"), slate: v("slate"), surface: v("surface"),
      },
      fontFamily: { display: ["var(--font-display)"], sans: ["var(--font-text)", "system-ui", "sans-serif"] },
      fontSize: { "s12": "12px", "s14": "14px", "s16": "16px", "s20": "20px", "s28": "28px", "s40": "40px" },
      borderRadius: { card: "24px", sheet: "16px", input: "12px" },
    },
  },
  plugins: [],
} satisfies Config;
