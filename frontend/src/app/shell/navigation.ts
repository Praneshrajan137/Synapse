import {
  Boxes,
  Drama,
  Gavel,
  History,
  type LucideIcon,
  Radar,
  ScanSearch,
  Waves,
} from "lucide-react";

/**
 * The seven surfaces of Synaptic Calm (plan section 4.1).
 *
 * Surfaces marked `construction` are rebuilt in later phases; until then
 * the shell renders a placeholder. `live` surfaces are wired to a
 * working route (a rebuilt surface, or a legacy page during migration).
 */

export type SurfaceStatus = "live" | "construction";

export interface Surface {
  readonly id: string;
  readonly label: string;
  readonly route: string;
  readonly description: string;
  readonly icon: LucideIcon;
  readonly phase: number;
  readonly status: SurfaceStatus;
  /** Single-key navigation hint shown in the command palette. */
  readonly hotkey: string;
}

export const SURFACES: readonly Surface[] = [
  {
    id: "bridge",
    label: "Bridge",
    route: "/",
    description: "Situational awareness — KPIs, live map, decision tape",
    icon: Radar,
    phase: 4,
    status: "live",
    hotkey: "B",
  },
  {
    id: "theater",
    label: "Theater",
    route: "/theater",
    description: "Live consensus deliberation as a cinematic process",
    icon: Drama,
    phase: 5,
    status: "construction",
    hotkey: "T",
  },
  {
    id: "council",
    label: "Council",
    route: "/council",
    description: "HITL override — single-decision interrogation surface",
    icon: Gavel,
    phase: 6,
    status: "live",
    hotkey: "C",
  },
  {
    id: "replay",
    label: "Replay",
    route: "/replay",
    description: "Decision time machine — scrub the audit log",
    icon: History,
    phase: 7,
    status: "live",
    hotkey: "R",
  },
  {
    id: "twin",
    label: "Twin",
    route: "/twin",
    description: "Digital twin, what-if Monte Carlo, supply network",
    icon: Boxes,
    phase: 8,
    status: "live",
    hotkey: "W",
  },
  {
    id: "inspector",
    label: "Inspector",
    route: "/inspector",
    description: "Per-agent deep dive — rewards, calibration, traffic",
    icon: ScanSearch,
    phase: 8,
    status: "live",
    hotkey: "I",
  },
  {
    id: "streams",
    label: "Streams",
    route: "/streams",
    description: "Kafka topic explorer — filter, replay, inspect schemas",
    icon: Waves,
    phase: 8,
    status: "construction",
    hotkey: "S",
  },
];

export function surfaceByRoute(route: string): Surface | undefined {
  return SURFACES.find((s) => s.route === route);
}
