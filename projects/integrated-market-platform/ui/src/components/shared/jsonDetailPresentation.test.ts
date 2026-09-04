import { describe, expect, it } from "vitest";
import { flattenJsonDetail } from "./jsonDetailPresentation";

describe("flattenJsonDetail", () => {
  it("formats primitives and nested objects for display", () => {
    const rows = flattenJsonDetail({
      status: "AUTHORIZED",
      nested: { count: 2, enabled: true },
      items: ["a"],
    });
    expect(rows.some((row) => row.label === "Status" && row.value === "AUTHORIZED")).toBe(true);
    expect(rows.some((row) => row.label === "Nested" && row.nested?.length)).toBe(true);
    expect(rows.some((row) => row.label === "Items" && row.value.includes("1 item"))).toBe(true);
  });
});
