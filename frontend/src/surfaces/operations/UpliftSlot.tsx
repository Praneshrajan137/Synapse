import { DataPathNotice } from "@ds/compounds";
import { AWAITING_UPLIFT_MEASURE, type UpliftMeasure, resolveUpliftSlot } from "@lib/uplift-slot";
import { surfaceDataPath } from "../data-paths";

/**
 * Operations uplift slot (Req 17) — a DEFINED, always-present slot reserving a
 * place for a system-level uplift measure.
 *
 * When the Backend_Contract exposes a measure it renders the value with its
 * sample size, evaluation window, and "as of" timestamp (Req 17.2). When it
 * does not — the reality today, a Cross_Boundary_Dependency — it renders
 * "awaiting uplift measure" (Req 17.3) rather than hiding the slot (Req 17.1)
 * or fabricating a value (Req 17.4). The corresponding backend gap is recorded
 * in the contract-fidelity drift report (`UPLIFT_BACKEND_GAP`).
 *
 * The measure is passed in (default `null`) because no backend endpoint exposes
 * one yet; wiring a hook later needs no change to this slot.
 *
 * R13.6: "awaiting uplift measure" says the value is missing; it does not say
 * that no endpoint exists to deliver it. The registered data path
 * (`operations.uplift`, `endpoint: null`) states that, so "awaiting" is not
 * mistaken for "a measurement is in flight". This matters more here than
 * anywhere else on the console: uplift is the one number the system exists to
 * produce, and its absence must not read as a pending refresh.
 */
export function UpliftSlot({ measure = null }: { readonly measure?: UpliftMeasure | null }) {
  const slot = resolveUpliftSlot(measure);
  const dataPath = surfaceDataPath("operations.uplift", { degraded: null, synthetic: null });

  return (
    <section className="syn-card space-y-3 p-4" aria-label="System-level uplift">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">System uplift</h2>
        <span className="text-2xs font-medium uppercase tracking-wide text-ink-subtle">
          {slot.kind === "present" ? "measured" : "awaiting"}
        </span>
      </div>

      <DataPathNotice state={dataPath} />

      {slot.kind === "awaiting" ? (
        <p className="text-xs text-ink-subtle">{AWAITING_UPLIFT_MEASURE}</p>
      ) : (
        <div className="space-y-2">
          <div className="font-mono text-2xl text-ink">{slot.value}</div>
          <dl className="grid grid-cols-3 gap-2 text-2xs text-ink-subtle">
            <div className="space-y-0.5">
              <dt className="uppercase tracking-[0.14em]">Sample size</dt>
              <dd className="font-mono text-xs text-ink-muted">n = {slot.sampleSize}</dd>
            </div>
            <div className="space-y-0.5">
              <dt className="uppercase tracking-[0.14em]">Window</dt>
              <dd className="text-xs text-ink-muted">{slot.windowLabel}</dd>
            </div>
            <div className="space-y-0.5">
              <dt className="uppercase tracking-[0.14em]">As of</dt>
              <dd className="font-mono text-xs text-ink-muted">{slot.asOf}</dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  );
}
