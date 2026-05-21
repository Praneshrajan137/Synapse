/**
 * SYNAPSE Atlas Console — KPI hook.
 *
 * Tails `synapse.metrics.agent` over SSE, validates each frame against
 * `MetricsFrameSchema`, holds a 1-minute sliding window, and reduces
 * to the 5-tile `KPI` shape every render.
 *
 * Pure-function reducer + ref-held window means React renders are
 * stable when the input set is unchanged — the KPITicker memoisation
 * stays valid.
 */
import { useMemo, useRef } from "react";

import { useSse } from "@shared/realtime";

import { type KPI, MetricsFrameSchema, reduceKPI } from "../model/kpi";

const WINDOW_MS = 60_000;

export interface UseKpiResult {
  readonly kpi: KPI;
  readonly connected: boolean;
}

export function useKpi(): UseKpiResult {
  const window = useRef<{ ts: number; frame: import("../model/kpi").MetricsFrame }[]>([]);

  const { events, connected } = useSse("synapse.metrics.agent", {
    schema: MetricsFrameSchema,
    maxBuffer: 200,
  });

  // Append-only ring window; prune by wall-clock age so the reducer is bounded.
  const kpi = useMemo<KPI>(() => {
    const now = Date.now();
    for (const event of events.slice(window.current.length)) {
      window.current.push({ ts: now, frame: event });
    }
    while (window.current.length > 0 && now - window.current[0]!.ts > WINDOW_MS) {
      window.current.shift();
    }
    return reduceKPI(window.current.map((e) => e.frame));
  }, [events]);

  return { kpi, connected };
}
