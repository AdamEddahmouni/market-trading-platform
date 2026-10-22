import { expect, it } from "vitest";
import { flowDetailWindow } from "./flowDetailWindow";

it("includes surrounding observations when replacing an overlapping coarse bucket", () => {
  expect(flowDetailWindow(5000, 10000, [{ time_ms: 0, end_ms: 15000 }]))
    .toEqual({ start: 0, end: 15000 });
});

it("preserves the requested interval without overlapping buckets", () => {
  expect(flowDetailWindow(5000, 10000, [{ time_ms: 10000, end_ms: 15000 }]))
    .toEqual({ start: 5000, end: 10000 });
});
