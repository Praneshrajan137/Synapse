import type { City } from "@domain/primitives";
import { PageHeader } from "@ds/compounds";
import { Button } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { useCityStore } from "@state/city.store";
import { useMutation } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { toast } from "sonner";

/**
 * Ingress Console — ops surface that exercises the live pipeline directly.
 *
 * Two write paths:
 *   1. Order ingress — injects a real demand order onto `synapse.orders.demand`
 *      via the outbox-backed `POST /api/v1/orders` (202 Accepted), keyed by a
 *      per-intent Idempotency-Key.
 *   2. Manual decision trigger — kicks consensus on the orchestrator and links
 *      straight to the resulting decision's replay.
 *
 * Access is gated to `minRole="ops"` by the router (wired separately).
 */

interface OrderForm {
  readonly city: City;
  readonly store_id: string;
  readonly sku_id: string;
  readonly quantity: number;
}

interface DecisionForm {
  readonly order_id: string;
  readonly store_id: string;
  readonly disruption_active: boolean;
  readonly requires_twin_simulation: boolean;
}

interface OrderReceipt {
  readonly order_id: string;
  readonly outbox_id: string;
}

const inputClass =
  "mt-1 block w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus-visible:shadow-focus focus-visible:outline-none";
const labelClass = "block text-2xs uppercase tracking-wide text-ink-muted";

export function Ingress() {
  const api = useSynapseApi();
  const city = useCityStore((s) => s.city);
  const ids = useId();
  const [receipts, setReceipts] = useState<ReadonlyArray<OrderReceipt>>([]);
  const [lastDecisionId, setLastDecisionId] = useState<string | null>(null);

  const orderForm = useForm<OrderForm>({
    defaultValues: { city, store_id: "", sku_id: "", quantity: 1 },
  });
  const decisionForm = useForm<DecisionForm>({
    defaultValues: {
      order_id: "",
      store_id: "",
      disruption_active: false,
      requires_twin_simulation: false,
    },
  });

  const orderMutation = useMutation({
    mutationFn: (body: OrderForm) =>
      api.submitOrder(
        {
          city: body.city,
          store_id: body.store_id,
          sku_id: body.sku_id,
          quantity: Number(body.quantity),
        },
        { idempotencyKey: crypto.randomUUID() },
      ),
    onSuccess: (res) => {
      setReceipts((prev) =>
        [{ order_id: res.order_id, outbox_id: res.outbox_id }, ...prev].slice(0, 8),
      );
      toast.success(`Order accepted — ${res.order_id.slice(0, 8)}`);
      orderForm.reset({ city, store_id: "", sku_id: "", quantity: 1 });
    },
    onError: (err: Error) => {
      toast.error(`Order ingress failed: ${err.message}`);
    },
  });

  const decisionMutation = useMutation({
    mutationFn: (body: DecisionForm) =>
      api.submitDecision({
        ...(body.order_id ? { order_id: body.order_id } : {}),
        ...(body.store_id ? { store_id: body.store_id } : {}),
        disruption_active: body.disruption_active,
        requires_twin_simulation: body.requires_twin_simulation,
      }),
    onSuccess: (res) => {
      // ConsensusDecision carries `decision_id`; read defensively.
      const decisionId = res?.decision_id;
      if (decisionId) {
        setLastDecisionId(decisionId);
        toast.success(`Consensus triggered — ${decisionId.slice(0, 8)}`);
      } else {
        toast.success("Consensus triggered");
      }
    },
    onError: (err: Error) => {
      toast.error(`Decision trigger failed: ${err.message}`);
    },
  });

  return (
    <section className="mx-auto flex max-w-4xl flex-col gap-4">
      <PageHeader
        title="Ingress Console"
        subtitle="Inject real demand orders and manually trigger consensus — for operators to exercise the live pipeline end to end."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <form
          className="syn-card flex flex-col gap-3 p-4"
          aria-label="Order ingress form"
          onSubmit={orderForm.handleSubmit((data) => orderMutation.mutate(data))}
        >
          <h2 className="font-semibold text-ink text-sm">Order Ingress</h2>

          <div>
            <label htmlFor={`${ids}-city`} className={labelClass}>
              City
            </label>
            <select id={`${ids}-city`} className={inputClass} {...orderForm.register("city")}>
              <option value="bengaluru">Bengaluru</option>
              <option value="mumbai">Mumbai</option>
            </select>
          </div>

          <div>
            <label htmlFor={`${ids}-store`} className={labelClass}>
              Store ID
            </label>
            <input
              id={`${ids}-store`}
              className={inputClass}
              placeholder="store_blr_001"
              {...orderForm.register("store_id", { required: true })}
            />
          </div>

          <div>
            <label htmlFor={`${ids}-sku`} className={labelClass}>
              SKU ID
            </label>
            <input
              id={`${ids}-sku`}
              className={inputClass}
              placeholder="sku_00042"
              {...orderForm.register("sku_id", { required: true })}
            />
          </div>

          <div>
            <label htmlFor={`${ids}-qty`} className={labelClass}>
              Quantity
            </label>
            <input
              id={`${ids}-qty`}
              type="number"
              min={1}
              max={1000}
              className={inputClass}
              {...orderForm.register("quantity", {
                required: true,
                min: 1,
                max: 1000,
                valueAsNumber: true,
              })}
            />
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={orderMutation.isPending}>
              {orderMutation.isPending ? "Submitting…" : "Inject order"}
            </Button>
          </div>

          {receipts.length > 0 && (
            <ul className="space-y-1 border-border border-t pt-2" aria-label="Recent submissions">
              {receipts.map((r) => (
                <li key={r.outbox_id} className="font-mono text-2xs text-ink-muted">
                  order <span className="text-ink">{r.order_id.slice(0, 8)}</span> · outbox{" "}
                  <span className="text-ink">{r.outbox_id.slice(0, 8)}</span>
                </li>
              ))}
            </ul>
          )}
        </form>

        <form
          className="syn-card flex flex-col gap-3 p-4"
          aria-label="Manual decision trigger form"
          onSubmit={decisionForm.handleSubmit((data) => decisionMutation.mutate(data))}
        >
          <h2 className="font-semibold text-ink text-sm">Manual Decision Trigger</h2>

          <div>
            <label htmlFor={`${ids}-d-order`} className={labelClass}>
              Order ID (optional)
            </label>
            <input
              id={`${ids}-d-order`}
              className={inputClass}
              placeholder="order_…"
              {...decisionForm.register("order_id")}
            />
          </div>

          <div>
            <label htmlFor={`${ids}-d-store`} className={labelClass}>
              Store ID (optional)
            </label>
            <input
              id={`${ids}-d-store`}
              className={inputClass}
              placeholder="store_blr_001"
              {...decisionForm.register("store_id")}
            />
          </div>

          <label
            htmlFor={`${ids}-d-disruption`}
            className="flex items-center gap-2 text-sm text-ink"
          >
            <input
              id={`${ids}-d-disruption`}
              type="checkbox"
              className="accent-accent"
              {...decisionForm.register("disruption_active")}
            />
            Disruption active
          </label>

          <label htmlFor={`${ids}-d-twin`} className="flex items-center gap-2 text-sm text-ink">
            <input
              id={`${ids}-d-twin`}
              type="checkbox"
              className="accent-accent"
              {...decisionForm.register("requires_twin_simulation")}
            />
            Requires twin simulation
          </label>

          <div className="flex justify-end">
            <Button type="submit" disabled={decisionMutation.isPending}>
              {decisionMutation.isPending ? "Triggering…" : "Trigger consensus"}
            </Button>
          </div>

          {lastDecisionId && (
            <div className="flex items-center justify-between gap-2 border-border border-t pt-2">
              <span className="font-mono text-2xs text-ink-muted">
                {lastDecisionId.slice(0, 8)}
              </span>
              <Link
                to={`/decisions/${lastDecisionId}`}
                className="text-2xs font-medium text-accent hover:underline"
              >
                Replay →
              </Link>
            </div>
          )}
        </form>
      </div>
    </section>
  );
}
