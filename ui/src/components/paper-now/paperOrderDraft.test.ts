import { describe, expect, it, vi } from "vitest";
import {
  buildPaperOrderRequest,
  createPaperOrderDraft,
  createPaperPreviewAttemptKey,
  paperOrderDraftFingerprint,
  parsePaperOrderDraft,
} from "./paperOrderDraft";

describe("paper order draft", () => {
  it("creates only an explicit integer MARKET draft within the account limit", () => {
    expect(createPaperOrderDraft({
      instrumentId: " biya ", side: "BUY", quantity: 25, maxOrderShares: 100,
      sourceAttentionId: "attention-1",
    })).toEqual({
      version: 1, instrumentId: "BIYA", side: "BUY", quantity: 25,
      orderType: "MARKET", sourceAttentionId: "attention-1",
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
  });

  it("builds a request from the draft without carrying preview authority", () => {
    const draft = { version: 1 as const, instrumentId: "BIYA", side: "BUY" as const, quantity: 5, orderType: "MARKET" as const };
    expect(buildPaperOrderRequest(draft, "attempt-1")).toEqual({
      side: "BUY", quantity: 5, order_type: "MARKET", instrument_id: "BIYA", symbol: "BIYA",
      client_order_id: "attempt-1", idempotency_key: "attempt-1",
    });
    expect(paperOrderDraftFingerprint(draft)).toBe("BIYA|BUY|5|MARKET");
  });

  it("creates a new attempt key for each preview attempt", () => {
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000001")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000002");
    expect(createPaperPreviewAttemptKey("paper-now")).not.toBe(createPaperPreviewAttemptKey("paper-now"));
  });
});
