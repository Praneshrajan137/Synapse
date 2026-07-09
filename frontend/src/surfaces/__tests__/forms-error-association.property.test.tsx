// Feature: atlas-console-elevation, Property 29: Invalid form input is programmatically associated with its error
//
// Property 29 (Validates: Requirements 9.7) — for every form the Console
// hardened for accessibility (RejectForm, ModifyForm, ScenarioBuilder, Login),
// whenever a field is driven into an invalid state it is BOTH marked invalid
// (`aria-invalid="true"`) AND programmatically associated (`aria-describedby`)
// with a present text error message exposed as an alert. Assistive tech can
// therefore always find and read the error for the field that produced it.
//
// The invariant is asserted against the ACTUAL rendered components, driven to
// their invalid states through real user interaction (empty/whitespace reason,
// malformed JSON, out-of-range numeric input, a rejected sign-in), so it
// verifies the shipped forms rather than a re-implementation.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { HttpError } from "@transport/errors";
import fc from "fast-check";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModifyForm } from "@surfaces/override-cockpit/ModifyForm";
import { RejectForm } from "@surfaces/override-cockpit/RejectForm";
import { ScenarioBuilder } from "@surfaces/twin-lab/ScenarioBuilder";

// Login talks to the transport layer through `useSynapseApi`; stub it so a
// sign-in attempt can be forced to fail with a 401 and drive the form invalid.
const loginMock = vi.hoisted(() => vi.fn());
vi.mock("@hooks/use-synapse-api", () => ({
  useSynapseApi: () => ({ login: loginMock }),
}));
// Toasts are irrelevant here — keep them inert so no <Toaster> is required.
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn() } }));

import { useSessionStore } from "@state/session.store";
import { Login } from "@surfaces/auth/Login";
import { MemoryRouter } from "react-router-dom";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  // Reset the session so Login renders the form (role must be anonymous).
  useSessionStore.setState({
    role: "anonymous",
    accessToken: null,
    operatorTokenRef: null,
    tokenExpiresAt: null,
  });
});

/**
 * The heart of Property 29: an element flagged `aria-invalid="true"` must point
 * (via `aria-describedby`) at a PRESENT element carrying a non-empty text error
 * message exposed to assistive tech as an alert.
 */
function expectAssociatedError(input: HTMLElement): void {
  expect(input.getAttribute("aria-invalid")).toBe("true");

  const describedBy = input.getAttribute("aria-describedby");
  expect(describedBy, "invalid input must reference its error via aria-describedby").toBeTruthy();

  const errorEl = document.getElementById(describedBy!);
  expect(
    errorEl,
    `aria-describedby "${describedBy}" must resolve to a present element`,
  ).not.toBeNull();
  expect(errorEl!.getAttribute("role")).toBe("alert");
  expect(errorEl!.textContent?.trim().length ?? 0).toBeGreaterThan(0);
}

// ─────────────────────────────────────────────────────────────────────────
// RejectForm — an empty / whitespace-only reason is invalid on submit.
// ─────────────────────────────────────────────────────────────────────────

const whitespaceArb = fc.stringOf(fc.constantFrom(" ", "\t", "\n", "\r"), { maxLength: 6 });

describe("RejectForm — Property 29", () => {
  it("marks an empty/whitespace reason invalid and associates the error text", () => {
    fc.assert(
      fc.property(whitespaceArb, (blank) => {
        const { container } = render(<RejectForm onCancel={() => {}} onSubmit={() => {}} />);
        const textarea = container.querySelector("textarea")!;
        fireEvent.change(textarea, { target: { value: blank } });
        fireEvent.submit(container.querySelector("form")!);

        expectAssociatedError(textarea);
        cleanup();
      }),
      { numRuns: 100 },
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────
// ModifyForm — malformed JSON marks the JSON field invalid; a valid object
// with a blank reason marks the reason field invalid. Either way the invalid
// field owns the associated error.
// ─────────────────────────────────────────────────────────────────────────

describe("ModifyForm — Property 29", () => {
  it("marks the malformed-JSON field invalid and associates the error text", () => {
    fc.assert(
      fc.property(fc.string({ maxLength: 20 }), (tail) => {
        const { container } = render(
          <ModifyForm initialAction={{}} onCancel={() => {}} onSubmit={() => {}} />,
        );
        const jsonField = container.querySelector("textarea")!;
        // A leading "@" guarantees the payload is not parseable JSON.
        fireEvent.change(jsonField, { target: { value: `@${tail}` } });
        fireEvent.submit(container.querySelector("form")!);

        expectAssociatedError(jsonField);
        cleanup();
      }),
      { numRuns: 100 },
    );
  });

  it("marks a blank reason invalid (valid JSON object) and associates the error text", () => {
    const { container } = render(
      <ModifyForm initialAction={{ x: 1 }} onCancel={() => {}} onSubmit={() => {}} />,
    );
    // Default text is a valid JSON object; leaving the reason blank is invalid.
    fireEvent.submit(container.querySelector("form")!);
    const reasonInput = container.querySelector('input[type="text"]')!;
    expectAssociatedError(reasonInput as HTMLElement);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// ScenarioBuilder — free-entry numeric inputs out of range are invalid.
// ─────────────────────────────────────────────────────────────────────────

const outOfRangeScenarios = fc.oneof(
  fc.integer({ min: -1000, max: 99 }),
  fc.integer({ min: 5001, max: 100_000 }),
);
const outOfRangeDuration = fc.oneof(
  fc.integer({ min: -500, max: 0 }),
  fc.integer({ min: 25, max: 1000 }),
);

describe("ScenarioBuilder — Property 29", () => {
  it("marks an out-of-range scenario count invalid and associates the error text", () => {
    fc.assert(
      fc.property(outOfRangeScenarios, (n) => {
        render(<ScenarioBuilder onRun={() => {}} />);
        const input = screen.getByRole("spinbutton", { name: /n scenarios/i });
        fireEvent.change(input, { target: { value: String(n) } });
        expectAssociatedError(input);
        cleanup();
      }),
      { numRuns: 100 },
    );
  });

  it("marks an out-of-range duration invalid and associates the error text", () => {
    fc.assert(
      fc.property(outOfRangeDuration, (h) => {
        render(<ScenarioBuilder onRun={() => {}} />);
        const input = screen.getByRole("spinbutton", { name: /duration/i });
        fireEvent.change(input, { target: { value: String(h) } });
        expectAssociatedError(input);
        cleanup();
      }),
      { numRuns: 100 },
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Login — a rejected sign-in (401) marks the credential inputs invalid and
// associates them with the sign-in error message.
// ─────────────────────────────────────────────────────────────────────────

describe("Login — Property 29", () => {
  it("marks the credential inputs invalid and associates the error on a failed sign-in", async () => {
    loginMock.mockRejectedValueOnce(new HttpError(401, "Unauthorized", "unauthorized"));

    const { container } = render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    const operator = screen.getByLabelText(/operator id/i);
    const password = screen.getByLabelText(/password/i);
    fireEvent.change(operator, { target: { value: "ops@synapse.local" } });
    fireEvent.change(password, { target: { value: "wrong-password" } });
    fireEvent.submit(container.querySelector("form")!);

    // The sign-in was attempted and the error alert appears once it settles.
    const alert = await screen.findByRole("alert");
    expect(loginMock).toHaveBeenCalledOnce();
    expect(alert.textContent?.trim().length ?? 0).toBeGreaterThan(0);

    expectAssociatedError(screen.getByLabelText(/operator id/i));
    expectAssociatedError(screen.getByLabelText(/password/i));
  });
});
