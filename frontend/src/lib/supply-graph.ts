import type { TopologyEdge, TopologyNode } from "@surfaces/twin-lab/useTopology";
import Graph from "graphology";
import louvain from "graphology-communities-louvain";
import forceAtlas2 from "graphology-layout-forceatlas2";

/**
 * Supply-graph builder for the WebGL renderer (SENSORIUM Phase 6b).
 *
 * Pure transform: topology nodes/edges → a graphology Graph with deterministic
 * seed positions, a ForceAtlas2 layout, and Louvain community detection (the
 * supply network's natural zones — a genuine analytic upgrade over the old 3D
 * view). Sigma renders this graph on the GPU (WebGL); keeping the transform
 * separate makes it unit-testable without a WebGL context.
 *
 * Deterministic by construction (seed positions hashed from node id) so renders
 * are reproducible (FE-INV-009).
 *
 * Colours are literal rgb() strings because WebGL cannot resolve CSS custom
 * properties; they mirror the chromatic tokens (tracked for migration like the
 * deck.gl palette).
 */

// chromatic-allow: Sigma/WebGL consumes literal colour strings (INV-CLR-009).
export const NODE_TYPE_COLOR: Record<string, string> = {
  Warehouse: "rgb(56 189 248)", // chromatic-allow
  DarkStore: "rgb(34 197 94)", // chromatic-allow
  Supplier: "rgb(251 191 36)", // chromatic-allow
  Rider: "rgb(129 140 248)", // chromatic-allow
};
// chromatic-allow: fallback node colour (INV-CLR-009).
const NODE_FALLBACK_COLOR = "rgb(148 163 184)"; // chromatic-allow
// chromatic-allow: edge colour (INV-CLR-009).
const EDGE_COLOR = "rgba(148, 163, 184, 0.35)"; // chromatic-allow

/** Deterministic [x,y] seed on the unit circle from a node id + index. */
function seedPosition(id: string, index: number, total: number): { x: number; y: number } {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  const jitter = ((h >>> 0) % 1000) / 1000; // 0..1, stable per id
  const angle = (index / Math.max(1, total)) * Math.PI * 2;
  const radius = 0.5 + jitter * 0.5;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

export interface SupplyGraphResult {
  readonly graph: Graph;
  readonly communityCount: number;
}

export function buildSupplyGraph(
  nodes: ReadonlyArray<TopologyNode>,
  edges: ReadonlyArray<TopologyEdge>,
): SupplyGraphResult {
  const graph = new Graph({ type: "directed", multi: true, allowSelfLoops: false });

  nodes.forEach((n, i) => {
    if (graph.hasNode(n.id)) return;
    const pos = seedPosition(n.id, i, nodes.length);
    graph.addNode(n.id, {
      label: n.id,
      nodeType: n.type,
      color: NODE_TYPE_COLOR[n.type] ?? NODE_FALLBACK_COLOR,
      size: 4,
      x: pos.x,
      y: pos.y,
    });
  });

  for (const e of edges) {
    if (e.src === e.dst) continue;
    if (!graph.hasNode(e.src) || !graph.hasNode(e.dst)) continue;
    graph.addDirectedEdge(e.src, e.dst, {
      weight: e.weight ?? 1,
      edgeType: e.type,
      color: EDGE_COLOR,
      size: 0.6,
    });
  }

  // ForceAtlas2 layout — synchronous, bounded iterations.
  if (graph.order > 1) {
    try {
      forceAtlas2.assign(graph, {
        iterations: 100,
        settings: forceAtlas2.inferSettings(graph),
      });
    } catch {
      // Layout is best-effort; seed positions remain if it fails.
    }
  }

  // Louvain community detection — the supply network's natural zones.
  let communityCount = 0;
  if (graph.order > 1) {
    try {
      louvain.assign(graph, { nodeCommunityAttribute: "community" });
      const seen = new Set<number>();
      graph.forEachNode((_, attrs) => {
        const c = (attrs as { community?: number }).community;
        if (typeof c === "number") seen.add(c);
      });
      communityCount = seen.size;
    } catch {
      communityCount = 0;
    }
  }

  // Size nodes by degree so hubs (warehouses, key suppliers) read larger.
  graph.forEachNode((node) => {
    const degree = graph.degree(node);
    graph.setNodeAttribute(node, "size", 3 + Math.min(9, degree));
  });

  return { graph, communityCount };
}
