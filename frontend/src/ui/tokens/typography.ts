/**
 * Synaptic Calm — typography tokens (JS mirror of the @theme type scale).
 */

export const fontFamily = {
  display: '"Geist", "Inter Display", system-ui, sans-serif',
  ui: '"Inter Variable", "Inter", system-ui, sans-serif',
  mono: '"Geist Mono", "JetBrains Mono", ui-monospace, monospace',
} as const;

/** Modular scale, ratio 1.2. Values in rem. */
export const fontSize = {
  "2xs": "0.75rem",
  xs: "0.875rem",
  sm: "1rem",
  base: "1.1875rem",
  lg: "1.4375rem",
  xl: "1.75rem",
  "2xl": "2.0625rem",
  "3xl": "2.5rem",
  "4xl": "3rem",
  "5xl": "3.625rem",
} as const;

export type FontSizeKey = keyof typeof fontSize;

export const fontWeight = {
  regular: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const;

export const lineHeight = {
  tight: 1.2,
  normal: 1.5,
  relaxed: 1.65,
} as const;
