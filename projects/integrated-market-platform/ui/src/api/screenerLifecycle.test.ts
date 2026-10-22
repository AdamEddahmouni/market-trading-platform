import { afterEach, describe, expect, it, vi } from "vitest";
import { SchemaMismatchError } from "./fetchJson";
import { TradeLifecycleListSchema, TradeLifecycleSchema, tradeLifecycle, tradeLifecycles } from "./screenerLifecycle";
import { breachedPosition, closedEpisode, detailOf, lifecycle, lifecycleList, openPosition } from "../components/screener/lifecycle/lifecycleFixture";

const respond = (body: unknown) => vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })));

afterEach(() => vi.unstubAllGlobals());

describe("trade lifecycle contract", () => {
  it("accepts every lifecycle shape the server projects", () => {
    for (const value of [lifecycle(), openPosition(), breachedPosition(), closedEpisode(), detailOf(openPosition()), detailOf(closedEpisode())]) {
      expect(TradeLifecycleSchema.safeParse(value).success).toBe(true);
    }
    expect(TradeLifecycleListSchema.safeParse(lifecycleList({ selected: [lifecycle()], active_managed: [openPosition()], recent_closed: [closedEpisode()] })).success).toBe(true);
  });

  it("keeps absent fills, exits, stops and P&L null rather than zero", () => {
    const flat = TradeLifecycleSchema.parse(lifecycle());
    expect([flat.entry.fill, flat.entry.average_price_minor, flat.exit.fill, flat.risk_control.stop, flat.pnl.realized_minor, flat.pnl.unrealized_minor])
      .toEqual([null, null, null, null, null, null]);
    expect(TradeLifecycleSchema.safeParse({ ...lifecycle(), pnl: { ...lifecycle().pnl, unrealized_minor: undefined } }).success).toBe(false);
  });

  it.each([
    ["stage", { stage: "FILLED" }],
    ["entry status", { entry: { ...lifecycle().entry, status: "OPEN" } }],
    ["exit status", { exit: { ...lifecycle().exit, status: "DONE" } }],
    ["decision action", { decision: { ...lifecycle().decision!, action_state: "BUY" } }],
    ["fill kind", { entry: { ...openPosition().entry, fill: { ...openPosition().entry.fill!, kind: "LIVE_FILL" } } }],
    ["market-truth flag", { entry: { ...openPosition().entry, fill: { ...openPosition().entry.fill!, is_market_truth: true } } }],
    ["risk model", { risk_control: { ...lifecycle().risk_control, model: "gpt" } }],
    ["live capital", { experiment: { ...detailOf(lifecycle()).experiment!, live_capital: true } }],
  ])("rejects an unknown %s", (_, patch) => {
    expect(TradeLifecycleSchema.safeParse({ ...lifecycle(), ...patch }).success).toBe(false);
  });

  it("requests the list and one detail with the run identity", async () => {
    respond(lifecycleList());
    await tradeLifecycles("run 1");
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain("/screener/trade-lifecycles?run_id=run%201");
    await tradeLifecycles(null);
    expect(String(vi.mocked(fetch).mock.calls[1][0]).endsWith("/screener/trade-lifecycles")).toBe(true);
    respond(detailOf(openPosition()));
    await tradeLifecycle("TE-aapl-1", "run-1");
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain("/screener/trade-lifecycles/TE-aapl-1?run_id=run-1");
  });

  it("fails visibly on a malformed payload", async () => {
    respond({ ...lifecycleList(), execution: "LIVE" });
    await expect(tradeLifecycles()).rejects.toBeInstanceOf(SchemaMismatchError);
  });
});
