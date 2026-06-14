import { Badge } from "@ds/primitives";
import { useMemo } from "react";
import type { TopologyEdge, TopologyNode } from "./useTopology";

interface NodeInspectorProps {
  readonly selectedId: string | null;
  readonly nodes: ReadonlyArray<TopologyNode>;
  readonly edges: ReadonlyArray<TopologyEdge>;
  readonly onClose: () => void;
}

/**
 * Inspector for a clicked supply-network node (Sprint 17). Derives the node's
 * type, geo position, and its in/out neighbours (with edge type + weight) from
 * the live topology — turning the previously inert WebGL graph into a
 * navigable map of the supply ontology.
 */
export function NodeInspector({ selectedId, nodes, edges, onClose }: NodeInspectorProps) {
  const node = useMemo(() => nodes.find((n) => n.id === selectedId) ?? null, [nodes, selectedId]);

  const { outgoing, incoming } = useMemo(() => {
    const typeOf = (id: string) => nodes.find((n) => n.id === id)?.type ?? "node";
    return {
      outgoing: edges
        .filter((e) => e.src === selectedId)
        .map((e) => ({ id: e.dst, type: typeOf(e.dst), edge: e.type, weight: e.weight })),
      incoming: edges
        .filter((e) => e.dst === selectedId)
        .map((e) => ({ id: e.src, type: typeOf(e.src), edge: e.type, weight: e.weight })),
    };
  }, [edges, nodes, selectedId]);

  if (!selectedId || !node) {
    return (
      <div className="syn-card flex h-full min-h-[120px] items-center justify-center p-4 text-center text-xs text-ink-subtle">
        Click a node in the supply network to inspect its connections.
      </div>
    );
  }

  const degree = outgoing.length + incoming.length;

  return (
    <aside className="syn-card-raised space-y-3 p-4" aria-label={`Inspector for node ${node.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <Badge tone="neutral">{node.type}</Badge>
            <span className="font-mono text-2xs text-ink-muted tabular-nums">{degree} links</span>
          </div>
          <p className="mt-1 break-all font-mono text-xs text-ink">{node.id}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded px-1.5 text-ink-subtle hover:text-ink focus-visible:shadow-focus focus-visible:outline-none"
          aria-label="Clear node selection"
        >
          ✕
        </button>
      </div>

      {(node.lat != null || node.lon != null) && (
        <p className="font-mono text-2xs text-ink-muted tabular-nums">
          {node.lat?.toFixed(4)}, {node.lon?.toFixed(4)}
        </p>
      )}

      <NeighbourList title={`Supplies / serves (${outgoing.length})`} items={outgoing} />
      <NeighbourList title={`Fed by (${incoming.length})`} items={incoming} />
    </aside>
  );
}

interface Neighbour {
  readonly id: string;
  readonly type: string;
  readonly edge: string;
  readonly weight?: number | undefined;
}

function NeighbourList({ title, items }: { title: string; items: ReadonlyArray<Neighbour> }) {
  return (
    <div className="space-y-1">
      <h4 className="text-2xs uppercase tracking-wide text-ink-subtle">{title}</h4>
      {items.length === 0 ? (
        <p className="text-2xs text-ink-subtle">None</p>
      ) : (
        <ul className="space-y-0.5">
          {items.slice(0, 12).map((n) => (
            <li
              key={`${n.edge}-${n.id}`}
              className="flex items-center justify-between gap-2 font-mono text-2xs"
            >
              <span className="truncate text-ink-muted" title={n.id}>
                {n.id}
              </span>
              <span className="shrink-0 tabular-nums text-ink-subtle">
                {n.edge}
                {n.weight != null ? ` · ${n.weight.toFixed(2)}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
