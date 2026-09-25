import { describe, expect, it } from "vitest";
import {
  buildPaperOrderHistoryMetrics,
  buildPaperOrderHistoryRow,
  buildPaperOrderHistoryRows,
  filterPaperOrderHistoryRows,
  formatOrderAge,
  splitPaperOrderHistoryRows,
} from "./paperOrderHistoryModel";

describe("paperOrderHistoryModel", () => {
  const fillsByOrderId = new Map([
    [
      "order-1",
      [{ fillId: "fill-1", quantity: 5, priceMinor: 1200, direction: "long" }],
    ],
  ]);

  it("maps lane provenance and status fields", () => {
    const row = buildPaperOrderHistoryRow(
      {
        order_id: "order-1",
        intent_id: "intent-1",
        client_order_id: "client-1",
        correlation_id: "lane:squeeze",
        state: "FILLED",
        side: "BUY",
        desired_quantity: 5,
        filled_quantity: 5,
        order_type: "MARKET",
        symbol: "BIYA",
        submitted_sequence: 12,
      },
      fillsByOrderId,
    );
    expect(row.provenance.sourceCategory).toBe("WORKSPACE_LANE");
    expect(row.statusLabel).toBe("Filled");
    expect(row.fillSummary).toContain("5 @");
    expect(row.isOpen).toBe(false);
  });

  it("sorts newest sequence first", () => {
    const rows = buildPaperOrderHistoryRows([
      { order_id: "a", submitted_sequence: 1, state: "FILLED" },
      { order_id: "b", submitted_sequence: 9, state: "FILLED" },
    ]);
    expect(rows.map((row) => row.orderId)).toEqual(["b", "a"]);
  });

  it("filters by source and status", () => {
    const rows = buildPaperOrderHistoryRows([
      {
        order_id: "lane",
        correlation_id: "lane:order-flow",
        client_order_id: "client-lane",
        state: "FILLED",
        symbol: "NVDA",
      },
      {
        order_id: "manual",
        correlation_id: "client-manual",
        client_order_id: "client-manual",
        state: "REJECTED",
        symbol: "BIYA",
      },
    ]);
    const laneOnly = filterPaperOrderHistoryRows(rows, {
      status: "ALL",
      source: "WORKSPACE_LANE",
      symbolQuery: "",
    });
    expect(laneOnly).toHaveLength(1);
    expect(laneOnly[0]?.orderId).toBe("lane");

    const rejected = filterPaperOrderHistoryRows(rows, {
      status: "REJECTED",
      source: "ALL",
      symbolQuery: "BIYA",
    });
    expect(rejected).toHaveLength(1);
    expect(rejected[0]?.orderId).toBe("manual");
  });

  it("computes summary metrics", () => {
    const rows = buildPaperOrderHistoryRows([
      { order_id: "1", correlation_id: "attention-biya", client_order_id: "c1", state: "WORKING" },
      { order_id: "2", correlation_id: "lane:squeeze", client_order_id: "c2", state: "FILLED" },
      { order_id: "3", correlation_id: "c3", client_order_id: "c3", state: "REJECTED" },
    ]);
    const metrics = buildPaperOrderHistoryMetrics(rows);
    expect(metrics.openOrders).toBe(1);
    expect(metrics.filled).toBe(1);
    expect(metrics.rejected).toBe(1);
    expect(metrics.paperCommandSourced).toBe(1);
    expect(metrics.laneSourced).toBe(1);
  });

  it("splits open and historical orders", () => {
    const rows = buildPaperOrderHistoryRows([
      { order_id: "open", state: "WORKING" },
      { order_id: "done", state: "FILLED" },
    ]);
    const split = splitPaperOrderHistoryRows(rows);
    expect(split.openOrders.map((row) => row.orderId)).toEqual(["open"]);
    expect(split.historyOrders.map((row) => row.orderId)).toEqual(["done"]);
  });

  it("handles old records without correlation", () => {
    const row = buildPaperOrderHistoryRow({ order_id: "legacy", state: "FILLED" }, new Map());
    expect(row.provenance.sourceCategory).toBe("MANUAL");
    expect(row.provenance.sourceDetail).toBe("No recorded decision source");
    expect(row.provenance.persistedSourceContext.snapshotAvailable).toBe(false);
  });

  it("maps persisted decision source snapshot onto provenance", () => {
    const row = buildPaperOrderHistoryRow(
      {
        order_id: "order-att",
        correlation_id: "attention-biya",
        client_order_id: "client-att",
        decision_source_snapshot: {
          source_type: "paper_command_attention",
          source_id: "attention-biya",
          headline: "Short interest elevated into catalyst window",
        },
        state: "FILLED",
        symbol: "BIYA",
      },
      new Map(),
    );
    expect(row.provenance.persistedSourceContext.snapshotAvailable).toBe(true);
    expect(row.provenance.tableSourceSummary).toBe("Short interest elevated into catalyst window");
  });

  it("carries the order's own instrument into a Workspace handoff", () => {
    const row = buildPaperOrderHistoryRow(
      { order_id: "o", state: "WORKING", symbol: "AAPL", side: "BUY" },
      new Map(),
    );
    expect(row.instrumentId).toBe("AAPL");
    expect(row.workspaceHref).toBe("/workspace/AAPL");
  });

  it("leaves the handoff empty rather than inventing an instrument", () => {
    const row = buildPaperOrderHistoryRow({ order_id: "o", state: "WORKING" }, new Map());
    expect(row.workspaceHref).toBeNull();
    expect(row.instrumentId).toBeNull();
  });

  it("formats fill price from minor units and separates filled from working size", () => {
    const row = buildPaperOrderHistoryRow(
      {
        order_id: "order-1",
        state: "PARTIALLY_FILLED",
        side: "SELL",
        symbol: "NVDA",
        desired_quantity: 400,
        filled_quantity: 150,
      },
      fillsByOrderId,
    );
    // Fills on the record win for the display figures; the working remainder is
    // requested minus the backend's filled quantity.
    expect(row.filledLabel).toBe("5");
    expect(row.fillPriceLabel).toBe("12.00");
    expect(row.workingQuantity).toBe(250);
  });

  it("offers cancel only for states the backend cancel path can still act on", () => {
    const working = buildPaperOrderHistoryRow(
      { order_id: "w", state: "WORKING", symbol: "AAPL" },
      new Map(),
    );
    const partial = buildPaperOrderHistoryRow(
      { order_id: "p", state: "PARTIALLY_FILLED", symbol: "AAPL" },
      new Map(),
    );
    const filled = buildPaperOrderHistoryRow({ order_id: "f", state: "FILLED" }, new Map());
    const cancelled = buildPaperOrderHistoryRow(
      { order_id: "c", state: "CANCELLED" },
      new Map(),
    );
    expect(working.cancelEligible).toBe(true);
    expect(partial.cancelEligible).toBe(true);
    expect(filled.cancelEligible).toBe(false);
    expect(cancelled.cancelEligible).toBe(false);
    for (const state of ["CREATED", "RISK_ACCEPTED", "SUBMITTED", "CANCEL_PENDING", "REPLACE_PENDING"]) {
      expect(buildPaperOrderHistoryRow({ order_id: state, state }, new Map()).cancelEligible).toBe(false);
    }
    for (const state of ["ACTIVATED", "REPLACED"]) {
      expect(buildPaperOrderHistoryRow({ order_id: state, state }, new Map()).cancelEligible).toBe(true);
    }
  });

  it("shows a working order's age but a fixed record time for a completed one", () => {
    const now = Date.parse("2026-09-25T12:00:00Z");
    const working = buildPaperOrderHistoryRow(
      { order_id: "w", state: "WORKING", created_time: now - 90 * 60_000 },
      new Map(),
    );
    const done = buildPaperOrderHistoryRow(
      { order_id: "d", state: "FILLED", created_time: now - 26 * 3_600_000 },
      new Map(),
    );
    expect(formatOrderAge(working, now)).toEqual({
      label: "1h",
      title: "2026-09-25 10:30:00 UTC",
    });
    expect(formatOrderAge(done, now)?.label).toBe("09-24 10:00");
    expect(formatOrderAge(done, now)?.title).toBe("2026-09-24 10:00:00 UTC");
  });
});
