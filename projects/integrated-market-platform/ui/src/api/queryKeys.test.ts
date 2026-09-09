import { describe, expect, it } from "vitest";
import { queryKeys } from "./hooks";

describe("queryKeys account isolation", () => {
  it("scopes canary snapshot keys under live mode with lane and account identity", () => {
    expect(queryKeys.liveCanarySnapshot("squeeze")).toEqual([
      "live",
      "canary-snapshot",
      "squeeze",
      "fp-canary-local",
    ]);
  });

  it("keeps distinct account keys for the same lane", () => {
    const local = queryKeys.liveCanarySnapshot("portfolio", "fp-canary-local");
    const alt = queryKeys.liveCanarySnapshot("portfolio", "fp-canary-alt");
    expect(local).not.toEqual(alt);
  });

  it("isolates demo and paper portfolio keys", () => {
    expect(queryKeys.demoPortfolio).toEqual(["demo", "portfolio"]);
    expect(queryKeys.paperPortfolio).toEqual(["paper", "portfolio"]);
    expect(queryKeys.demoPortfolio).not.toEqual(queryKeys.paperPortfolio);
  });

  it("preserves workspace symbol isolation", () => {
    expect(queryKeys.workspaceSqueeze("BIYA", "frozen")).not.toEqual(
      queryKeys.workspaceSqueeze("AAPL", "frozen"),
    );
  });

  it("aligns G14 product keys with canonical compact helpers", () => {
    expect(queryKeys.optionsProduct("AAPL", "PAPER")).toEqual(["op", "AAPL", "PAPER", "u", "fixture"]);
    expect(queryKeys.futuresProduct("ES202512", "PAPER")).toEqual(["fp", "ES202512", "PAPER", "u", "fixture"]);
  });
});
