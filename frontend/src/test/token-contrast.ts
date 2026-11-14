/**
 * WCAG 2.1 contrast of SYNAPSE colour tokens, read from `src/styles/tokens.css` (finding 134).
 *
 * A test oracle, kept apart from the shipped colour code on purpose. It parses the token file
 * the browser loads, paints a translucent background over a surface the way a browser does,
 * and computes the WCAG 2.1 ratio axe-core judges. Only `R G B` channel tokens are read. A
 * theme rule that does not declare a token inherits the dark rule's value, as the cascade
 * does: `:root` carries the dark rule.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export type TokenTheme = "dark" | "light" | "hc";

export const TOKEN_THEMES: readonly TokenTheme[] = ["dark", "light", "hc"];

/** The page surfaces a component can sit on. */
export const PAGE_SURFACES: readonly string[] = ["canvas", "surface", "surface-raised"];

/** axe-core 4.11 passes normal-size text only when its ratio is strictly above this. */
export const WCAG_AA_NORMAL_TEXT = 4.5;

export type Rgb = readonly [number, number, number];

/** A colour token a Tailwind utility names, and the alpha its `/NN` modifier applies. */
export interface TokenUse {
  readonly name: string;
  readonly alpha: number;
}

const TOKENS_CSS = join(dirname(fileURLToPath(import.meta.url)), "..", "styles", "tokens.css");

const THEME_SELECTOR: Readonly<Record<TokenTheme, string>> = {
  dark: '[data-theme="dark"]',
  light: '[data-theme="light"]',
  hc: '[data-theme="hc"]',
};

const CHANNELS = /^(\d+) (\d+) (\d+)$/;

/** The custom properties the first top-level rule for `selector` declares. */
function declarations(css: string, selector: string): Map<string, string> {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`tokens.css has no rule "${selector} {"`);
  const end = css.indexOf("\n}", start);
  if (end < 0) throw new Error(`tokens.css never closes the rule "${selector}"`);
  const block = css.slice(start, end);
  const pattern = /(--syn-[a-z0-9-]+):\s*([^;]+);/g;
  const found = new Map<string, string>();
  let match = pattern.exec(block);
  while (match !== null) {
    const [, name, value] = match;
    if (name !== undefined && value !== undefined) found.set(name, value.trim());
    match = pattern.exec(block);
  }
  return found;
}

let cache: Readonly<Record<TokenTheme, ReadonlyMap<string, string>>> | undefined;

/** Every theme's custom properties, the dark rule's filling what a theme leaves undeclared. */
function themes(): Readonly<Record<TokenTheme, ReadonlyMap<string, string>>> {
  if (cache === undefined) {
    const css = readFileSync(TOKENS_CSS, "utf8");
    const dark = declarations(css, THEME_SELECTOR.dark);
    cache = {
      dark,
      light: new Map([...dark, ...declarations(css, THEME_SELECTOR.light)]),
      hc: new Map([...dark, ...declarations(css, THEME_SELECTOR.hc)]),
    };
  }
  return cache;
}

/** Whether `--syn-<name>` is an `R G B` channel token, so a Tailwind colour utility can name it. */
export function isChannelToken(name: string): boolean {
  return CHANNELS.test(themes().dark.get(`--syn-${name}`) ?? "");
}

/** `--syn-<name>` in `theme`, as 8-bit sRGB. */
export function tokenRgb(theme: TokenTheme, name: string): Rgb {
  const value = themes()[theme].get(`--syn-${name}`);
  const match = value === undefined ? null : CHANNELS.exec(value);
  if (match === null) {
    throw new Error(
      `--syn-${name} is not an "R G B" token in the ${theme} theme: ${String(value)}`,
    );
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** `top` at `alpha` painted over the opaque `bottom` (source-over), rounded to 8 bits. */
export function over(top: Rgb, alpha: number, bottom: Rgb): Rgb {
  const channel = (index: 0 | 1 | 2): number =>
    Math.round(alpha * top[index] + (1 - alpha) * bottom[index]);
  return [channel(0), channel(1), channel(2)];
}

function linear(channel: number): number {
  const encoded = channel / 255;
  return encoded <= 0.04045 ? encoded / 12.92 : ((encoded + 0.055) / 1.055) ** 2.4;
}

/** WCAG 2.1 relative luminance. */
export function luminance([red, green, blue]: Rgb): number {
  return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
}

/** The WCAG 2.1 contrast ratio of two opaque colours. */
export function contrast(first: Rgb, second: Rgb): number {
  const a = luminance(first);
  const b = luminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

/** The colour token the first `bg-*` or `text-*` utility in `classes` names, if any does. */
export function tokenIn(classes: string, prefix: "bg" | "text"): TokenUse | undefined {
  const utility = new RegExp(`^${prefix}-([a-z0-9-]+)(?:/(\\d+))?$`);
  for (const cls of classes.split(/\s+/)) {
    const match = utility.exec(cls);
    const name = match?.[1];
    if (name !== undefined && isChannelToken(name)) {
      const percent = match?.[2];
      return { name, alpha: percent === undefined ? 1 : Number(percent) / 100 };
    }
  }
  return undefined;
}
