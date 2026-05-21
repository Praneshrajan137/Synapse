import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";
import forms from "@tailwindcss/forms";
import typography from "@tailwindcss/typography";

// SYNAPSE Atlas Console — design system surface.
// Tokens live in src/shared/design-tokens/tokens.css as CSS custom properties.
// Tailwind here only references them; never hard-code colour values.
//
// Theming: [data-theme="light"|"dark"] on <html>. `darkMode` strategy is
// "selector" so a class-driven story in Storybook can override per-component.
//
// Safety-critical palette (`safety-*`) MUST clear AAA contrast (7:1) on the
// surface where it appears. See plan §12 and ADR-028.

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx,js,jsx,mdx}",
    "./.storybook/**/*.{ts,tsx,mdx}",
  ],
  theme: {
    container: {
      center: true,
      padding: { DEFAULT: "1rem", lg: "2rem" },
      screens: { "2xl": "1440px" },
    },
    extend: {
      colors: {
        // Foundational surface palette — drawn from CSS variables so the same
        // class flips between light + dark via [data-theme]. The `<alpha-value>`
        // sentinel lets Tailwind compose opacity utilities (`bg-bg/70`).
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        fg: "rgb(var(--color-fg) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        "muted-fg": "rgb(var(--color-muted-fg) / <alpha-value>)",
        card: "rgb(var(--color-card) / <alpha-value>)",
        "card-fg": "rgb(var(--color-card-fg) / <alpha-value>)",
        border: "rgb(var(--color-border) / <alpha-value>)",
        ring: "rgb(var(--color-ring) / <alpha-value>)",

        // Brand
        primary: {
          DEFAULT: "rgb(var(--color-primary) / <alpha-value>)",
          fg: "rgb(var(--color-primary-fg) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--color-accent) / <alpha-value>)",
          fg: "rgb(var(--color-accent-fg) / <alpha-value>)",
        },

        // Decision-tier semantics (I-8). Each tier has its own colour;
        // never re-purpose for status. Tier 4 is reserved for crisis.
        tier: {
          1: "rgb(var(--color-tier-1) / <alpha-value>)", // <100ms RL-only — green
          2: "rgb(var(--color-tier-2) / <alpha-value>)", // <500ms phi3:mini — blue
          3: "rgb(var(--color-tier-3) / <alpha-value>)", // 2-15s deepseek-r1 — amber
          4: "rgb(var(--color-tier-4) / <alpha-value>)", // 15-120s llama3.3 70b — red
        },

        // AAA-CONTRAST safety palette. Used only on:
        //   - pricing-cap badges (I-6 essential ≤ 1.3x)
        //   - freshness ≤ 6h pins (Freshness Guardian)
        //   - disruption tier-4 banner (Disruption Shield)
        // Storybook a11y AAA stories enforce 7:1 against bg/fg.
        safety: {
          ok: "rgb(var(--color-safety-ok) / <alpha-value>)",
          warn: "rgb(var(--color-safety-warn) / <alpha-value>)",
          alert: "rgb(var(--color-safety-alert) / <alpha-value>)",
          critical: "rgb(var(--color-safety-critical) / <alpha-value>)",
        },

        // Confidence gauge tri-state (kept compatible with the existing
        // ConfidenceGauge.jsx component until S3 rebuild).
        confidence: {
          high: "rgb(var(--color-confidence-high) / <alpha-value>)",
          mid: "rgb(var(--color-confidence-mid) / <alpha-value>)",
          low: "rgb(var(--color-confidence-low) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["InterVariable", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Step ratio 1.125 (minor third) — quiet, dense, ops-friendly.
        "ops-xs": ["0.75rem", { lineHeight: "1rem" }],
        "ops-sm": ["0.84375rem", { lineHeight: "1.125rem" }],
        "ops-base": ["0.9375rem", { lineHeight: "1.375rem" }],
        "ops-lg": ["1.0625rem", { lineHeight: "1.5rem" }],
        "ops-xl": ["1.1875rem", { lineHeight: "1.625rem" }],
      },
      borderRadius: {
        sm: "calc(var(--radius) - 4px)",
        md: "calc(var(--radius) - 2px)",
        lg: "var(--radius)",
        xl: "calc(var(--radius) + 4px)",
      },
      keyframes: {
        // Respect prefers-reduced-motion — these are gated in tokens.css.
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "fade-in": "fade-in 120ms ease-out",
        "pulse-slow": "pulse 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [animate, forms({ strategy: "class" }), typography],
};

export default config;
