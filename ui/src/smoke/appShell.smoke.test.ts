/**
 * High-value application smoke coverage via Vitest + Testing Library.
 * Browser E2E (Playwright) deferred: no harness, backend coupling, and App.test.tsx
 * already exercises route rendering with fetch mocks at integration depth.
 */
import { describe, expect, it } from "vitest";
import { queryKeys } from "../api/hooks";

describe("application smoke invariants", () => {
  it("live canary keys are mode-scoped", () => {
    expect(queryKeys.liveCanarySnapshot("now")[0]).toBe("live");
  });

  it("paper portfolio key is isolated from live canary", () => {
    expect(queryKeys.paperPortfolio[0]).toBe("paper");
    expect(queryKeys.paperPortfolio).not.toEqual(queryKeys.liveCanarySnapshot());
  });
});
