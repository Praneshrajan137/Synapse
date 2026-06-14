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
 * Sprint 17: clicking a node is no longer a no-op — it selects the node and
 * raises `onSelectNode`, so Twin Lab can render an inspector pane; the selected
 * node is highlighted (larger, labelled) via a node reducer. Clicking the empty
 * stage clears the selection.
 *
 * Accessibility: the WebGL canvas is opaque to assistive tech, so a role=img
 * label + a screen-reader summary carry the node/edge/zone counts
 * (INV-CLR-011 spirit — never a sole visual channel).
 */

interface SupplyNetworkGraphProps {
  readonly nodes: ReadonlyArray<TopologyNode>;
  readonly edges: ReadonlyArray<TopologyEdge>;
  readonly height?: number;
  readonly selectedId?: string | null;
  readonly onSelectNode?: (id: string | null) => void;
}

export function SupplyNetworkGraph({
  nodes,
  edges,
  height = 420,
  selectedId = null,
  onSelectNode,
}: SupplyNetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<Sigma | null>(null);
  const [summary, setSummary] = useState({ order: 0, size: 0, communities: 0 });

  // Keep the latest selection + callback in refs so the Sigma renderer (created
  // once per nodes/edges change) reads current values without re-initialising.
  const selectedRef = useRef<string | null>(selectedId);
  selectedRef.current = selectedId;
  const onSelectRef = useRef(onSelectNode);
  onSelectRef.current = onSelectNode;

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
        // Highlight the selected node: larger, always-labelled, raised z-index.
        nodeReducer: (node, data) => {
          if (node === selectedRef.current) {
            return { ...data, size: (data.size ?? 4) * 1.8, forceLabel: true, zIndex: 1 };
          }
          return data;
        },
      });
      renderer.on("clickNode", ({ node }) => onSelectRef.current?.(node));
      renderer.on("clickStage", () => onSelectRef.current?.(null));
    } catch {
      // WebGL unavailable (older GPU / headless) — the SR summary still informs.
    }
    rendererRef.current = renderer;

    return () => {
      renderer?.kill();
      rendererRef.current = null;
    };
  }, [nodes, edges]);

  // Repaint when the selection changes so the reducer re-runs (the renderer is
  // not recreated — only refreshed). selectedId is the intentional trigger.
  // biome-ignore lint/correctness/useExhaustiveDependencies: selectedId drives the repaint via the nodeReducer ref, not the body
  useEffect(() => {
    rendererRef.current?.refresh();
  }, [selectedId]);

  const label = `Supply network: ${summary.order} nodes, ${summary.size} links, ${summary.communities} zones (WebGL). Click a node to inspect it.`;

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
