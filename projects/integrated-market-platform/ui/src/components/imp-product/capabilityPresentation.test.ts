import { describe, expect, it } from "vitest";
import { capabilityTone, presentCapabilityStates } from "./capabilityPresentation";

describe("capabilityPresentation", () => {
  it("fails closed on unknown capability states", () => {
    expect(capabilityTone("MYSTERY")).toBe("blocked");
    expect(capabilityTone(undefined)).toBe("blocked");
  });

  it("maps known ready states", () => {
    expect(capabilityTone("READY")).toBe("ok");
    expect(capabilityTone("degraded")).toBe("warn");
  });

  it("presents capability rows for the strip", () => {
    const rows = presentCapabilityStates([
      { capability_id: "paper.order.submit", state: "READY" },
    ]);
    expect(rows[0].tone).toBe("ok");
    expect(rows[0].label).toContain("paper.order.submit");
  });
});
