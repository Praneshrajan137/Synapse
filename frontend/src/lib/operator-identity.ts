// Operator-identity presentation (Req 12.1, FE-INV-019, STRIDE).
//
// The Console NEVER renders a raw operator username. The only identity it is
// permitted to surface is the opaque Vault token reference carried on the
// audit row (`operator_token_ref`), and only while authenticated. These pure
// helpers are the single source of truth for that rule so the rendering
// component and the property test (Property 40) share one implementation.

import type { Role } from "@state/session.store";

/** Leading characters of the Vault token reference we surface (short, opaque). */
export const OPERATOR_TOKEN_REF_DISPLAY_LEN = 8;

/** A session is authenticated iff it holds a concrete (non-anonymous) role. */
export function isOperatorAuthenticated(role: Role): boolean {
  return role !== "anonymous";
}

/**
 * Pure operator-identity formatter (Req 12.1 / FE-INV-019 / Property 40).
 *
 * Returns a shortened Vault token reference ONLY while authenticated; returns
 * an empty string when unauthenticated or when no token reference is present.
 * By construction it can never surface a raw username — its only identity
 * input is the opaque Vault token reference, and an unauthenticated session
 * always renders empty.
 */
export function operatorIdentityRef(role: Role, tokenRef: string | null | undefined): string {
  if (!isOperatorAuthenticated(role)) return "";
  if (!tokenRef) return "";
  return tokenRef.slice(0, OPERATOR_TOKEN_REF_DISPLAY_LEN);
}
