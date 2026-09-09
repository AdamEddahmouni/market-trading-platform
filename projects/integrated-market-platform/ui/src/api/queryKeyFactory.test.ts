import { describe, expect, it } from "vitest";
import {
  decodeInstrumentRouteParam,
  encodeInstrumentRouteParam,
  selectionDisabledReason,
  type CanonicalSelectorResult,
} from "./instrumentIdentity";
import { canonicalQueryKey, queryKeyFactory } from "./queryKeyFactory";

describe("queryKeyFactory isolation", () => {
  it("isolates same equity across two accounts", () => {
    expect(queryKeyFactory.paperPortfolio("PAPER", "acct-a")).not.toEqual(
      queryKeyFactory.paperPortfolio("PAPER", "acct-b"),
    );
  });

  it("isolates Demo vs Paper mode", () => {
    expect(queryKeyFactory.optionsProduct("AAPL", "DEMO")).not.toEqual(
      queryKeyFactory.optionsProduct("AAPL", "PAPER"),
    );
  });

  it("isolates providers for the same instrument", () => {
    expect(
      canonicalQueryKey("quote", { instrumentId: "AAPL", provider: "IBKR" }),
    ).not.toEqual(canonicalQueryKey("quote", { instrumentId: "AAPL", provider: "MOOMOO" }));
  });

  it("isolates as_of historical queries", () => {
    expect(
      queryKeyFactory.workspaceLane("history", "AAPL", "PAPER", "acct", "fixture", "T1"),
    ).not.toEqual(
      queryKeyFactory.workspaceLane("history", "AAPL", "PAPER", "acct", "fixture", "T2"),
    );
  });

  it("isolates equity vs option contract", () => {
    expect(queryKeyFactory.optionsProduct("AAPL", "PAPER")).not.toEqual(
      queryKeyFactory.optionsProduct("NVDA20260815C00130000", "PAPER"),
    );
  });

  it("isolates future family vs contract", () => {
    expect(queryKeyFactory.futuresProduct("ES", "PAPER")).not.toEqual(
      queryKeyFactory.futuresProduct("ES202512", "PAPER"),
    );
  });

  it("isolates BTC/USD vs BTC/USDT", () => {
    expect(queryKeyFactory.workspaceLane("crypto", "BTCUSD", "PAPER")).not.toEqual(
      queryKeyFactory.workspaceLane("crypto", "BTCUSDT", "PAPER"),
    );
  });

  it("is deterministic for identical inputs", () => {
    const left = queryKeyFactory.futuresProduct("ES202512", "PAPER", "acct-1");
    const right = queryKeyFactory.futuresProduct("ES202512", "PAPER", "acct-1");
    expect(left).toEqual(right);
  });

  it("stable param ordering cannot alter semantically identical key", () => {
    const left = canonicalQueryKey("probe", {
      params: { b: "2", a: "1" },
    });
    const right = canonicalQueryKey("probe", {
      params: { a: "1", b: "2" },
    });
    expect(left).toEqual(right);
  });
});

describe("instrumentIdentity serialization", () => {
  it("round-trips canonical reference", () => {
    const sample = "NVDA20260815C00130000";
    expect(decodeInstrumentRouteParam(encodeInstrumentRouteParam(sample))).toBe(sample);
  });

  it("marks future family as non-executable", () => {
    const result: CanonicalSelectorResult = {
      instrument_id: "ES",
      asset_class: "FUTURE",
      instrument_kind: "FUTURE_FAMILY",
      display_label: "ES",
      tradability: "REFERENCE_ONLY",
      execution_eligible: false,
      selection_action: "OPEN_FUTURE_FAMILY_REFERENCE",
      provider_availability: "FIXTURE_CATALOG",
      metadata: {},
    };
    expect(selectionDisabledReason(result)).toMatch(/reference-only/i);
  });
});
