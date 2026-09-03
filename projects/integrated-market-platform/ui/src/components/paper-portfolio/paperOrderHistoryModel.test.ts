import { describe, expect, it } from "vitest";
import {
  buildPaperOrderHistoryMetrics,
  buildPaperOrderHistoryRow,
  buildPaperOrderHistoryRows,
  filterPaperOrderHistoryRows,
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
});
