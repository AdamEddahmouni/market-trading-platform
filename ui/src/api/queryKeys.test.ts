import { describe, expect, it } from "vitest";
import { queryKeys } from "./hooks";

describe("queryKeys live canary isolation", () => {
  it("scopes canary snapshot keys under live mode with lane identity", () => {
    expect(queryKeys.liveCanarySnapshot("squeeze")).toEqual(["live", "canary-snapshot", "squeeze"]);
    expect(queryKeys.liveCanarySnapshot("portfolio")).toEqual(["live", "canary-snapshot", "portfolio"]);
  });

  it("keeps distinct lane keys from legacy unscoped canary key", () => {
    const legacy = ["canary-snapshot"];
    expect(queryKeys.liveCanarySnapshot("account")).not.toEqual(legacy);
  });

  it("preserves workspace symbol isolation", () => {
    expect(queryKeys.workspaceSqueeze("BIYA", "frozen")).not.toEqual(
      queryKeys.workspaceSqueeze("AAPL", "frozen"),
    );
  });
});
