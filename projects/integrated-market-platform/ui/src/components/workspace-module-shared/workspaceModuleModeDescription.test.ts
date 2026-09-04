import { describe, expect, it } from "vitest";
import { workspaceModuleModeDescription } from "./workspaceModuleModeDescription";

const BASE = "Fixture-backed lane evidence.";

describe("workspaceModuleModeDescription", () => {
  it("returns base description unchanged in Demo mode", () => {
    expect(workspaceModuleModeDescription(BASE, "DEMO", "squeeze")).toBe(BASE);
  });

  it("appends squeeze-specific Paper hint", () => {
    expect(workspaceModuleModeDescription(BASE, "PAPER", "squeeze")).toContain(
      "Preview squeeze ignition",
    );
  });

  it("appends order-flow-specific Live hint", () => {
    expect(workspaceModuleModeDescription(BASE, "LIVE", "order-flow")).toContain(
      "broker-reported order flow",
    );
  });

  it("falls back to default Paper hint for overview", () => {
    expect(workspaceModuleModeDescription(BASE, "PAPER", "overview")).toContain(
      "Route lane evidence into paper simulation",
    );
  });

  it("falls back to default Live hint for overview", () => {
    expect(workspaceModuleModeDescription(BASE, "LIVE", "overview")).toContain(
      "Broker-observed context without execution authority",
    );
  });
});
