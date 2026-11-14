import * as fs from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { i18n } from "@i18n/index";
import { DemoTheater } from "@surfaces/demo-theater/DemoTheater";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { getI18n, initReactI18next } from "react-i18next";
import { afterEach, describe, expect, it } from "vitest";
import demoTheaterCatalog from "../en/demo-theater.json";

// FE-INV-013 (atlas-console-elevation Req 8.1 and 15.6; the CLAUDE.md "English-only UI" rule):
// the UI ships in English only, from one `en` catalog, with no language detector and no language
// switcher. Every assertion reads the i18next instance src/i18n/index.ts initialises (main.tsx
// imports that module), the catalog tree it is built from, or a surface rendered through it.
// Nothing is mocked.
//
// Not asserted, because it is false today: that ALL user-visible copy threads through the catalog.
// FE-INV-013's registry description names the literals. The Demo Theater tests assert only the
// copy that goes through t(), and name it.

/** src/, two levels up from this file (Vitest serves a test file from its file: URL). */
const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

/** src/test/ holds the Vitest set-up and the MSW handlers; none of it ships. */
const TEST_HARNESS_DIR = join(SRC_DIR, "test");

const SCRIPT_FILE = /\.[jt]sx?$/;
const NOT_SHIPPED = /\.(?:test|spec|stories)\.[jt]sx?$/;

/** Every module under `dir` that ships: tests, stories and the test harness are left out. */
function shippedModules(dir: string): string[] {
  const found: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "__tests__" && file !== TEST_HARNESS_DIR) {
        found.push(...shippedModules(file));
      }
    } else if (SCRIPT_FILE.test(entry.name) && !NOT_SHIPPED.test(entry.name)) {
      found.push(file);
    }
  }
  return found;
}

/** A path under src/, spelled with forward slashes on every platform. */
function fromSrc(file: string): string {
  return relative(SRC_DIR, file).split(sep).join("/");
}

/** True when a module's source names i18next's changeLanguage. */
function callsChangeLanguage(file: string): boolean {
  return /\bchangeLanguage\b/.test(fs.readFileSync(file, "utf8"));
}

/**
 * A key of the glob below, as a path under src/i18n/. Vite 5.4.21 spells a relative glob's keys
 * relative to the importer, and leaves the importer out (transformGlobImport, read in
 * dist/node/chunks/dep-BK3b2jBa.js), so src/i18n/en/common.json is "../en/common.json" and a file
 * beside this one is "./name". Any other spelling is kept as it came, so the assertions show it.
 */
function underI18n(key: string): string {
  if (key.startsWith("../")) return key.slice("../".length);
  if (key.startsWith("./")) return `__tests__/${key.slice("./".length)}`;
  return key;
}

/**
 * Every file under src/i18n/ as Vite's import.meta.glob resolves the tree, which is the resolver
 * the bundle reaches its catalogs through. The glob is lazy: no file is imported, only keys read.
 */
const I18N_TREE: readonly string[] = Object.keys(import.meta.glob("../**/*")).map(underI18n);

/** index.ts is the bootstrap and __tests__/ holds this suite; neither is a catalog. */
function isCatalogCandidate(file: string): boolean {
  return file !== "index.ts" && !file.startsWith("__tests__/");
}

const EN_CATALOG_FILE = /^en\/[^/]+\.json$/;

type DemoTheaterKey = keyof typeof demoTheaterCatalog;

/** The segment-label keys DemoTheater.tsx reads, in SEGMENTS order. */
const SEGMENT_LABEL_KEYS: readonly DemoTheaterKey[] = [
  "segments.living_map",
  "segments.ipl_signal",
  "segments.disruption",
  "segments.debate",
  "segments.evidence",
];

/** Mounts the Demo Theater in the one provider it needs: its artifact query runs on TanStack. */
function renderDemoTheater(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DemoTheater />
    </QueryClientProvider>,
  );
}

/** A segment button's text without the keyboard-shortcut digit it leads with. */
function withoutShortcut(text: string | null): string {
  return (text ?? "").replace(/^\d+/, "");
}

/**
 * Asserts that each piece of Demo Theater copy that goes through t() reads `copy(key)`: the page
 * header's title and subtitle, the run control, the five segment labels, the selected segment's
 * heading, and the evidence heading and the name of its region.
 */
function expectDemoTheaterCopy(copy: (key: DemoTheaterKey) => string): void {
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(copy("title"));
  expect(screen.getByText(copy("subtitle"))).toBeInTheDocument();
  expect(screen.getByRole("button", { name: copy("controls.run") })).toBeInTheDocument();
  const segmentButtons = within(screen.getByRole("list")).getAllByRole("button");
  const labels = segmentButtons.map((button) => withoutShortcut(button.textContent));
  expect(labels).toEqual(SEGMENT_LABEL_KEYS.map(copy));
  const subheadings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
  expect(subheadings).toEqual([copy("segments.living_map"), copy("evidence.header")]);
  const evidence = screen.getByRole("complementary", { name: copy("evidence.header") });
  expect(evidence).toBeInTheDocument();
}

describe("English-only i18n (FE-INV-013)", () => {
  // Wrong if index.ts initialised an instance other than the one react-i18next hands components,
  // or if a lookup could resolve in a language other than en.
  it("FE-INV-013: components translate through the instance src/i18n/index.ts initialises, and it resolves every lookup in `en`", () => {
    expect(i18n.isInitialized).toBe(true);
    expect(getI18n()).toBe(i18n);
    expect(i18n.language).toBe("en");
    expect(i18n.languages).toEqual(["en"]);
  });

  // Wrong if a second locale's resources were bundled, or a backend could fetch one at runtime.
  it("FE-INV-013: `en` is the only language the instance holds a catalog for, and no backend is registered to fetch another", () => {
    expect(Object.keys(i18n.store.data)).toEqual(["en"]);
    expect(i18n.modules.backend).toBeUndefined();
  });

  // Wrong if supportedLngs gained a language, or were dropped: i18next's default, false, accepts
  // every language.
  it("FE-INV-013: supportedLngs is the configured en plus the cimode i18next appends, and nothing else", () => {
    // src/i18n/index.ts configures supportedLngs: ["en"]. i18next 23.16.8 appends its built-in
    // "cimode" (t() returns the key) to any configured list, in transformOptions at
    // node_modules/i18next/dist/esm/i18next.js lines 1871-1872, the build Vitest loads through
    // the package's "import" export.
    expect(i18n.options.supportedLngs).toEqual(["en", "cimode"]);
  });

  // Wrong if a detector were registered with i18n.use(), or a third-party plugin that could set
  // the language when it initialises.
  it("FE-INV-013: no language detector is registered, and react-i18next's binding is the only plugin", () => {
    expect(i18n.modules.languageDetector).toBeUndefined();
    expect(i18n.services.languageDetector).toBeUndefined();
    expect(i18n.modules.external).toEqual([initReactI18next]);
  });

  // Wrong if src/i18n gained another locale's catalog (hi/, hi.json, a .ts catalog), or held an en
  // file the bootstrap does not load. The second assertion is also the non-vacuity check: the
  // instance holds ten namespaces, so a glob that matched nothing fails it.
  it("FE-INV-013: src/i18n holds no catalog but en/*.json, one file per namespace the instance holds", () => {
    const catalogs = I18N_TREE.filter(isCatalogCandidate);
    expect(catalogs.filter((file) => !EN_CATALOG_FILE.test(file))).toEqual([]);
    const namespaces = catalogs.map((file) => file.slice("en/".length, -".json".length));
    expect(namespaces.sort()).toEqual(Object.keys(i18n.store.data.en ?? {}).sort());
  });

  // Wrong if a shipped module called changeLanguage. A text scan: it cannot see a switch made
  // without that call (a second i18next instance, an I18nextProvider), and src/ holds neither.
  it("FE-INV-013: no shipped module under src calls changeLanguage, the call a language switcher makes", () => {
    const modules = shippedModules(SRC_DIR);
    // Non-vacuity: the walk reached the bootstrap the rest of this suite reads.
    expect(modules.map(fromSrc)).toContain("i18n/index.ts");
    expect(modules.filter(callsChangeLanguage).map(fromSrc)).toEqual([]);
  });
});

describe("Demo Theater copy (FE-INV-013)", () => {
  afterEach(async () => {
    // Unmount first, so no mounted component re-renders outside act() when the language changes.
    cleanup();
    await i18n.changeLanguage("en");
  });

  // Wrong if this copy came from another namespace or a key were missing from demo-theater.json:
  // the element would then show something other than that catalog's English.
  it("FE-INV-013: in English, the Demo Theater's header, run control, segment labels and evidence heading show the demo-theater catalog's copy", () => {
    renderDemoTheater();
    expectDemoTheaterCopy((key) => demoTheaterCatalog[key]);
  });

  // Wrong if any of that copy were written into DemoTheater.tsx: a literal equal to the catalog's
  // English passes the test above, but under cimode it still reads as English, not as its key.
  it("FE-INV-013: under i18next's cimode the same Demo Theater copy reads as its catalog keys, so it is looked up rather than written in", async () => {
    await i18n.changeLanguage("cimode");
    renderDemoTheater();
    expectDemoTheaterCopy((key) => key);
  });
});
