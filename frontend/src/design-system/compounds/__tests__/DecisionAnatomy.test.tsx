import { ChainIntegrityChip } from "@ds/compounds/ChainIntegrityChip";
import { TwinDivergenceCaveat } from "@ds/compounds/TwinDivergenceCaveat";
import { useFirehoseStore } from "@state/firehose.store";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
// i18next global bootstrap (registers the "common" namespace).
import "@i18n/index";

// ─── ChainIntegrityChip (FE-INV-039) — the tri-state is exhaustive ─────────

describe("ChainIntegrityChip", () => {
  it("verified=true renders the success state with a row-level qualifier (R6.15)", () => {
    render(<ChainIntegrityChip verified={true} />);
    // "Row hash verified", not "Chain verified": the field is a single-row hash
    // recompute and the operator-visible label must not read chain-wide.
    const badge = screen.getByText(/row hash verified/i);
    expect(badge).toBeInTheDocument();
    // Regression guard against the previous chain-wide wording.
    expect(screen.queryByText(/^chain verified$/i)).not.toBeInTheDocument();
    expect(badge.getAttribute("title")).toMatch(/row-level integrity only/i);
  });

  it("verified=false renders tamper evidence with the hash pair", () => {
    render(
      <ChainIntegrityChip
        verified={false}
        prevHash={"a".repeat(64)}
        currentHash={"b".repeat(64)}
      />,
    );
    expect(screen.getByText(/chain mismatch/i)).toBeInTheDocument();
    // The truncated hash pair is exposed for the forensic trail.
    expect(screen.getByText("aaaaaaaa→bbbbbbbb")).toBeInTheDocument();
  });

  it("legacy (null) renders pre-chain — NEVER 'verified'", () => {
    render(<ChainIntegrityChip verified={null} />);
    expect(screen.getByText(/pre-chain/i)).toBeInTheDocument();
    expect(screen.queryByText(/verified/i)).not.toBeInTheDocument();
  });

  it("undefined behaves as legacy (older gateways omit the field)", () => {
    render(<ChainIntegrityChip verified={undefined} />);
    expect(screen.getByText(/pre-chain/i)).toBeInTheDocument();
  });
});

// ─── TwinDivergenceCaveat — trust calibration (I-12) ───────────────────────

describe("TwinDivergenceCaveat", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
  });

  it("renders nothing while the twin is silent", () => {
    const { container } = render(<TwinDivergenceCaveat />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the caveat when the newest twin event breaches its threshold", () => {
    useFirehoseStore.getState().appendTwin(
      {
        agent_name: "demand_prophet",
        kl_divergence: 0.42,
        threshold: 0.1,
        timestamp: 1760000000,
        action: "re_sync_required",
      },
      1,
    );
    render(<TwinDivergenceCaveat />);
    const caveat = screen.getByRole("img");
    expect(caveat).toHaveTextContent(/twin diverging/i);
    expect(caveat.getAttribute("title")).toContain("demand_prophet");
    expect(caveat.getAttribute("title")).toContain("0.420");
  });

  it("a newer in-threshold sample clears the caveat (the twin recovered)", () => {
    const store = useFirehoseStore.getState();
    store.appendTwin({ agent_name: "demand_prophet", kl_divergence: 0.42, threshold: 0.1 }, 1);
    store.appendTwin({ agent_name: "demand_prophet", kl_divergence: 0.02, threshold: 0.1 }, 2);
    const { container } = render(<TwinDivergenceCaveat />);
    expect(container).toBeEmptyDOMElement();
  });

  it("falls back to the canonical 0.1 re-sync threshold when the event has none", () => {
    useFirehoseStore
      .getState()
      .appendTwin({ agent_name: "routing_navigator", kl_divergence: 0.15 }, 1);
    render(<TwinDivergenceCaveat />);
    expect(screen.getByRole("img")).toHaveTextContent(/twin diverging/i);
  });
});
