import type { ActionPayload } from "@/domain/decision";
import { cn } from "@/ui/lib/cn";
import { signed } from "@/ui/lib/format";
import { signal } from "@/ui/tokens";

/**
 * Generative UI — schema-driven payload rendering (plan section 6.1).
 *
 * An agent's action payload is tagged with a `kind`; this registry maps
 * each known kind to a purpose-built mini-component. Unknown payloads
 * fall through to a generic introspection card — the interface always
 * renders *something* meaningful, never "[object Object]".
 */

type Data = Readonly<Record<string, unknown>>;

const num = (d: Data, key: string): number =>
  typeof d[key] === "number" ? (d[key] as number) : Number.NaN;
const str = (d: Data, key: string): string =>
  d[key] === undefined || d[key] === null ? "—" : String(d[key]);

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-display text-2xs font-semibold uppercase tracking-[0.1em] text-ink-hint">
        {label}
      </span>
      <span className="tnum text-xs text-ink-primary">{children}</span>
    </div>
  );
}

function ForecastBandCard({ data }: { data: Data }) {
  const horizons = (data.horizons as Record<string, number> | undefined) ?? {};
  const keys = ["15m", "1h", "6h", "24h", "7d"];
  const max = Math.max(1, ...keys.map((k) => horizons[k] ?? 0));
  return (
    <div className="flex items-end gap-2">
      {keys.map((k) => (
        <div key={k} className="flex flex-col items-center gap-1">
          <div className="flex h-14 w-7 items-end rounded-xs bg-membrane">
            <div
              className="w-full rounded-xs"
              style={{
                height: `${((horizons[k] ?? 0) / max) * 100}%`,
                backgroundColor: signal.live,
              }}
            />
          </div>
          <span className="font-mono text-2xs text-ink-hint">{k}</span>
          <span className="tnum font-mono text-2xs text-ink-secondary">
            {horizons[k] ?? 0}
          </span>
        </div>
      ))}
    </div>
  );
}

function PriceChangeBadge({ data }: { data: Data }) {
  const oldM = num(data, "oldMultiplier");
  const newM = num(data, "newMultiplier");
  const delta = newM - oldM;
  const essential = data.essential === true;
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-baseline gap-2 font-mono text-base">
        <span className="text-ink-hint line-through">{oldM.toFixed(2)}x</span>
        <span aria-hidden="true" className="text-ink-hint">
          →
        </span>
        <span className="font-semibold text-ink-primary">{newM.toFixed(2)}x</span>
      </div>
      <span
        className="tnum rounded-sm px-1.5 py-0.5 text-2xs"
        style={{
          color: delta > 0 ? signal.warn : signal.ok,
          backgroundColor: `color-mix(in oklab, ${delta > 0 ? signal.warn : signal.ok} 14%, transparent)`,
        }}
      >
        {signed(delta, 2)}
      </span>
      {essential && <span className="text-2xs text-sig-warn">essential · 1.3x cap</span>}
    </div>
  );
}

function ReorderBar({ data }: { data: Data }) {
  const current = num(data, "currentUnits");
  const reorder = num(data, "reorderUnits");
  const total = current + reorder;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between text-2xs text-ink-hint">
        <span>{str(data, "skuId")}</span>
        <span>{str(data, "storeId")}</span>
      </div>
      <div className="flex h-3 overflow-hidden rounded-full bg-membrane">
        <div
          style={{ width: `${(current / total) * 100}%`, backgroundColor: signal.stop }}
        />
        <div
          style={{ width: `${(reorder / total) * 100}%`, backgroundColor: signal.ok }}
        />
      </div>
      <div className="flex gap-4 text-2xs">
        <span className="text-sig-stop">on hand {current}u</span>
        <span className="text-sig-ok">reorder {reorder}u</span>
      </div>
    </div>
  );
}

function RoutePlanMini({ data }: { data: Data }) {
  return (
    <div className="flex gap-5">
      <Field label="Rider">{str(data, "riderId")}</Field>
      <Field label="Stops">{str(data, "stops")}</Field>
      <Field label="ETA">{str(data, "etaMin")} min</Field>
    </div>
  );
}

function DisruptionBanner({ data }: { data: Data }) {
  const severity = num(data, "severity");
  const stores = (data.affectedStores as string[] | undefined) ?? [];
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-sig-stop">{str(data, "kind")}</span>
        <span className="tnum rounded-sm bg-sig-stop/14 px-1.5 text-2xs text-sig-stop">
          severity {severity.toFixed(2)}
        </span>
      </div>
      <span className="text-2xs text-ink-hint">affects {stores.join(", ") || "—"}</span>
    </div>
  );
}

function ShelfLifeRing({ data }: { data: Data }) {
  return (
    <div className="flex gap-5">
      <Field label="SKU">{str(data, "skuId")}</Field>
      <Field label="Shelf life">{str(data, "shelfLifeHours")} h</Field>
      <Field label="Markdown">{str(data, "markdownPct")}%</Field>
    </div>
  );
}

function SupplierScore({ data }: { data: Data }) {
  return (
    <div className="flex gap-5">
      <Field label="Supplier">{str(data, "supplierId")}</Field>
      <Field label="Trust">{num(data, "trustScore").toFixed(2)}</Field>
      <Field label="Lead time">{str(data, "leadTimeDays")} d</Field>
    </div>
  );
}

function CarbonCard({ data }: { data: Data }) {
  return (
    <div className="flex gap-5">
      <Field label="CO₂ / delivery">{num(data, "co2KgPerDelivery").toFixed(2)} kg</Field>
      <Field label="Waste forecast">{str(data, "wastePredictionKg")} kg</Field>
    </div>
  );
}

/** Fallback — introspects an unknown payload's fields. Never "[object]". */
function JsonIntrospect({ data }: { data: Data }) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return <span className="text-2xs text-ink-hint">No payload fields.</span>;
  }
  return (
    <dl className="grid grid-cols-2 gap-x-5 gap-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="flex flex-col">
          <dt className="font-display text-2xs uppercase tracking-[0.1em] text-ink-hint">
            {key}
          </dt>
          <dd className="truncate font-mono text-2xs text-ink-secondary">
            {typeof value === "object" ? JSON.stringify(value) : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

const REGISTRY: Record<string, (props: { data: Data }) => React.ReactNode> = {
  "demand.forecast.v1": ForecastBandCard,
  "pricing.update.v1": PriceChangeBadge,
  "inventory.reorder.v1": ReorderBar,
  "routing.plan.v1": RoutePlanMini,
  "disruption.alert.v1": DisruptionBanner,
  "freshness.alert.v1": ShelfLifeRing,
  "supplier.score.v1": SupplierScore,
  "sustainability.carbon.v1": CarbonCard,
};

export function hasRenderer(kind: string): boolean {
  return kind in REGISTRY;
}

/** Render an action payload with its purpose-built component, or fall back. */
export function PayloadRenderer({
  payload,
  className,
}: {
  payload: ActionPayload;
  className?: string;
}) {
  const Renderer = REGISTRY[payload.kind] ?? JsonIntrospect;
  return (
    <div className={cn("rounded-md border border-line-faint bg-void p-3", className)}>
      <Renderer data={payload.data} />
    </div>
  );
}
