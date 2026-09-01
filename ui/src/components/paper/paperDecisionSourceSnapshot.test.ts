import { describe, expect, it } from "vitest";
import {
  buildPaperDecisionSourceSnapshot,
  buildPersistedPaperSourceContext,
  formatPaperSourceTimeLabel,
  parsePaperDecisionSourceSnapshot,
} from "./paperDecisionSourceSnapshot";
import { createAttentionPaperOrderDraft, createLanePaperOrderDraft } from "../paper-now/paperOrderDraft";
import { attentionItem } from "../paper-now/paperNowTestFixtures";

describe("paperDecisionSourceSnapshot", () => {
  it("builds attention snapshot from draft sourceContext", () => {
    const draft = createAttentionPaperOrderDraft(
      attentionItem({
        attention_id: "ATT-123",
        headline: "Short interest elevated into catalyst window",
        tier: 1,
        reasons: [{ code: "SI", label: "Short interest elevated" }],
        surfaced_time: 1_700_000_000_000_000_000,
      }),
      { now: () => 1_700_000_100_000 },
    )!;
    const snapshot = buildPaperDecisionSourceSnapshot(draft);
    expect(snapshot).toEqual({
      source_type: "paper_command_attention",
      source_id: "ATT-123",
      headline: "Short interest elevated into catalyst window",
      tier: 1,
      reasons: [{ code: "SI", label: "Short interest elevated" }],
      source_time: 1_700_000_000_000_000_000,
    });
  });

  it("builds lane snapshot with handoff source_time", () => {
    const draft = createLanePaperOrderDraft("BIYA", "squeeze", { now: () => 1_700_000_100_000 });
    const snapshot = buildPaperDecisionSourceSnapshot(draft);
    expect(snapshot).toEqual({
      source_type: "workspace_lane",
      source_id: "squeeze",
      source_module: "squeeze",
      source_time: 1_700_000_100_000_000_000,
    });
  });

  it("returns undefined for manual drafts", () => {
    expect(
      buildPaperDecisionSourceSnapshot({
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
      }),
    ).toBeUndefined();
  });

  it("parses persisted snapshot and formats source time", () => {
    const parsed = parsePaperDecisionSourceSnapshot({
      source_type: "paper_command_attention",
      source_id: "ATT-1",
      headline: "Setup",
      source_time: 1_700_000_000_000,
    });
    expect(parsed?.headline).toBe("Setup");
    expect(formatPaperSourceTimeLabel(1_700_000_000_000)).toMatch(/2023/);
  });

  it("builds persisted context with semantic source time label", () => {
    const persisted = buildPersistedPaperSourceContext(
      {
        source_type: "paper_command_attention",
        source_id: "ATT-1",
        headline: "Setup",
        source_time: 1_700_000_000_000,
      },
      "ATT-1",
    );
    expect(persisted.sourceTimeFieldLabel).toBe("Attention surfaced");
    expect(persisted.sourceTimeLabel).toMatch(/2023/);
  });

  it("detects snapshot/correlation mismatch", () => {
    const persisted = buildPersistedPaperSourceContext(
      {
        source_type: "paper_command_attention",
        source_id: "ATT-1",
        headline: "Mismatch",
      },
      "lane:squeeze",
    );
    expect(persisted.snapshotMismatch).toBe(true);
    expect(persisted.snapshotAvailable).toBe(false);
  });

  it("accepts matching lane snapshot", () => {
    const persisted = buildPersistedPaperSourceContext(
      {
        source_type: "workspace_lane",
        source_id: "squeeze",
        source_module: "squeeze",
      },
      "lane:squeeze",
    );
    expect(persisted.snapshotAvailable).toBe(true);
    expect(persisted.headline).toMatch(/Short Squeeze lane handoff/);
  });

  it("tolerates malformed snapshot input", () => {
    expect(parsePaperDecisionSourceSnapshot(null)).toBeNull();
    expect(parsePaperDecisionSourceSnapshot({ source_type: "bad", source_id: "x" })).toBeNull();
    expect(buildPersistedPaperSourceContext({ headline: "orphan" }, "ATT-1").snapshotAvailable).toBe(false);
  });
});
