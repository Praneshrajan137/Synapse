import { buildSupplyGraph } from "@lib/supply-graph";
import { useEffect, useRef, useState } from "react";
import Sigma from "sigma";
import type { TopologyEdge, TopologyNode } from "./useTopology";

/**
 * SupplyNetworkGraph — the supply ontology rendered on the GPU via Sigma.js /
 * WebGL (SENSORIUM Phase 6b), replacing the three.js force graph.
 *
 * Sigma renders the graph on the GPU; graphology computes a ForceAtlas2 layout
 * and — the genuine upgrade — Louvain community detection, so the network's
 * natural zones emerge. MIT-licensed (within the repo's allowed-license rule);
 * the GPU-force-compute alternative (Cosmograph) is CC-BY-NC and disallowed.
 *
 * Accessibility: the WebGL canvas is opaque to assistive tech, so a role=img
 * label + a screen-reader summary carry the node/edge/zone counts
 * (INV-CLR-011 spirit — never a sole visual channel).
 */

interface SupplyNetworkGraphProps {
  readonly nodes: ReadonlyArray<TopologyNode>;
  readonly edges: ReadonlyArray<TopologyEdge>;
  readonly height?: number;
}

export function SupplyNetworkGraph({ nodes, edges, height = 420 }: SupplyNetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [summary, setSummary] = useState({ order: 0, size: 0, communities: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const { graph, communityCount } = buildSupplyGraph(nodes, edges);
    setSummary({ order: graph.order, size: graph.size, communities: communityCount });

    let renderer: Sigma | null = null;
    try {
      renderer = new Sigma(graph, el, {
        allowInvalidContainer: true,
        renderEdgeLabels: false,
        renderLabels: graph.order <= 60, // labels only on small graphs
        defaultEdgeType: "line",
        labelColor: { color: "rgb(148 163 184)" }, // chromatic-allow: WebGL label colour (INV-CLR-009)
        labelDensity: 0.4,
      });
    } catch {
      // WebGL unavailable (older GPU / headless) — the SR summary still informs.
    }

    return () => {
      renderer?.kill();
    };
  }, [nodes, edges]);

  const label = `Supply network: ${summary.order} nodes, ${summary.size} links, ${summary.communities} zones (WebGL).`;

  return (
    <div className="syn-card relative overflow-hidden" style={{ height }}>
      <div ref={containerRef} className="absolute inset-0" role="img" aria-label={label} />
      <div className="pointer-events-none absolute left-2 top-2 rounded bg-surface/70 px-2 py-1 text-2xs text-ink-muted backdrop-blur-sm">
        {summary.order} nodes · {summary.size} links · {summary.communities} zones
      </div>
      <ul className="sr-only">
        <li>{label}</li>
      </ul>
    </div>
  );
}
