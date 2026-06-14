import type { DemandForecast } from "@domain/demand-forecast";
import type { FreshnessAlert } from "@domain/freshness-alert";
import type { PricingUpdate } from "@domain/pricing-update";
import { useFirehoseStore } from "@state/firehose.store";
import { LiveMarkets } from "@surfaces/live-markets/LiveMarkets";
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

// jsdom can't compute OKLCH/color-mix contrast — perceptual contrast is the
// design-system APCA/WCAG oracle's job; we assert structural a11y only.
const AXE_OPTS = { rules: { "color-contrast": { enabled: false } } } as const;

// NOTE: useFirehose flushes the store on mount (FE-INV-016 cross-city flush),
// so seeded rows must be appended AFTER render. The store selector drives a
// re-render, so the rows appear without re-mounting the socket.
function seedPricing(...rows: ReadonlyArray<PricingUpdate>) {
  act(() => {
    rows.forEach((r, i) => useFirehoseStore.getState().appendPricing(r, i + 1));
  });
}
function seedFreshness(...rows: ReadonlyArray<FreshnessAlert>) {
  act(() => {
    rows.forEach((r, i) => useFirehoseStore.getState().appendFreshness(r, i + 1));
  });
}

function seedDemand(...rows: ReadonlyArray<DemandForecast>) {
  act(() => {
    rows.forEach((r, i) => useFirehoseStore.getState().appendDemand(r, i + 1));
  });
}

function demand(overrides: Partial<DemandForecast> = {}): DemandForecast {
  return {
    sku_id: "sku_eggs_042",
    store_id: "store_blr_003",
    forecast_timestamp: "2026-06-14T10:02:00+00:00",
    horizons: { "15min": 12, "1h": 40, "24h": 320 },
    lower_90: { "15min": 8, "1h": 33, "24h": 290 },
    upper_90: { "15min": 17, "1h": 48, "24h": 355 },
    confidence: 0.88,
    drift_detected: false,
    ...overrides,
  } as DemandForecast;
}

function pricing(overrides: Partial<PricingUpdate> = {}): PricingUpdate {
  return {
    pricing_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    sku_id: "sku_milk_001",
    category: "dairy",
    base_price: 50,
    multiplier: 1.1,
    final_price: 55,
    is_essential: false,
    elasticity_source: "causal_doubleml",
    timestamp: "2026-06-14T10:00:00+00:00",
    confidence: 0.84,
    ...overrides,
  } as PricingUpdate;
}

function freshness(overrides: Partial<FreshnessAlert> = {}): FreshnessAlert {
  return {
    alert_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    store_id: "store_blr_007",
    sku_id: "sku_bread_009",
    days_to_expiry: 0.5,
    quality_score: 0.62,
    markdown_applied: true,
    markdown_pct: 25,
    fssai_compliant: true,
    timestamp: "2026-06-14T10:01:00+00:00",
    confidence: 0.71,
    ...overrides,
  } as FreshnessAlert;
}

describe("LiveMarkets surface", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
  });

  it("renders empty states before any events arrive", () => {
    render(<LiveMarkets />);
    expect(screen.getByText(/Waiting for live pricing events/)).toBeInTheDocument();
    expect(screen.getByText(/Waiting for live freshness events/)).toBeInTheDocument();
  });

  it("renders pricing + freshness rows from the store", () => {
    render(<LiveMarkets />);
    seedPricing(pricing());
    seedFreshness(freshness());
    expect(screen.getByText("sku_milk")).toBeInTheDocument();
    expect(screen.getByText("sku_brea")).toBeInTheDocument();
    expect(screen.getByText("dairy")).toBeInTheDocument();
  });

  it("marks the I-6 essential cap when an essential SKU hits 1.3×", () => {
    render(<LiveMarkets />);
    seedPricing(
      pricing({
        pricing_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        sku_id: "sku_rice_essential",
        is_essential: true,
        multiplier: 1.3,
        essential_cap_enforced: true,
      }),
    );
    expect(screen.getByText(/1\.30× \(cap\)/)).toBeInTheDocument();
    expect(screen.getByText(/Essential/)).toBeInTheDocument();
    expect(screen.getByText(/Cap/)).toBeInTheDocument();
  });

  it("renders demand forecasts with point values, the conformal band, and a drift badge", () => {
    render(<LiveMarkets />);
    seedDemand(demand({ drift_detected: true }));
    expect(screen.getByText("sku_eggs")).toBeInTheDocument();
    // point forecast (24h ≈ 320) and the 90% band beneath it (290–355)
    expect(screen.getByText("320")).toBeInTheDocument();
    expect(screen.getByText("290–355")).toBeInTheDocument();
    expect(screen.getByTitle(/Distribution drift detected/)).toBeInTheDocument();
  });

  it("renders the FSSAI badge for freshness alerts", () => {
    render(<LiveMarkets />);
    seedFreshness(freshness({ fssai_compliant: false }));
    expect(screen.getByText(/FSSAI ✗/)).toBeInTheDocument();
  });

  it("renders newest-first (most recent pricing row first)", () => {
    render(<LiveMarkets />);
    seedPricing(
      pricing({ pricing_id: "11111111-1111-4111-8111-111111111111", sku_id: "sku_old_000" }),
      pricing({ pricing_id: "22222222-2222-4222-8222-222222222222", sku_id: "sku_new_111" }),
    );
    const cells = screen.getAllByText(/^sku_(old|new)/);
    expect(cells[0]).toHaveTextContent("sku_new");
  });

  it("has no axe violations", async () => {
    const { container } = render(<LiveMarkets />);
    seedPricing(pricing());
    seedFreshness(freshness());
    expect(await axe(container, AXE_OPTS)).toHaveNoViolations();
  });
});
