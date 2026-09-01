import { describe, expect, it } from "vitest";
import { MODE_LAUNCH_ORDER, modeMetadata } from "./modeMetadata";

describe("modeMetadata", () => {
  it("defines launch metadata for every mode without authority logic", () => {
    for (const mode of MODE_LAUNCH_ORDER) {
      const meta = modeMetadata(mode);
      expect(meta.id).toBe(mode);
      expect(meta.label.length).toBeGreaterThan(0);
      expect(meta.launchCopy.length).toBeGreaterThan(0);
      expect(meta.cssToken).toBeTruthy();
    }
  });
});
