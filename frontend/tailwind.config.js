/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FAFAFA",
        surface: "#FFFFFF",
        ink: "#191A1C",
        muted: "#6B7280",
        faint: "#9CA3AF",
        line: "#ECECEC",
        accent: "#4F46E5",
        "accent-soft": "#EEF0FF",
        ok: "#16A34A",
        "ok-soft": "#ECFDF3",
        bad: "#DC2626",
        "bad-soft": "#FEF2F2",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)",
        pop: "0 8px 24px rgba(16,24,40,0.08)",
      },
      borderRadius: { xl2: "14px" },
      keyframes: {
        shimmer: { "0%": { opacity: "0.35" }, "50%": { opacity: "1" }, "100%": { opacity: "0.35" } },
      },
      animation: { shimmer: "shimmer 1.4s ease-in-out infinite" },
    },
  },
  plugins: [],
};
