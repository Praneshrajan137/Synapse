// Feature: atlas-console-elevation, Property 40: Operator identity is never a raw username
//
// Property 40 (Validates: Requirements 12.1) — for ANY session, the rendered
// operator identity produced by `operatorIdentityRef`:
//   • is EMPTY while unauthenticated (role === "anonymous"), and
//   • while authenticated is ONLY ever a prefix of the opaque Vault token
//     reference (never a raw username), bounded to the display length.
//
// The helper's signature makes the invariant structural: its only identity
// input is the Vault `tokenRef`, so a raw username has no channel through which
// to leak. This test pins that: even when a distinct "username" value is thrown
// into the mix, the rendered identity never reflects it — it is always derived
// solely from the token reference.

import {
  OPERATOR_TOKEN_REF_DISPLAY_LEN,
  isOperatorAuthenticated,
  operatorIdentityRef,
} from "@lib/operator-identity";
import type { Role } from "@state/session.store";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const ROLES: readonly Role[] = ["viewer", "ops", "engineer", "admin", "anonymous"];
const roleArb: fc.Arbitrary<Role> = fc.constantFrom(...ROLES);

// A Vault token reference looks like an opaque handle, e.g. "hvs.CAESIJ...".
const tokenRefArb: fc.Arbitrary<string | null | undefined> = fc.oneof(
  fc.string({ minLength: 0, maxLength: 40 }),
  fc.constant(null),
  fc.constant(undefined),
  fc.constant(""),
);

// A raw username is exactly the thing the Console must NEVER surface. We use a
// dedicated marker prefix so we can assert it never appears in the output.
const usernameArb: fc.Arbitrary<string> = fc
  .string({ minLength: 1, maxLength: 20 })
  .map((s) => `operator_${s}`);

describe("operatorIdentityRef — Property 40: identity is never a raw username", () => {
  it("renders EMPTY while unauthenticated, regardless of any token reference", () => {
    fc.assert(
      fc.property(tokenRefArb, (tokenRef) => {
        expect(operatorIdentityRef("anonymous", tokenRef)).toBe("");
      }),
      { numRuns: 200 },
    );
  });

  it("renders ONLY a prefix of the Vault token reference (never a username)", () => {
    fc.assert(
      fc.property(roleArb, tokenRefArb, usernameArb, (role, tokenRef, username) => {
        const rendered = operatorIdentityRef(role, tokenRef);

        // The rendered identity is always a prefix of the token reference
        // (empty string is a prefix of everything), bounded by the display len.
        const ref = tokenRef ?? "";
        expect(ref.startsWith(rendered)).toBe(true);
        expect(rendered.length).toBeLessThanOrEqual(OPERATOR_TOKEN_REF_DISPLAY_LEN);

        // The raw username can never be the rendered identity: it carries a
        // marker prefix that never originates from the token-ref channel.
        expect(rendered).not.toBe(username);

        // Unauthenticated sessions always render empty.
        if (!isOperatorAuthenticated(role)) {
          expect(rendered).toBe("");
        }
      }),
      { numRuns: 300 },
    );
  });

  it("is a pure function of (role, tokenRef): equals the token-ref prefix when authenticated", () => {
    fc.assert(
      fc.property(roleArb, tokenRefArb, (role, tokenRef) => {
        const expected =
          isOperatorAuthenticated(role) && tokenRef
            ? tokenRef.slice(0, OPERATOR_TOKEN_REF_DISPLAY_LEN)
            : "";
        expect(operatorIdentityRef(role, tokenRef)).toBe(expected);
      }),
      { numRuns: 200 },
    );
  });
});
