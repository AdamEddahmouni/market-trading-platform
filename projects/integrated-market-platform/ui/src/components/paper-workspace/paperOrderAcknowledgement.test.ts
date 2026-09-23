import { describe, expect, it } from "vitest";
import type { PaperOrderDraft } from "../paper-now/paperOrderDraft";
import { buildPaperOrderAcknowledgement } from "./paperOrderAcknowledgement";

describe("buildPaperOrderAcknowledgement", () => {
  const opportunityDraft: PaperOrderDraft = {
    version: 1,
    instrumentId: "AAPL",
    side: "BUY",
    quantity: 1,
    orderType: "MARKET",
    sourceAttentionId: "opportunity:opp-ack-1",
    sourceContext: {
      reasons: [{ code: "WATCHED_OPPORTUNITY", label: "Watched Radar opportunity handoff" }],
    },
  };

  it("surfaces durable order id, status, provenance, and order-history href", () => {
    const ack = buildPaperOrderAcknowledgement(
      {
        duplicate: false,
        decision: "ALLOW",
        intent_id: "intent-1",
        order_id: "order-1",
        order: {
          order_id: "order-1",
          state: "FILLED",
          side: "BUY",
          desired_quantity: 1,
          instrument_id: "AAPL",
          correlation_id: "opportunity:opp-ack-1",
        },
        fill: { fill_id: "fill-1", order_id: "order-1" },
      },
      opportunityDraft,
    );

    expect(ack.hasDurableOrder).toBe(true);
    expect(ack.orderId).toBe("order-1");
    expect(ack.intentId).toBe("intent-1");
    expect(ack.orderState).toBe("FILLED");
    expect(ack.orderLabel).toBe("BUY × 1 MARKET");
    expect(ack.opportunityId).toBe("opp-ack-1");
    expect(ack.provenanceLabel).toMatch(/Radar watched opportunity/i);
    expect(ack.orderHistoryHref).toBe("/portfolio#portfolio-order-history");
    expect(ack.fillObserved).toBe(true);
    expect(ack.fillId).toBe("fill-1");
    expect(ack.duplicate).toBe(false);
  });

  it("keeps duplicate acknowledgements durable without inventing a fill", () => {
    const ack = buildPaperOrderAcknowledgement(
      {
        duplicate: true,
        order_id: "order-dup",
        order: { order_id: "order-dup", state: "WORKING", side: "SELL", quantity: 12 },
      },
      {
        version: 1,
        instrumentId: "BIYA",
        side: "SELL",
        quantity: 12,
        orderType: "MARKET",
        sourceAttentionId: "attention-biya",
      },
    );

    expect(ack.duplicate).toBe(true);
    expect(ack.hasDurableOrder).toBe(true);
    expect(ack.orderId).toBe("order-dup");
    expect(ack.intentId).toBeNull();
    expect(ack.fillObserved).toBe(false);
    expect(ack.fillId).toBeNull();
    expect(ack.orderLabel).toBe("SELL × 12 MARKET");
  });

  it("does not invent fillObserved when the server omitted fill", () => {
    const ack = buildPaperOrderAcknowledgement({
      duplicate: false,
      intent_id: "intent-open",
      order_id: "order-open",
      order: { order_id: "order-open", state: "WORKING", side: "BUY", quantity: 2 },
      fill: null,
    });
    expect(ack.fillObserved).toBe(false);
    expect(ack.fillId).toBeNull();
  });
});
