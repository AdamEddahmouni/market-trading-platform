import { describe, expect, it } from "vitest";
import { matchKnownDataIncident } from "./knownDataIncidents";

describe("knownDataIncidents", () => {
  it("matches epoch 121031 outage tokens without guessing other epochs", () => {
    expect(matchKnownDataIncident("ITEM7_EPOCH_121031_GAP")?.id).toBe("EPOCH_121031");
    expect(matchKnownDataIncident("epoch-121031-unbackfilled")?.title).toMatch(/epoch 121031/i);
    expect(matchKnownDataIncident("STALE_DATA")).toBeNull();
  });
});
