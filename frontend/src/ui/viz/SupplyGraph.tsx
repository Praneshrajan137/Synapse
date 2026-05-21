import type { TwinNode, TwinTopology } from "@/domain/twin";
import { cn } from "@/ui/lib/cn";
import { useMemo } from "react";

/**
 * SupplyGraph — the digital twin's supply network.
 *
 * A custom SVG layered graph (suppliers → warehouses → stores). Node
 * stress drives a warm glow and a ping ring; the layout is deterministic
 * per city. No map vendor, no tiles (tenet T-12).
 */

const KIND_COLOR: Record<TwinNode["kind"], string> = {
  supplier: "var(--color-agent-supplier)",
  warehouse: "var(--color-agent-demand)",
  store: "var(--color-sig-live)",
  rider: "var(--color-sig-ok)",
  zone: "var(--color-ink-hint)",
};

const KIND_RADIUS: Record<TwinNode["kind"], number> = {
  supplier: 1.4,
  warehouse: 1.7,
  store: 1.1,
  rider: 0.9,
  zone: 1,
};

export interface SupplyGraphProps {
  topology: TwinTopology;
  className?: string;
}

export function SupplyGraph({ topology, className }: SupplyGraphProps) {
  const nodeIndex = useMemo(() => {
    const map = new Map<string, TwinNode>();
    for (const n of topology.nodes) map.set(n.id, n);
    return map;
  }, [topology.nodes]);

  return (
    <div className={cn("relative overflow-hidden rounded-lg bg-void", className)}>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="size-full"
        role="img"
        aria-label={`Supply network — ${topology.nodes.length} nodes`}
      >
        <title>Digital twin supply network</title>
        {topology.edges.map((edge, i) => {
          const from = nodeIndex.get(edge.from);
          const to = nodeIndex.get(edge.to);
          if (!from || !to) return null;
          return (
            <line
              key={`${edge.from}-${edge.to}-${i}`}
              x1={from.x * 100}
              y1={from.y * 100}
              x2={to.x * 100}
              y2={to.y * 100}
              stroke="var(--color-line-strong)"
              strokeWidth={0.25}
            />
          );
        })}
        {topology.nodes.map((node) => {
          const color = KIND_COLOR[node.kind];
          const radius = KIND_RADIUS[node.kind];
          const stressed = node.stress > 0.7;
          return (
            <g key={node.id}>
              {stressed && (
                <circle
                  cx={node.x * 100}
                  cy={node.y * 100}
                  r={radius * 2.4}
                  fill="none"
                  stroke="var(--color-sig-stop)"
                  strokeWidth={0.3}
                  style={{
                    transformOrigin: `${node.x * 100}px ${node.y * 100}px`,
                    animation: "synapse-ping 2.6s ease-out infinite",
                  }}
                />
              )}
              <circle
                cx={node.x * 100}
                cy={node.y * 100}
                r={radius}
                fill={stressed ? "var(--color-sig-stop)" : color}
                fillOpacity={0.45 + node.stress * 0.5}
              >
                <title>{`${node.label} · ${node.kind} · stress ${(node.stress * 100).toFixed(0)}%`}</title>
              </circle>
            </g>
          );
        })}
      </svg>
      <div className="absolute bottom-2 left-3 flex flex-wrap gap-x-3 gap-y-1 text-2xs text-ink-hint">
        {(["supplier", "warehouse", "store"] as const).map((kind) => (
          <span key={kind} className="flex items-center gap-1.5">
            <span
              className="size-2 rounded-full"
              style={{ backgroundColor: KIND_COLOR[kind] }}
            />
            {kind}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-sig-stop" />
          stressed
        </span>
      </div>
    </div>
  );
}
