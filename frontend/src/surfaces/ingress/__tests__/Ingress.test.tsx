import { Ingress } from "@surfaces/ingress/Ingress";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the api hook — the surface is exercised through submitOrder /
// submitDecision; we assert the outgoing shape, not the transport.
const submitOrderMock = vi.hoisted(() => vi.fn());
const submitDecisionMock = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-synapse-api", () => ({
  useSynapseApi: () => ({ submitOrder: submitOrderMock, submitDecision: submitDecisionMock }),
}));

// sonner toasts render to a portal we don't mount; stub to keep tests quiet.
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function wrapper(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Ingress surface", () => {
  beforeEach(() => {
    submitOrderMock.mockReset();
    submitDecisionMock.mockReset();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("renders both ingress panels", () => {
    render(wrapper(<Ingress />));
    expect(screen.getByLabelText(/Order ingress form/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Manual decision trigger form/)).toBeInTheDocument();
  });

  it("submits an order with the right shape and shows a receipt", async () => {
    const user = userEvent.setup();
    submitOrderMock.mockResolvedValue({
      status: "accepted",
      order_id: "order_ab12cd34",
      outbox_id: "outbox_ef56gh78",
    });
    render(wrapper(<Ingress />));

    // "Store ID" appears in both forms — scope to the order form.
    const orderForm = within(screen.getByLabelText(/Order ingress form/));
    await user.type(orderForm.getByLabelText(/^Store ID$/), "store_blr_001");
    await user.type(orderForm.getByLabelText(/SKU ID/), "sku_00042");
    const qty = orderForm.getByLabelText(/Quantity/);
    await user.clear(qty);
    await user.type(qty, "5");

    await user.click(orderForm.getByRole("button", { name: /Inject order/ }));

    await waitFor(() => expect(submitOrderMock).toHaveBeenCalledTimes(1));
    const [body, opts] = submitOrderMock.mock.calls[0] ?? [];
    expect(body).toEqual({
      city: "bengaluru",
      store_id: "store_blr_001",
      sku_id: "sku_00042",
      quantity: 5,
    });
    expect(opts.idempotencyKey).toEqual(expect.any(String));

    await waitFor(() => expect(screen.getByText(/order_ab/)).toBeInTheDocument());
  });

  it("triggers consensus and renders a replay link", async () => {
    const user = userEvent.setup();
    submitDecisionMock.mockResolvedValue({
      decision_id: "11111111-1111-4111-8111-111111111111",
    });
    render(wrapper(<Ingress />));

    await user.click(screen.getByRole("button", { name: /Trigger consensus/ }));

    await waitFor(() => expect(submitDecisionMock).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      const link = screen.getByRole("link", { name: /Replay/ });
      expect(link).toHaveAttribute("href", "/decisions/11111111-1111-4111-8111-111111111111");
    });
  });
});
