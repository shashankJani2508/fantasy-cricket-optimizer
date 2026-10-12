import type { Config } from "tailwindcss";

// Tokens from docs/UI_REDESIGN.md section 2.
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0B10", surface: "#15171F", surface2: "#1F2230", ink: "#F5F6F8", muted: "#9AA0AE",
        red: "#E8172C", orange: "#FF7A1A", gold: "#F5B700", silver: "#D6DCE6", green: "#2BB673", amber: "#FFB020",
      },
      fontFamily: { display: ["var(--font-display)"], sans: ["var(--font-text)", "system-ui", "sans-serif"] },
      fontSize: { s12: "12px", s14: "14px", s16: "16px", s20: "20px", s26: "26px", s34: "34px" },
      borderRadius: { card: "28px", sheet: "32px", tile: "20px", input: "14px" },
      boxShadow: { card: "0 20px 40px rgba(0,0,0,0.45)" },
    },
  },
  plugins: [],
} satisfies Config;
