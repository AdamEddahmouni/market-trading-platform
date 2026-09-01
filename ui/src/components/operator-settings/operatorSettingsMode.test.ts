import { describe, expect, it } from "vitest";
import {
  canMutateOperatorSettings,
  operatorSettingsRestrictionNote,
} from "./operatorSettingsMode";

describe("operatorSettingsMode", () => {
  it("permits mutations only in Paper mode", () => {
    expect(canMutateOperatorSettings("DEMO")).toBe(false);
    expect(canMutateOperatorSettings("PAPER")).toBe(true);
    expect(canMutateOperatorSettings("LIVE")).toBe(false);
  });

  it("returns restriction notes for Demo and Live", () => {
    expect(operatorSettingsRestrictionNote("DEMO")).toMatch(/exploration only/i);
    expect(operatorSettingsRestrictionNote("PAPER")).toBeNull();
    expect(operatorSettingsRestrictionNote("LIVE")).toMatch(/read-only/i);
  });
});
