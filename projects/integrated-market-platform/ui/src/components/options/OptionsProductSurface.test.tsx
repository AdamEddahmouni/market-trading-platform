import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { OptionsProductSurface } from "./OptionsProductSurface";

const baseProduct = {
  schema_version: "g14.product.v1",
  domain: "options",
  instrument_id: "NVDA20260815C00130000",
  mode: "PAPER",
  account_id: "paper-local",
  as_of_context: {
    mode: "PAPER" as const,
    as_of_time: "2026-01-01T00:00:00Z",
    timezone: "UTC",
  },
  status: "AVAILABLE",
  reason: null,
  execution_available: true,
  runtime: {
    status: "AVAILABLE",
    instrument_id: "NVDA20260815C00130000",
    instrument_kind: "OPTION_CONTRACT",
  },
  identity: {
    expiry: "2026-08-15",
    strike: "130",
    right: "call",
    multiplier: "100",
  },
  analytics: {
    iv: null,
    greeks: { delta: null },
    open_interest: null,
    volume: null,
  },
  chain_status: "EMPTY",
  position: null,
  orders: [],
  short_open_risk: null,
};

describe("OptionsProductSurface", () => {
  it("renders unknown IV/Greeks instead of zero", () => {
    render(
      <OptionsProductSurface mode="PAPER" instrumentId="NVDA20260815C00130000" product={baseProduct} />,
    );
    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    expect(screen.queryByText("0")).toBeNull();
  });

  it("shows EMPTY chain distinct from unavailable copy", () => {
    render(
      <OptionsProductSurface mode="PAPER" instrumentId="NVDA20260815C00130000" product={baseProduct} />,
    );
    expect(screen.getByText(/EMPTY/i)).toBeTruthy();
  });

  it("does not expose Live submit", () => {
    render(
      <OptionsProductSurface
        mode="LIVE"
        instrumentId="NVDA20260815C00130000"
        product={baseProduct}
        paperActionsPermitted
      />,
    );
    expect(screen.getByText(/observational only/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /preview paper order/i })).toBeNull();
  });
});
