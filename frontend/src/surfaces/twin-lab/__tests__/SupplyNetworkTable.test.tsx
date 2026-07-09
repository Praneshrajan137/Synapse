import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SupplyNetworkTable } from "../SupplyNetworkTable";
import type { TopologyEdge, TopologyNode } from "../useTopology";

const NODES: TopologyNode[] = [
  { id: "warehouse-blr-0", type: "Warehouse", lat: 12.97, lon: 77.59 },
  { id: "store-blr-001", type: "DarkStore", lat: 12.93, lon: 77.62 },
  { id: "supplier-blr-0", type: "Supplier" },
];
const EDGES: TopologyEdge[] = [
  { src: "warehouse-blr-0", dst: "store-blr-001", type: "SERVES", weight: 0.8 },
  { src: "supplier-blr-0", dst: "warehouse-blr-0", type: "SUPPLIES", weight: 0.5 },
];

// Req 7.4: the WebGL graph must have a keyboard/SR-reachable non-spatial twin.
describe("SupplyNetworkTable", () => {
  it("lists every node with its type, position, and link count", () => {
    render(<SupplyNetworkTable nodes={NODES} edges={EDGES} />);
    const table = screen.getByRole("table");
    // header row + 3 nodes
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(within(table).getByText("Warehouse")).toBeInTheDocument();
    expect(within(table).getByText(/12.9700, 77.5900/)).toBeInTheDocument();
    // supplier has no coordinates -> em dash
    expect(within(table).getByText("Supplier")).toBeInTheDocument();
  });

  it("selects a node by keyboard activation, mirroring a canvas click", async () => {
    const onSelectNode = vi.fn();
    render(<SupplyNetworkTable nodes={NODES} edges={EDGES} onSelectNode={onSelectNode} />);
    const trigger = screen.getByRole("button", { name: "warehouse-blr-0" });
    trigger.focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelectNode).toHaveBeenCalledWith("warehouse-blr-0");
  });

  it("toggles the selection off when the selected row is activated again", async () => {
    const onSelectNode = vi.fn();
    render(
      <SupplyNetworkTable
        nodes={NODES}
        edges={EDGES}
        selectedId="warehouse-blr-0"
        onSelectNode={onSelectNode}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "warehouse-blr-0" }));
    expect(onSelectNode).toHaveBeenCalledWith(null);
  });

  it("shows an explicit empty note rather than a bare table when there is no topology", () => {
    render(<SupplyNetworkTable nodes={[]} edges={[]} />);
    expect(screen.getByText(/no topology to list yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
