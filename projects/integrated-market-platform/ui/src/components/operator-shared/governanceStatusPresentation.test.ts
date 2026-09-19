import { describe, expect, it } from "vitest";
import { buildGovernanceFacts } from "./governanceStatusPresentation";

describe("governanceStatusPresentation", () => {
  it("never claims Item 9 calibrated without capability state", () => {
    const facts = buildGovernanceFacts({
      asOf: {
        mode: "PAPER",
        as_of_time: "2026-01-01T00:00:00Z",
        timezone: "UTC",
        execution_authority: "PAPER_ONLY",
        execution_mode: "INTERNAL_SIMULATION",
      },
    });
    const item9 = facts.find((row) => row.id === "item9-calibration");
    expect(item9?.value).toMatch(/not on API/i);
    expect(item9?.value).not.toMatch(/3\/3/);
  });
});
