import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FuturesProductSurface } from "./FuturesProductSurface";

describe("FuturesProductSurface", () => {
  it("marks family reference as non-actionable", () => {
    render(
      <FuturesProductSurface
        mode="PAPER"
        instrumentId="ES"
        product={{
          schema_version: "g14.product.v1",
          domain: "futures",
          instrument_id: "ES",
          mode: "PAPER",
          account_id: "paper-local",
          as_of_context: {
            mode: "PAPER",
            as_of_time: "2026-01-01T00:00:00Z",
            timezone: "UTC",
          },
          status: "UNSUPPORTED_INSTRUMENT",
          reason: "NON_EXECUTABLE:FUTURE_FAMILY",
          execution_available: false,
          runtime: { status: "UNSUPPORTED_INSTRUMENT", instrument_kind: "FUTURE_FAMILY" },
          identity: { instrument_kind: "FUTURE_FAMILY" },
          exposure: { margin: { state: "NOT_APPLICABLE" } },
          position: null,
          orders: [],
        }}
      />,
    );
    expect(screen.getByText(/not executable/i)).toBeTruthy();
  });

  it("shows margin missing state without inventing broker margin", () => {
    render(
      <FuturesProductSurface
        mode="PAPER"
        instrumentId="ES202512"
        product={{
          schema_version: "g14.product.v1",
          domain: "futures",
          instrument_id: "ES202512",
          mode: "PAPER",
          account_id: "paper-local",
          as_of_context: {
            mode: "PAPER",
            as_of_time: "2026-01-01T00:00:00Z",
            timezone: "UTC",
          },
          status: "AVAILABLE",
          execution_available: true,
          runtime: { status: "AVAILABLE", instrument_kind: "FUTURE_CONTRACT" },
          identity: { instrument_kind: "FUTURE_CONTRACT", multiplier: "50" },
          exposure: {
            notional: "275000",
            margin: { state: "MARGIN_MISSING", reason: "NO_AUTHORITATIVE_MARGIN_FACTS" },
            cash_debit_semantics: "MARGIN_NOT_NOTIONAL",
          },
          position: null,
          orders: [],
        }}
      />,
    );
    expect(screen.getByText(/MARGIN_MISSING/i)).toBeTruthy();
    expect(screen.getByText(/275000/)).toBeTruthy();
  });
});
