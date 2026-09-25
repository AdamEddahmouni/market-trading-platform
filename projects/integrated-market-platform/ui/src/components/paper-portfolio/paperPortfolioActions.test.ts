import { describe, expect, it } from "vitest";
import { buildPositionTradeDraft } from "./paperPortfolioActions";

describe("buildPositionTradeDraft", () => {
  it("prefills add, reduce, and close for a long position", () => {
    const position = { instrumentId: "AAPL", side: "long" as const, quantity: 12 };
    expect(buildPositionTradeDraft(position, "add", 100)).toMatchObject({ instrumentId: "AAPL", side: "BUY", quantity: 1, orderType: "MARKET" });
    expect(buildPositionTradeDraft(position, "reduce", 100)).toMatchObject({ side: "SELL", quantity: 1 });
    expect(buildPositionTradeDraft(position, "close", 100)).toMatchObject({ side: "SELL", quantity: 12 });
  });

  it("uses the opposite side for short reduction and hides an oversized close", () => {
    const position = { instrumentId: "NVDA", side: "short" as const, quantity: 120 };
    expect(buildPositionTradeDraft(position, "add", 100)).toMatchObject({ side: "SELL", quantity: 1 });
    expect(buildPositionTradeDraft(position, "reduce", 100)).toMatchObject({ side: "BUY", quantity: 1 });
    expect(buildPositionTradeDraft(position, "close", 100)).toBeNull();
  });

  it("does not invent a trade from flat or malformed exposure", () => {
    expect(buildPositionTradeDraft({ instrumentId: "AAPL", side: "flat", quantity: 0 }, "close", 100)).toBeNull();
    expect(buildPositionTradeDraft({ instrumentId: "AAPL", side: "long", quantity: 1.5 }, "close", 100)).toBeNull();
  });
});
