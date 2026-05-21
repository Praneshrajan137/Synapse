/**
 * SYNAPSE Atlas Console — feature-flag client (logic surface).
 *
 * Self-hosted Unleash (Apache-2.0). The Unleash Edge proxy lives in the
 * compose stack (added in S6 hardening); for S2 we ship the client and a
 * **stub mode** that resolves all flags to their defaults so surfaces can
 * ship behind named gates without a running Edge.
 *
 * The provider component is in ./provider.tsx (JSX).
 *
 * Flag naming convention:
 *   atlas.<surface>.<feature>           — surface-scoped feature
 *   atlas.kill.<surface>                — emergency kill switch
 *   atlas.experimental.<feature>        — pre-prod toggles
 */
import {
  useFlag as useUnleashFlag,
  useUnleashContext,
} from "@unleash/proxy-client-react";

/** Known flags — declared so TS can autocomplete. Add as surfaces land. */
export const FLAG = {
  missionControlBulkApprove: "atlas.mission-control.bulk-approve",
  decisionTraceCompare: "atlas.decision-trace.compare",
  twinStudioMonteCarlo: "atlas.twin-studio.monte-carlo",
  auditVaultPdfExport: "atlas.audit-vault.pdf-export",
  // Kills — default OFF so a flip is fail-safe.
  killTwinStudio: "atlas.kill.twin-studio",
  killAuditVault: "atlas.kill.audit-vault",
} as const;

export type FlagKey = (typeof FLAG)[keyof typeof FLAG];

const PROXY_URL = import.meta.env["VITE_UNLEASH_PROXY_URL"];
const PROXY_TOKEN = import.meta.env["VITE_UNLEASH_TOKEN"];

export const flagsAreLive: boolean = Boolean(PROXY_URL && PROXY_TOKEN);

/**
 * Hook returning whether `flag` is enabled. In stub mode (no Edge URL) we
 * return the default. Default is OFF unless explicitly overridden.
 *
 * The conditional return is keyed on a *build constant*, not runtime state,
 * so React's rules-of-hooks invariant is preserved across renders for any
 * given build.
 */
export function useFlag(flag: FlagKey, defaultEnabled = false): boolean {
  if (!flagsAreLive) {
    return defaultEnabled;
  }
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useUnleashFlag(flag);
}

/**
 * Update Unleash context (e.g. `userId`, `properties.city`). Returns null in
 * stub mode. Called from the auth + city-switch effects so flag rollouts
 * can target ops cohorts.
 */
export function useFlagsContext(): ReturnType<typeof useUnleashContext> | null {
  if (!flagsAreLive) return null;
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useUnleashContext();
}

export { FlagsProvider } from "./provider";
