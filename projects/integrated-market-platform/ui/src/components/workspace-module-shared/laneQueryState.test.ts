import { describe, expect, it } from "vitest";
import { deriveLaneQueryState, modeSpecificEmptyMessage } from "./laneQueryState";

describe("deriveLaneQueryState", () => {
  it("returns loading phase while query is loading", () => {
    expect(deriveLaneQueryState({ isLoading: true, isError: false })).toEqual({
      phase: "loading",
      message: "Loading lane evidence…",
    });
  });

  it("returns degraded ready when available is false", () => {
    expect(
      deriveLaneQueryState({
        isLoading: false,
        isError: false,
        data: { available: false, reason: "NO_FIXTURE" },
      }),
    ).toMatchObject({
      phase: "ready",
      message: "NO_FIXTURE",
      degraded: true,
      stale: false,
    });
  });
});

describe("modeSpecificEmptyMessage", () => {
  it("uses Demo replay wording for empty state", () => {
    expect(modeSpecificEmptyMessage("DEMO", "empty")).toMatch(/fixture/i);
  });

  it("uses Live broker wording for error state", () => {
    expect(modeSpecificEmptyMessage("LIVE", "error")).toMatch(/broker/i);
  });
});
