import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useAvailableFilters, useScreenSnapshot } from "./screenerRenderMemo";
import type { ScreenerConfig } from "../../api/screener";

const catalog = [{ field: "price", label: "Price", unit: "USD", type: "number", category: "Market", availability: "SNAPSHOT", operators: ["gt"], universes: ["US_EQUITIES", "CRYPTO"] }] as ScreenerConfig["catalog"];
const input = () => ({ filters: [], view: "Overview", sort: "price", descending: true,
  keys: ["price", "symbol"], visibility: { price: true, symbol: false },
  order: ["symbol", "price", "removed"], sizing: { price: 90, removed: 10 }, pinning: { left: ["symbol", "removed"] } });

describe("production Screener render memoization", () => {
  it("keeps filter identity stable and refreshes labels and universe membership", () => {
    const fields = { price: { label: "Spot Price", unit: "USDT" } };
    const { result, rerender } = renderHook(({ entries, universe, caps }) => useAvailableFilters(entries, universe, caps),
      { initialProps: { entries: catalog, universe: "US_EQUITIES", caps: fields } });
    const first = result.current;
    expect(first[0].label).toBe("Spot Price");
    rerender({ entries: catalog, universe: "US_EQUITIES", caps: fields });
    expect(result.current).toBe(first);
    rerender({ entries: catalog, universe: "FUTURES", caps: fields });
    expect(result.current).toEqual([]);
    rerender({ entries: catalog, universe: "CRYPTO", caps: { price: { label: "Crypto Price", unit: "USDT" } } });
    expect(result.current[0].label).toBe("Crypto Price");
    rerender({ entries: [{ ...catalog[0], field: "bid", label: "Bid" }], universe: "CRYPTO", caps: fields });
    expect(result.current[0].field).toBe("bid");
  });

  it("serializes real screen state and invalidates every snapshot dependency", () => {
    const initial = input();
    const { result, rerender } = renderHook(useScreenSnapshot, { initialProps: initial });
    expect(JSON.parse(result.current.serialized)).toEqual({ filters: [], view: "Overview", sort: { field: "price", descending: true },
      columns: { visible: ["price"], order: ["symbol", "price"], widths: { price: 90 }, pinned: ["symbol"] } });
    const first = result.current.snapshot;
    rerender(initial);
    expect(result.current.snapshot).toBe(first);
    const changes = [
      { filters: [{ id: "p", field: "price", operator: "gt", value: 2 }] },
      { view: "Custom" }, { sort: "symbol" }, { descending: false }, { keys: ["symbol"] },
      { visibility: { price: false, symbol: true } }, { order: ["price", "symbol"] },
      { sizing: { price: 120, removed: 10 } }, { pinning: { left: ["price"] } },
    ];
    for (const change of changes) {
      rerender(initial);
      const before = result.current.serialized;
      rerender({ ...initial, ...change });
      expect(result.current.serialized).not.toBe(before);
      expect(JSON.stringify(result.current.snapshot())).toBe(result.current.serialized);
    }
  });
});
