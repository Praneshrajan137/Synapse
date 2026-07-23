import { SyntheticBadge } from "@ds/compounds";
import type { WorldVital } from "@lib/autonomy";
import { fmt } from "@lib/formatters";
import { useTranslation } from "react-i18next";

/**
 * The "perceive" phase made visible (ADR-053): per-city live world vitals from
 * the standing WorldRuntime. Honest by construction —
 *   - a stalled sim clock renders a degraded state, never healthy vitals;
 *   - an unreachable world says so, never a fabricated snapshot;
 *   - the world is ALWAYS labeled synthetic (it is a simulation, not commerce).
 */
export function WorldVitals({ worlds }: { readonly worlds: ReadonlyArray<WorldVital> }) {
  const { t } = useTranslation("common");

  if (worlds.length === 0) {
    return <p className="text-xs text-ink-subtle">{t("world.unreachable")}</p>;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {worlds.map((w) => (
        <div key={w.city} className="syn-card px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium capitalize text-ink">{w.city}</span>
            {w.synthetic && <SyntheticBadge />}
          </div>

          {w.kind === "unreachable" && (
            <p
              className="mt-2 flex items-center gap-1.5 text-xs font-medium text-state-degraded"
              style={{ color: "var(--syn-state-degraded)" }}
            >
              <span aria-hidden>▲</span>
              {t("world.unreachable")}
            </p>
          )}

          {w.kind === "stalled" && (
            <p
              className="mt-2 flex items-center gap-1.5 text-xs font-medium"
              style={{ color: "var(--syn-state-degraded)" }}
            >
              <span aria-hidden>▲</span>
              {t("world.clock_stalled")}
            </p>
          )}

          {w.kind === "live" && (
            <>
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                <Vital
                  label={t("world.fill_rate")}
                  value={w.fillRate === null ? "—" : fmt.pct(w.fillRate)}
                  tone={w.fillRate !== null && w.fillRate < 0.9 ? "warn" : "neutral"}
                />
                <Vital
                  label={t("world.spoilage_rate")}
                  value={w.spoilageRate === null ? "—" : fmt.pct(w.spoilageRate)}
                  tone={w.spoilageRate !== null && w.spoilageRate > 0.05 ? "warn" : "neutral"}
                />
                <Vital
                  label={t("world.demand_rate")}
                  value={
                    w.demandRate === null
                      ? "—"
                      : `${fmt.decimal(w.demandRate, 2)} ${t("world.demand_rate_unit")}`
                  }
                />
                <Vital
                  label={t("world.pending_orders")}
                  value={w.pendingOrders === null ? "—" : fmt.compact(w.pendingOrders)}
                />
                <Vital
                  label={t("world.restocks")}
                  value={w.restocks === null ? "—" : fmt.compact(w.restocks)}
                />
                <Vital
                  label={t("world.inventory")}
                  value={w.skuCount === null ? "—" : `${fmt.compact(w.skuCount)} SKU`}
                />
              </dl>
              <p className="mt-2 text-2xs text-ink-subtle">{t("world.synthetic_note")}</p>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

function Vital({
  label,
  value,
  tone = "neutral",
}: {
  readonly label: string;
  readonly value: string;
  readonly tone?: "neutral" | "warn";
}) {
  return (
    <div className="flex flex-col">
      <dt className="text-2xs uppercase tracking-wide text-ink-subtle">{label}</dt>
      <dd
        className={
          tone === "warn"
            ? "font-medium tabular-nums text-signal-warning"
            : "font-medium tabular-nums text-ink"
        }
      >
        {value}
      </dd>
    </div>
  );
}
