import { describe, expect, it } from "vitest";
import { parseLimitPriceMinor } from "./paperOrderTerms";

describe("parseLimitPriceMinor", () => {
  it("converts a positive dollar price to exact minor units", () => {
    expect(parseLimitPriceMinor("12")).toBe(1200);
    expect(parseLimitPriceMinor("12.3")).toBe(1230);
    expect(parseLimitPriceMinor("12.34")).toBe(1234);
    expect(parseLimitPriceMinor("0.01")).toBe(1);
  });

  it("rejects zero, excess precision, and malformed values", () => {
    for (const value of ["", "0", "0.00", "-1", "1.234", "1e3", "1.", " 1", "999999999999999999"]) {
      expect(parseLimitPriceMinor(value)).toBeNull();
    }
  });
});
