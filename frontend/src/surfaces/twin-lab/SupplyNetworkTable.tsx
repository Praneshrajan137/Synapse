import { useMemo } from "react";
import type { TopologyEdge, TopologyNode } from "./useTopology";

interface SupplyNetworkTableProps {
  readonly nodes: ReadonlyArray<TopologyNode>;
  readonly edges: ReadonlyArray<TopologyEdge>;
  readonly selectedId?: string | null;
  readonly onSelectNode?: (id: string | null) => void;
}

/**
 * Non-spatial equivalent of the WebGL supply-network graph (Req 7.4).
 *
 * The Sigma/WebGL canvas is opaque to assistive tech and cannot be traversed by
 * keyboard, so this component exposes the same ontology — every node with its
 * type, position, and degree — as a keyboard-focusable, screen-reader-navigable
 * table. Selecting a row raises `onSelectNode`, mirroring a canvas node-click so
 * the shared NodeInspector works identically from either representation. It sits
 * in a `<details>` disclosure: always in the DOM (SR-reachable) and operable via
 * the `<summary>` without a pointer.
 */
export function SupplyNetworkTable({
  nodes,
  edges,
  selectedId = null,
  onSelectNode,
}: SupplyNetworkTableProps) {
  // Degree per node (in + out), derived once from the edge list.
  const degreeById = useMemo(() => {
    const d = new Map<string, number>();
    for (const e of edges) {
      d.set(e.src, (d.get(e.src) ?? 0) + 1);
      d.set(e.dst, (d.get(e.dst) ?? 0) + 1);
    }
    return d;
  }, [edges]);

  return (
    <details className="syn-card mt-2 p-0">
      <summary className="cursor-pointer select-none rounded-md px-3 py-2 text-xs font-medium text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:shadow-focus">
        Supply network as a table ({nodes.length} nodes · {edges.length} links)
      </summary>

      <div className="px-3 pb-3 pt-1">
        {nodes.length === 0 ? (
          <p className="text-2xs text-ink-subtle">No topology to list yet.</p>
        ) : (
          <table className="w-full text-left text-2xs">
            <caption className="sr-only">
              Supply network nodes with type, position, and connection count. Activate a row to
              inspect that node.
            </caption>
            <thead>
              <tr className="text-ink-subtle">
                <th scope="col" className="py-0.5 pr-3 font-medium">
                  Node
                </th>
                <th scope="col" className="py-0.5 pr-3 font-medium">
                  Type
                </th>
                <th scope="col" className="py-0.5 pr-3 font-medium">
                  Position
                </th>
                <th scope="col" className="py-0.5 font-medium">
                  Links
                </th>
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums text-ink-muted">
              {nodes.map((n) => {
                const selected = n.id === selectedId;
                const pos =
                  n.lat != null || n.lon != null
                    ? `${n.lat?.toFixed(4) ?? "—"}, ${n.lon?.toFixed(4) ?? "—"}`
                    : "—";
                return (
                  <tr key={n.id} aria-selected={selected}>
                    <th scope="row" className="py-0.5 pr-3 font-normal">
                      <button
                        type="button"
                        onClick={() => onSelectNode?.(selected ? null : n.id)}
                        aria-pressed={selected}
                        className="rounded px-1 text-left text-ink hover:text-accent focus-visible:outline-none focus-visible:shadow-focus aria-pressed:text-accent"
                      >
                        {n.id}
                      </button>
                    </th>
                    <td className="py-0.5 pr-3">{n.type}</td>
                    <td className="py-0.5 pr-3">{pos}</td>
                    <td className="py-0.5">{degreeById.get(n.id) ?? 0}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </details>
  );
}
