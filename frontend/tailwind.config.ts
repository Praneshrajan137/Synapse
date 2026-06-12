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
          overlay: "rgb(var(--syn-overlay) / <alpha-value>)",
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
        // Honesty states (Chromatic v1.1.0, ADR-044). Full oklch() vars —
        // no <alpha-value> support; tint via color-mix() in component CSS.
        state: {
          degraded: "var(--syn-state-degraded)",
          synthetic: "var(--syn-state-synthetic)",
        },
        accent: "rgb(var(--syn-accent) / <alpha-value>)",
        brand: "rgb(var(--syn-brand) / <alpha-value>)",
      },
      fontFamily: {
        // Self-hosted faces (ADR-045; see public/fonts/FONTS.md). Family
        // names must match the @font-face declarations in styles/fonts.css.
        display: ['"Space Grotesk"', '"Inter Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ['"Inter Variable"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
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
        // Display scale (ADR-045) — Space Grotesk territory: page titles,
        // hero numerals. Tight leading + negative tracking per size.
        "display-sm": ["1.375rem", { lineHeight: "1.25", letterSpacing: "-0.01em" }],
        "display-md": ["1.75rem", { lineHeight: "1.15", letterSpacing: "-0.015em" }],
        "display-lg": ["2.25rem", { lineHeight: "1.05", letterSpacing: "-0.02em" }],
        "display-xl": ["3rem", { lineHeight: "1.02", letterSpacing: "-0.022em" }],
        "display-2xl": ["3.75rem", { lineHeight: "1", letterSpacing: "-0.025em" }],
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
        arrive: "var(--syn-motion-arrive)",
        urgent: "var(--syn-motion-urgent)",
      },
      transitionTimingFunction: {
        standard: "var(--syn-ease-standard)",
        emphasized: "var(--syn-ease-emphasized)",
        entrance: "var(--syn-ease-entrance)",
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
        // The Cortex Pulse: a calm systolic breath. Drives the ambient ring;
        // duration is bound to the live decision cadence at runtime, falling
        // back to --syn-motion-breath. Honoured only when motion is allowed.
        "breathe": {
          "0%, 100%": { transform: "scale(1)", opacity: "0.85" },
          "50%": { transform: "scale(1.05)", opacity: "1" },
        },
        // Motion-as-cognition (ADR-044 Phase 5). arrive: a new fact enters
        // the stage with a hard-decelerate settle — causality, not flourish.
        "arrive": {
          "0%": { opacity: "0", transform: "translateY(-4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // demo-pulse: the synthetic ring breathes at the ambient cadence so
        // traffic-generator rows read as "alive but staged".
        "demo-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "pulse-confidence": "pulse-confidence 1.8s ease-in-out infinite",
        "shimmer": "shimmer 1.4s linear infinite",
        "fade-in": "fade-in var(--syn-motion-fast) var(--syn-ease-standard)",
        "breathe": "breathe var(--syn-motion-breath) ease-in-out infinite",
        "arrive": "arrive var(--syn-motion-arrive) var(--syn-ease-entrance)",
        "demo-pulse": "demo-pulse var(--syn-motion-breath) ease-in-out infinite",
        // urgency = frequency: the escalation pulse beats at exactly half
        // the ambient breath (1200ms vs 2400ms) — never a new colour.
        "urgent-pulse": "pulse-confidence var(--syn-motion-urgent) ease-in-out infinite",
      },
      backgroundImage: {
        "gradient-confidence": "var(--gradient-confidence)",
      },
    },
  },
  plugins: [],
} satisfies Config;
