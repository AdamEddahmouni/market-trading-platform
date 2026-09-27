import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchScreenerOptions } from "./screenerOptions";

const contract = (extra: Record<string, unknown> = {}) => ({
  option_id: "AAPL20261002C00250000", provider_symbol: "AAPL261002C00250000", type: "CALL", expiration: "2026-10-02", dte: 5, strike: 250,
  bid: 1.1, ask: 1.2, mid: 1.15, spread: 0.1, spread_pct: 8.7, last: null, volume: 0, open_interest: null, volume_oi_ratio: null,
  iv: 0.29, delta: 0.5, gamma: null, theta: null, vega: null, rho: null, last_trade_at: null, quality_flags: [], ...extra,
});
const payload = (extra: Record<string, unknown> = {}) => ({
  schema_version: "screener-options/1.0.0", generated_at: "2026-09-27T16:00:00Z", instrument_id: "AAPL", universe: "US_EQUITIES",
  symbol: "AAPL", view: "chain", market_session: "CLOSED", capability: {}, provider: { id: "options.finviz.elite_export", label: "Finviz Elite", delivery: "SNAPSHOT" },
  state: "MARKET_CLOSED", reason: "OPTIONS_MARKET_CLOSED", clock: null, underlying: null, completeness: null, quality_flags: [], fields_supplied: null,
  expirations: [{ expiration: "2026-10-02", dte: 5, contracts: 1, strikes: 1, call_volume: 0, put_volume: null }],
  selected_expiration: "2026-10-02", summary: null, expiry_summary: null, contracts: [contract()], ...extra,
});
const respond = (body: unknown) => vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })));

afterEach(() => vi.unstubAllGlobals());

describe("S7 options API contract", () => {
  it("requests one selected instrument by canonical id, universe, view, and expiry", async () => {
    respond(payload());
    const result = await fetchScreenerOptions("AAPL", { universe: "US_EQUITIES", view: "chain", expiration: "2026-10-02" });
    expect(result.contracts[0].volume).toBe(0);
    expect(result.contracts[0].open_interest).toBeNull();
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toBe("/screener/options?instrument=AAPL&universe=US_EQUITIES&view=chain&expiration=2026-10-02");
  });

  it("rejects a response for another instrument, universe, or view", async () => {
    respond(payload({ instrument_id: "NVDA" }));
    await expect(fetchScreenerOptions("AAPL", { universe: "US_EQUITIES", view: "chain" })).rejects.toThrow("OPTIONS_IDENTITY_MISMATCH");
    respond(payload({ universe: "US_ETFS" }));
    await expect(fetchScreenerOptions("AAPL", { universe: "US_EQUITIES", view: "chain" })).rejects.toThrow("OPTIONS_IDENTITY_MISMATCH");
    respond(payload());
    await expect(fetchScreenerOptions("AAPL", { universe: "US_EQUITIES", view: "summary" })).rejects.toThrow("OPTIONS_IDENTITY_MISMATCH");
  });

  it("rejects malformed values instead of rendering them", async () => {
    const bad = [
      payload({ contracts: [contract({ iv: "0.29" })] }), payload({ contracts: [contract({ volume: -1 })] }),
      payload({ contracts: [contract({ strike: "250" })] }), payload({ contracts: [contract({ delta: 3 })] }),
      payload({ contracts: [contract({ iv: 0 })] }), payload({ contracts: [contract({ expiration: "2026-10-16" })] }),
      payload({ selected_expiration: "2026-09-25" }), payload({ state: "LIVE" }), payload({ schema_version: "screener-options/2.0.0" }),
    ];
    for (const body of bad) {
      respond(body);
      await expect(fetchScreenerOptions("AAPL", { universe: "US_EQUITIES", view: "chain" })).rejects.toThrow();
    }
  });
});
