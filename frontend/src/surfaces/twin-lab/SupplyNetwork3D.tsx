import { useMemo, lazy, Suspense } from "react";
import type { TopologyEdge, TopologyNode } from "./useTopology";

// react-force-graph-3d pulls in three.js + force layout — lazy-load it so
// it never reaches the entry bundle (FE-INV-014 / FE-INV-025).
const ForceGraph3D = lazy(() => import("react-force-graph-3d"));

interface SupplyNetwork3DProps {
  readonly nodes: ReadonlyArray<TopologyNode>;
  readonly edges: ReadonlyArray<TopologyEdge>;
  readonly height?: number;
}

const TYPE_COLOR: Record<string, string> = {
  Warehouse: "rgb(56 189 248)",
  DarkStore: "rgb(34 197 94)",
  Supplier: "rgb(251 191 36)",
  Rider: "rgb(129 140 248)",
};

export function SupplyNetwork3D({ nodes, edges, height = 420 }: SupplyNetwork3DProps) {
  const graph = useMemo(
    () => ({
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type,
        color: TYPE_COLOR[n.type] ?? "rgb(148 163 184)",
      })),
      links: edges.map((e) => ({ source: e.src, target: e.dst, weight: e.weight ?? 1 })),
    }),
    [nodes, edges],
  );

  return (
    <Suspense
      fallback={
        <div className="syn-card flex items-center justify-center text-sm text-ink-muted" style={{ height }}>
          Loading 3D supply network…
        </div>
      }
    >
      <div className="syn-card overflow-hidden" style={{ height }}>
        <ForceGraph3D
          graphData={graph}
          backgroundColor="rgba(2, 6, 23, 0)"
          linkColor={() => "rgba(148, 163, 184, 0.4)"}
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
