import type { Config } from "tailwindcss";

// SYNAPSE design tokens — colors track decision tiers and confidence ramps
// defined in tier_router.py and I-5. CSS variables (in src/styles/tokens.css)
// are the canonical values; Tailwind references them so dark/light/HC themes
// only need to swap a single token layer.

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,mdx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--syn-canvas) / <alpha-value>)",
        surface: {
          DEFAULT: "rgb(var(--syn-surface) / <alpha-value>)",
          raised: "rgb(var(--syn-surface-raised) / <alpha-value>)",
          sunken: "rgb(var(--syn-surface-sunken) / <alpha-value>)",
        },
        ink: {
          DEFAULT: "rgb(var(--syn-ink) / <alpha-value>)",
          muted: "rgb(var(--syn-ink-muted) / <alpha-value>)",
          subtle: "rgb(var(--syn-ink-subtle) / <alpha-value>)",
          inverse: "rgb(var(--syn-ink-inverse) / <alpha-value>)",
        },
        border: {
          DEFAULT: "rgb(var(--syn-border) / <alpha-value>)",
          strong: "rgb(var(--syn-border-strong) / <alpha-value>)",
        },
        // Per-tier palette (matches tier_router.py: 1=fast, 4=monte-carlo).
        tier: {
          1: "rgb(var(--syn-tier-1) / <alpha-value>)",
          2: "rgb(var(--syn-tier-2) / <alpha-value>)",
          3: "rgb(var(--syn-tier-3) / <alpha-value>)",
          4: "rgb(var(--syn-tier-4) / <alpha-value>)",
        },
        // Confidence ramp (I-5): >=0.9 ok, 0.7-0.9 warn, <0.7 risk.
        confidence: {
          ok: "rgb(var(--syn-confidence-ok) / <alpha-value>)",
          warn: "rgb(var(--syn-confidence-warn) / <alpha-value>)",
          risk: "rgb(var(--syn-confidence-risk) / <alpha-value>)",
        },
        // Semantic signal palette.
        signal: {
          info: "rgb(var(--syn-signal-info) / <alpha-value>)",
          success: "rgb(var(--syn-signal-success) / <alpha-value>)",
          warning: "rgb(var(--syn-signal-warning) / <alpha-value>)",
          danger: "rgb(var(--syn-signal-danger) / <alpha-value>)",
        },
        accent: "rgb(var(--syn-accent) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "InterVariable", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrainsMono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
        xs: ["0.75rem", { lineHeight: "1.125rem" }],
        sm: ["0.875rem", { lineHeight: "1.25rem" }],
        base: ["1rem", { lineHeight: "1.5rem" }],
        lg: ["1.125rem", { lineHeight: "1.625rem" }],
        xl: ["1.25rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem", { lineHeight: "2rem" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem" }],
        "4xl": ["2.25rem", { lineHeight: "2.5rem" }],
        "5xl": ["3rem", { lineHeight: "1.05" }],
      },
      borderRadius: {
        xs: "var(--syn-radius-xs)",
        sm: "var(--syn-radius-sm)",
        md: "var(--syn-radius-md)",
        lg: "var(--syn-radius-lg)",
        xl: "var(--syn-radius-xl)",
      },
      boxShadow: {
        e0: "var(--syn-elev-0)",
        e1: "var(--syn-elev-1)",
        e2: "var(--syn-elev-2)",
        e3: "var(--syn-elev-3)",
        e4: "var(--syn-elev-4)",
        focus: "var(--syn-focus-ring)",
      },
      transitionDuration: {
        instant: "var(--syn-motion-instant)",
        fast: "var(--syn-motion-fast)",
        medium: "var(--syn-motion-medium)",
        slow: "var(--syn-motion-slow)",
      },
      transitionTimingFunction: {
        standard: "var(--syn-ease-standard)",
        emphasized: "var(--syn-ease-emphasized)",
      },
      keyframes: {
        "pulse-confidence": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-confidence": "pulse-confidence 1.8s ease-in-out infinite",
        "shimmer": "shimmer 1.4s linear infinite",
        "fade-in": "fade-in var(--syn-motion-fast) var(--syn-ease-standard)",
      },
    },
  },
  plugins: [],
} satisfies Config;
