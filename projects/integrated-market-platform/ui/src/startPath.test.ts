import { describe, expect, it } from "vitest";
import { redirectFreshVisitToScreener, startPath } from "./startPath";

describe("startPath", () => {
  it("sends a fresh visit to / straight to the Screener, keeping the query", () => {
    expect(startPath("/", "")).toBe("/screener");
    expect(startPath("/", "?universe=US_ETFS&q=SPY")).toBe("/screener?universe=US_ETFS&q=SPY");
  });

  it("leaves every other path alone", () => {
    expect(startPath("/screener", "")).toBeNull();
    expect(startPath("/control", "")).toBeNull();
    expect(startPath("/workspace/AAPL", "")).toBeNull();
  });

  it("rewrites the address without adding a history entry", () => {
    window.history.pushState({}, "", "/?q=NVDA");
    const before = window.history.length;
    redirectFreshVisitToScreener();
    expect(window.location.pathname).toBe("/screener");
    expect(window.location.search).toBe("?q=NVDA");
    expect(window.history.length).toBe(before);
    window.history.pushState({}, "", "/");
  });
});
