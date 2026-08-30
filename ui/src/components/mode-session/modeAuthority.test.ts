import { describe, expect, it } from "vitest";
import type { AsOfContext } from "../../api/client";
import { canUsePaperActions, evaluateModeContext } from "./modeAuthority";
import type { Mode } from "./types";

function context(overrides: Partial<AsOfContext> = {}): AsOfContext {
  return {
    mode: "REPLAY",
    as_of_time: "2026-08-30T12:00:00Z",
    timezone: "America/New_York",
    ...overrides,
  };
}

describe("mode authority", () => {
  it.each([
    [
      "DEMO",
      context({
        data_mode: "FIXTURE_REPLAY",
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
      }),
    ],
    [
      "PAPER",
      context({
        data_mode: "LIVE_OBSERVATIONAL",
        execution_mode: "INTERNAL_SIMULATION",
        execution_authority: "PAPER_ONLY",
      }),
    ],
    [
      "LIVE",
      context({
        data_mode: "LIVE_OBSERVATIONAL",
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
      }),
    ],
  ] satisfies Array<[Mode, AsOfContext]>)(
    "accepts compatible %s context",
    (mode, backendContext) => {
      expect(evaluateModeContext(mode, backendContext)).toMatchObject({
        status: "compatible",
        paperActionsPermitted: mode === "PAPER",
      });
    },
  );

  it("fails closed when selected Paper disagrees with backend context", () => {
    expect(
      evaluateModeContext(
        "PAPER",
        context({
          data_mode: "FIXTURE_REPLAY",
          execution_mode: "NONE",
          execution_authority: "BLOCKED",
        }),
      ),
    ).toMatchObject({ status: "mismatch", paperActionsPermitted: false });
  });

  it("reports unavailable context without granting Paper actions", () => {
    expect(evaluateModeContext("PAPER", undefined)).toEqual({
      status: "unavailable",
      paperActionsPermitted: false,
      actualSummary: "Unavailable",
    });
  });

  it("requires global and action-specific Paper authority", () => {
    const paper = {
      execution_mode: "INTERNAL_SIMULATION",
      execution_authority: "PAPER_ONLY",
    } as const;

    expect(canUsePaperActions("PAPER", true, paper)).toBe(true);
    expect(canUsePaperActions("PAPER", false, paper)).toBe(false);
    expect(canUsePaperActions("DEMO", true, paper)).toBe(false);
    expect(
      canUsePaperActions("PAPER", true, {
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
      }),
    ).toBe(false);
    expect(canUsePaperActions("PAPER", true, undefined)).toBe(false);
  });
});
