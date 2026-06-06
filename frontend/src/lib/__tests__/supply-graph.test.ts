import { NODE_TYPE_COLOR, buildSupplyGraph } from "@lib/supply-graph";
import type { TopologyEdge, TopologyNode } from "@surfaces/twin-lab/useTopology";
import { describe, expect, it } from "vitest";

const nodes: TopologyNode[] = [
  { id: "wh-1", type: "Warehouse" },
  { id: "store-1", type: "DarkStore" },
  { id: "store-2", type: "DarkStore" },
  { id: "sup-1", type: "Supplier" },
];

const edges: TopologyEdge[] = [
  { src: "sup-1", dst: "wh-1", type: "SUPPLIES", weight: 0.8 },
  { src: "wh-1", dst: "store-1", type: "SERVES", weight: 0.5 },
  { src: "wh-1", dst: "store-2", type: "SERVES", weight: 0.6 },
  { src: "store-1", dst: "store-1", type: "SELF", weight: 1 }, // self-loop — skipped
  { src: "wh-1", dst: "ghost", type: "SERVES", weight: 1 }, // missing endpoint — skipped
];

describe("buildSupplyGraph", () => {
  it("builds a graph with one node per topology node and only valid edges", () => {
    const { graph } = buildSupplyGraph(nodes, edges);
    expect(graph.order).toBe(4); // 4 nodes
    expect(graph.size).toBe(3); // 3 valid edges (self-loop + dangling skipped)
  });

  it("colours nodes by type and records the type attribute", () => {
    const { graph } = buildSupplyGraph(nodes, edges);
    expect(graph.getNodeAttribute("wh-1", "color")).toBe(NODE_TYPE_COLOR.Warehouse);
    expect(graph.getNodeAttribute("sup-1", "nodeType")).toBe("Supplier");
  });

  it("assigns deterministic positions (reproducible renders)", () => {
    const a = buildSupplyGraph(nodes, edges).graph;
    const b = buildSupplyGraph(nodes, edges).graph;
    expect(a.getNodeAttribute("wh-1", "x")).toBe(b.getNodeAttribute("wh-1", "x"));
    expect(a.getNodeAttribute("wh-1", "y")).toBe(b.getNodeAttribute("wh-1", "y"));
  });

  it("detects communities on a connected supply network", () => {
    const { communityCount } = buildSupplyGraph(nodes, edges);
    expect(communityCount).toBeGreaterThanOrEqual(1);
  });

  it("sizes nodes by degree (hubs read larger)", () => {
    const { graph } = buildSupplyGraph(nodes, edges);
    // wh-1 has degree 3 (1 in, 2 out); store-2 has degree 1.
    const hub = graph.getNodeAttribute("wh-1", "size") as number;
    const leaf = graph.getNodeAttribute("store-2", "size") as number;
    expect(hub).toBeGreaterThan(leaf);
  });

  it("handles an empty topology without throwing", () => {
    const { graph, communityCount } = buildSupplyGraph([], []);
    expect(graph.order).toBe(0);
    expect(communityCount).toBe(0);
  });

  it("dedupes repeated node ids", () => {
    const dupNodes: TopologyNode[] = [
      { id: "x", type: "Warehouse" },
      { id: "x", type: "Warehouse" },
    ];
    expect(buildSupplyGraph(dupNodes, []).graph.order).toBe(1);
  });
});
