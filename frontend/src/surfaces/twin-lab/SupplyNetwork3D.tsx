import { Suspense, lazy, useMemo } from "react";
import type { TopologyEdge, TopologyNode } from "./useTopology";

// react-force-graph-3d pulls in three.js + force layout — lazy-load it so
// it never reaches the entry bundle (FE-INV-014 / FE-INV-025).
const ForceGraph3D = lazy(() => import("react-force-graph-3d"));

interface SupplyNetwork3DProps {
  readonly nodes: ReadonlyArray<TopologyNode>;
  readonly edges: ReadonlyArray<TopologyEdge>;
  readonly height?: number;
}

// chromatic-allow: react-force-graph-3d / three.js consume literal colour
// strings on the GPU and cannot resolve CSS custom properties. Tracked for
// chromatic-token migration (INV-CLR-009).
const TYPE_COLOR: Record<string, string> = {
  Warehouse: "rgb(56 189 248)", // chromatic-allow
  DarkStore: "rgb(34 197 94)", // chromatic-allow
  Supplier: "rgb(251 191 36)", // chromatic-allow
  Rider: "rgb(129 140 248)", // chromatic-allow
};

// chromatic-allow: three.js fallback node colour (INV-CLR-009).
const NODE_FALLBACK_COLOR = "rgb(148 163 184)"; // chromatic-allow

export function SupplyNetwork3D({ nodes, edges, height = 420 }: SupplyNetwork3DProps) {
  const graph = useMemo(
    () => ({
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type,
        color: TYPE_COLOR[n.type] ?? NODE_FALLBACK_COLOR,
      })),
      links: edges.map((e) => ({ source: e.src, target: e.dst, weight: e.weight ?? 1 })),
    }),
    [nodes, edges],
  );

  return (
    <Suspense
      fallback={
        <div
          className="syn-card flex items-center justify-center text-sm text-ink-muted"
          style={{ height }}
        >
          Loading 3D supply network…
        </div>
      }
    >
      <div className="syn-card overflow-hidden" style={{ height }}>
        <ForceGraph3D
          graphData={graph}
          backgroundColor="rgba(2, 6, 23, 0)" // chromatic-allow: three.js GPU colour (INV-CLR-009)
          linkColor={() => "rgba(148, 163, 184, 0.4)"} // chromatic-allow: three.js GPU colour (INV-CLR-009)
          linkOpacity={0.4}
          nodeRelSize={4}
          nodeColor={(n) => (n as { color: string }).color}
          nodeLabel={(n) => `${(n as { id: string }).id} (${(n as { type: string }).type})`}
          height={height}
          enableNodeDrag={false}
        />
      </div>
    </Suspense>
  );
}
