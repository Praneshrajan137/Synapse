// Primary-Surface route registry (Req 8.2, FE-INV command-palette coverage).
//
// This is the single, named, testable source of truth for the Console's
// primary Surfaces — the top-level routes an operator navigates between. Three
// consumers derive from it so coverage stays mechanical rather than hand-kept:
//   1. The Shell primary nav (`Shell.tsx`) renders one link per surface.
//   2. The CommandPalette (`CommandPalette.tsx`) builds one keyboard-activatable
//      "Go to" command per surface, so every primary Surface is reachable
//      without a pointer.
//   3. Property test 17.3 (`Property 28`) asserts every entry here has a
//      palette command via `surfaceGoToCommands()`.
//
// Adding a primary Surface is one array entry — nav link and palette command
// (and the coverage guarantee) follow automatically. Detail/parameterized
// routes (e.g. /decisions/:id, /council/:id) are NOT primary Surfaces: they are
// reached from within a surface, not from the top-level registry.

import type { Role } from "@state/session.store";

/** Operator-loop grouping mirrored by the Shell nav and the palette. */
export type NavGroup = "Monitor" | "Intervene" | "Investigate" | "Configure";

export interface PrimarySurface {
  /** Stable id; the palette command is `go-${id}`. */
  readonly id: string;
  /** Router path (react-router). */
  readonly path: string;
  /** i18next key in the `common` namespace resolving the English label. */
  readonly labelKey: string;
  /** Operator-loop group for visual ordering. */
  readonly group: NavGroup;
  /** Minimum role the route is guarded by (mirrors router.tsx RouteGuard). */
  readonly minRole: Role;
  /** Extra fuzzy-search terms for the palette (optional). */
  readonly keywords?: string;
  /** react-router `end` flag for exact-match active styling (index route). */
  readonly end?: boolean;
}

/**
 * The canonical list of primary Surfaces, ordered by the operator's loop:
 * Monitor → Intervene → Investigate → Configure. Paths and roles mirror the
 * route registry in `router.tsx`.
 */
export const PRIMARY_SURFACES: readonly PrimarySurface[] = [
  {
    id: "mission-control",
    path: "/",
    labelKey: "surface.mission-control",
    group: "Monitor",
    minRole: "viewer",
    keywords: "cortex pulse home",
    end: true,
  },
  {
    id: "live-markets",
    path: "/markets",
    labelKey: "surface.live-markets",
    group: "Monitor",
    minRole: "viewer",
    keywords: "pricing freshness markdown shelf-life elasticity",
  },
  {
    id: "operations",
    path: "/operations",
    labelKey: "surface.operations",
    group: "Monitor",
    minRole: "viewer",
    keywords: "standing watch slo burn calibration outcomes",
  },
  {
    id: "override-cockpit",
    path: "/cockpit",
    labelKey: "surface.override-cockpit",
    group: "Intervene",
    minRole: "ops",
    keywords: "escalation hitl threshold override",
  },
  {
    id: "ingress",
    path: "/ingress",
    labelKey: "surface.ingress",
    group: "Intervene",
    minRole: "ops",
    keywords: "order submit trigger decision pipeline",
  },
  {
    id: "decision-theater",
    path: "/decisions",
    labelKey: "surface.decision-theater",
    group: "Investigate",
    minRole: "viewer",
    keywords: "tribunal pareto replay",
  },
  {
    id: "agent-council",
    path: "/agents",
    labelKey: "surface.agent-council",
    group: "Investigate",
    minRole: "engineer",
    keywords: "health latency",
  },
  {
    id: "twin-lab",
    path: "/twin",
    labelKey: "surface.twin-lab",
    group: "Investigate",
    minRole: "engineer",
    keywords: "projection divergence simulate monte carlo",
  },
  {
    id: "audit-vault",
    path: "/audit",
    labelKey: "surface.audit-vault",
    group: "Investigate",
    minRole: "viewer",
    keywords: "memory compliance hash chain",
  },
  {
    id: "steering",
    path: "/steering",
    labelKey: "surface.steering",
    group: "Configure",
    minRole: "ops",
    keywords: "weights pareto will threshold",
  },
  {
    id: "demo-theater",
    path: "/demo",
    labelKey: "surface.demo-theater",
    group: "Configure",
    minRole: "viewer",
    keywords: "scenario",
  },
] as const;

/**
 * A route→command mapping entry: pure metadata (no side effects). The palette
 * attaches the navigation `run` at render time; property test 17.3 consumes
 * this structure to assert every primary Surface is reachable by keyboard.
 */
export interface SurfaceGoToCommand {
  /** Palette command id, keyboard-activatable. */
  readonly id: string;
  /** The primary Surface's route path. */
  readonly path: string;
  /** i18next label key (common namespace). */
  readonly labelKey: string;
  /** Palette group label key (common namespace). */
  readonly groupKey: string;
  /** Fuzzy-search keywords. */
  readonly keywords?: string;
}

/**
 * Derive the palette's "Go to" command registry from {@link PRIMARY_SURFACES}.
 * Pure and deterministic so it is unit- and property-testable without React.
 * Because it is a total map over PRIMARY_SURFACES, every primary Surface is
 * guaranteed a keyboard-activatable command (Req 8.2, Property 28).
 */
export function surfaceGoToCommands(): readonly SurfaceGoToCommand[] {
  return PRIMARY_SURFACES.map((s) => ({
    id: `go-${s.id}`,
    path: s.path,
    labelKey: s.labelKey,
    groupKey: "command.group.go-to",
    ...(s.keywords ? { keywords: s.keywords } : {}),
  }));
}
