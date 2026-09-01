import { describe, expect, it, vi } from "vitest";
import {
  attentionSourceContextFromItem,
  buildPaperOrderRequest,
  createAttentionPaperOrderDraft,
  createLanePaperOrderDraft,
  createPaperOrderDraft,
  createPaperPreviewAttemptKey,
  derivePaperDecisionCorrelationId,
  formatPaperDraftSourceLabel,
  isLanePaperOrderDraft,
  parseLaneProvenance,
  parsePaperDraftProvenance,
  paperOrderDraftFingerprint,
  parsePaperOrderDraft,
} from "./paperOrderDraft";
import { attentionItem } from "./paperNowTestFixtures";

const HANDOFF_NS = 1_700_000_100_000_000_000;
const CANONICAL_NS = 1_700_000_000_000_000_000;
const fixedNow = () => 1_700_000_100_000;

describe("paper order draft", () => {
  it("creates only an explicit integer MARKET draft within the account limit", () => {
    expect(createPaperOrderDraft({
      instrumentId: " biya ", side: "BUY", quantity: 25, maxOrderShares: 100,
      sourceAttentionId: "attention-1",
      sourceContext: { headline: "Setup" },
    })).toEqual({
      version: 1, instrumentId: "BIYA", side: "BUY", quantity: 25,
      orderType: "MARKET", sourceAttentionId: "attention-1", sourceContext: { headline: "Setup" },
    });
    expect(createPaperOrderDraft({ instrumentId: "BIYA", side: null, quantity: 25, maxOrderShares: 100 })).toBeNull();
    expect(createPaperOrderDraft({ instrumentId: "BIYA", side: "SELL", quantity: 1.5, maxOrderShares: 100 })).toBeNull();
    expect(createPaperOrderDraft({ instrumentId: "BIYA", side: "SELL", quantity: 101, maxOrderShares: 100 })).toBeNull();
  });

  it("accepts only a structurally valid version-1 draft matching the route symbol", () => {
    const draft = { version: 1, instrumentId: "BIYA", side: "SELL", quantity: 4, orderType: "MARKET" };
    expect(parsePaperOrderDraft(draft, "biya")).toEqual(draft);
    expect(parsePaperOrderDraft({ ...draft, instrumentId: "NVDA" }, "BIYA")).toBeUndefined();
    expect(parsePaperOrderDraft({ ...draft, version: 2 }, "BIYA")).toBeUndefined();
    expect(parsePaperOrderDraft({ ...draft, risk_status: "PASS" }, "BIYA")).toBeUndefined();
    expect(
      parsePaperOrderDraft(
        {
          ...draft,
          sourceContext: { headline: "BIYA setup", tier: 1, reasons: [{ code: "X", label: "Y" }] },
        },
        "BIYA",
      ),
    ).toEqual({
      ...draft,
      sourceContext: { headline: "BIYA setup", tier: 1, reasons: [{ code: "X", label: "Y" }] },
    });
  });

  it("builds a request with decision correlation when provenance exists", () => {
    const draft = {
      version: 1 as const,
      instrumentId: "BIYA",
      side: "BUY" as const,
      quantity: 5,
      orderType: "MARKET" as const,
      sourceAttentionId: "attention-biya",
    };
    expect(buildPaperOrderRequest(draft, "attempt-1")).toEqual({
      side: "BUY",
      quantity: 5,
      order_type: "MARKET",
      instrument_id: "BIYA",
      symbol: "BIYA",
      client_order_id: "attempt-1",
      idempotency_key: "attempt-1",
      correlation_id: "attention-biya",
      decision_source_snapshot: {
        source_type: "paper_command_attention",
        source_id: "attention-biya",
      },
    });
    expect(paperOrderDraftFingerprint(draft)).toBe("BIYA|BUY|5|MARKET");
  });

  it("includes decision_source_snapshot for attention drafts with sourceContext", () => {
    const item = attentionItem({
      attention_id: "ATT-123",
      headline: "Short interest elevated into catalyst window",
      tier: 1,
      reasons: [{ code: "SI", label: "Short interest elevated" }],
      surfaced_time: CANONICAL_NS,
    });
    const draft = createAttentionPaperOrderDraft(item, { now: fixedNow })!;
    expect(buildPaperOrderRequest(draft, "attempt-2").decision_source_snapshot).toEqual({
      source_type: "paper_command_attention",
      source_id: "ATT-123",
      headline: "Short interest elevated into catalyst window",
      tier: 1,
      reasons: [{ code: "SI", label: "Short interest elevated" }],
      source_time: CANONICAL_NS,
    });
  });

  it("uses handoff time for attention when surfaced_time is absent", () => {
    const item = attentionItem({ attention_id: "ATT-fallback", surfaced_time: undefined });
    const draft = createAttentionPaperOrderDraft(item, { now: fixedNow })!;
    expect(draft.sourceContext?.source_time).toBe(HANDOFF_NS);
    expect(buildPaperOrderRequest(draft, "attempt-fb").decision_source_snapshot?.source_time).toBe(HANDOFF_NS);
  });

  it("includes lane decision_source_snapshot with handoff source_time", () => {
    const draft = createLanePaperOrderDraft("BIYA", "squeeze", { now: fixedNow });
    expect(buildPaperOrderRequest(draft, "attempt-3").decision_source_snapshot).toEqual({
      source_type: "workspace_lane",
      source_id: "squeeze",
      source_module: "squeeze",
      source_time: HANDOFF_NS,
    });
  });

  it("preserves source_time when draft fields are edited", () => {
    const draft = createAttentionPaperOrderDraft(
      attentionItem({ attention_id: "ATT-edit", surfaced_time: CANONICAL_NS }),
      { now: fixedNow },
    )!;
    const edited = createPaperOrderDraft({
      instrumentId: draft.instrumentId,
      side: "SELL",
      quantity: 5,
      maxOrderShares: 100,
      sourceAttentionId: draft.sourceAttentionId,
      sourceContext: draft.sourceContext,
    })!;
    expect(buildPaperOrderRequest(edited, "attempt-edit").decision_source_snapshot?.source_time).toBe(CANONICAL_NS);
  });

  it("omits decision_source_snapshot for manual drafts", () => {
    const draft = { version: 1 as const, instrumentId: "BIYA", side: "BUY" as const, quantity: 5, orderType: "MARKET" as const };
    expect(buildPaperOrderRequest(draft, "attempt-1").decision_source_snapshot).toBeUndefined();
  });

  it("omits correlation_id for manual drafts", () => {
    const draft = { version: 1 as const, instrumentId: "BIYA", side: "BUY" as const, quantity: 5, orderType: "MARKET" as const };
    expect(buildPaperOrderRequest(draft, "attempt-1").correlation_id).toBeUndefined();
    expect(derivePaperDecisionCorrelationId(draft)).toBeUndefined();
  });

  it("creates a new attempt key for each preview attempt", () => {
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000001")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000002");
    expect(createPaperPreviewAttemptKey("paper-now")).not.toBe(createPaperPreviewAttemptKey("paper-now"));
  });

  it("creates a lane-sourced draft that parses on the workspace route", () => {
    const draft = createLanePaperOrderDraft("biya", "squeeze", { now: fixedNow });
    expect(draft).toEqual({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "lane:squeeze",
      sourceContext: { source_time: HANDOFF_NS },
    });
    expect(parsePaperOrderDraft(draft, "BIYA")).toEqual(draft);
    expect(isLanePaperOrderDraft(draft)).toBe(true);
    expect(parseLaneProvenance(draft.sourceAttentionId)?.label).toBe("Short Squeeze");
    expect(derivePaperDecisionCorrelationId(draft)).toBe("lane:squeeze");
    expect(formatPaperDraftSourceLabel(draft)).toBe("Short Squeeze lane");
  });

  it("creates an attention placeholder draft without inferring side from attention strength", () => {
    const item = attentionItem({ attention_id: "ATT-123", tier: 1 });
    const draft = createAttentionPaperOrderDraft(item);
    expect(draft).toEqual({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "ATT-123",
      sourceContext: attentionSourceContextFromItem(item),
    });
    expect(parsePaperDraftProvenance(draft!).type).toBe("ATTENTION");
    expect(formatPaperDraftSourceLabel(draft)).toBe("Paper Command attention ATT-123");
  });

  it("parses provenance variants and malformed ids", () => {
    expect(parsePaperDraftProvenance(undefined).type).toBe("MANUAL");
    expect(parsePaperDraftProvenance({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "lane:",
    }).isValid).toBe(false);
    expect(parsePaperDraftProvenance({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "attention:",
    }).isValid).toBe(false);
    expect(parsePaperDraftProvenance({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "lane:custom-lane",
    }).warnings.length).toBeGreaterThan(0);
    expect(parsePaperDraftProvenance({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "attention:ATT-99",
    }).attentionId).toBe("ATT-99");
  });
});
