import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NodeInspector } from "../NodeInspector";
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

describe("NodeInspector", () => {
  it("prompts to select a node when nothing is selected", () => {
    render(<NodeInspector selectedId={null} nodes={NODES} edges={EDGES} onClose={() => {}} />);
    expect(screen.getByText(/click a node/i)).toBeInTheDocument();
  });

  it("renders the selected node's type, geo, and derived neighbours", () => {
    render(
      <NodeInspector selectedId="warehouse-blr-0" nodes={NODES} edges={EDGES} onClose={() => {}} />,
    );
    expect(screen.getByText("Warehouse")).toBeInTheDocument();
    expect(screen.getByText("warehouse-blr-0")).toBeInTheDocument();
    // degree = 1 outgoing (SERVES store) + 1 incoming (SUPPLIES from supplier)
    expect(screen.getByText(/2 links/)).toBeInTheDocument();
    expect(screen.getByText("store-blr-001")).toBeInTheDocument();
    expect(screen.getByText("supplier-blr-0")).toBeInTheDocument();
    expect(screen.getByText(/12.9700, 77.5900/)).toBeInTheDocument();
  });

  it("clears the selection via the close button", async () => {
    const onClose = vi.fn();
    render(
      <NodeInspector selectedId="store-blr-001" nodes={NODES} edges={EDGES} onClose={onClose} />,
    );
    await userEvent.click(screen.getByLabelText(/clear node selection/i));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
