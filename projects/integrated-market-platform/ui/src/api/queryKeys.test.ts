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
    expect(queryKeys.liveCanarySnapshot("portfolio", "fp-canary-alt")).toEqual([
      "live",
      "canary-snapshot",
      "portfolio",
      "fp-canary-alt",
    ]);
  });

  it("keeps distinct account keys for the same lane", () => {
    const local = queryKeys.liveCanarySnapshot("portfolio", "fp-canary-local");
    const alt = queryKeys.liveCanarySnapshot("portfolio", "fp-canary-alt");
    expect(local).not.toEqual(alt);
  });

  it("keeps distinct lane keys from legacy unscoped canary key", () => {
    const legacy = ["canary-snapshot"];
    expect(queryKeys.liveCanarySnapshot("account")).not.toEqual(legacy);
  });

  it("isolates demo and paper portfolio keys", () => {
    expect(queryKeys.demoPortfolio).toEqual(["demo", "portfolio"]);
    expect(queryKeys.paperPortfolio).toEqual(["paper", "portfolio"]);
    expect(queryKeys.demoPortfolio).not.toEqual(queryKeys.paperPortfolio);
  });

  it("scopes live reconciliation by account", () => {
    expect(queryKeys.liveCanaryReconciliation("fp-canary-local")).toEqual([
      "live",
      "canary-reconciliation",
      "fp-canary-local",
    ]);
  });

  it("preserves workspace symbol isolation", () => {
    expect(queryKeys.workspaceSqueeze("BIYA", "frozen")).not.toEqual(
      queryKeys.workspaceSqueeze("AAPL", "frozen"),
    );
  });
});
