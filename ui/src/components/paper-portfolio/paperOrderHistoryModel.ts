import type { PaperPortfolioResponse } from "../../api/client";
import {
  isTerminalPaperOrderState,
  parsePersistedPaperDecisionProvenance,
  type PaperDecisionSourceCategory,
  type PaperOperationalProvenance,
} from "./paperDecisionProvenance";
import { paperOrderRejectionSummary, paperOrderStatusLabel } from "./paperOrderStatusPresentation";

export type PaperOrderRecord = Record<string, unknown>;

export type PaperOrderHistoryRow = {
  rowId: string;
  orderId: string | null;
  intentId: string | null;
  clientOrderId: string | null;
  correlationId: string | null;
  symbol: string;
  side: string;
  quantity: number | null;
  filledQuantity: number | null;
  orderType: string;
  status: string;
  statusLabel: string;
  fillSummary: string;
  submittedAtLabel: string | null;
  submittedSequence: number | null;
  provenance: PaperOperationalProvenance;
  rejectionReason: string | null;
  isOpen: boolean;
  fills: PaperFillSummary[];
};

export type PaperFillSummary = {
  fillId: string;
  quantity: number;
  priceMinor: number;
  direction: string;
};

export type PaperOrderHistoryMetrics = {
  openOrders: number;
  filled: number;
  rejected: number;
  paperCommandSourced: number;
  laneSourced: number;
};

export type PaperOrderHistoryFilters = {
  status: "ALL" | "OPEN" | "FILLED" | "REJECTED";
  source: "ALL" | PaperDecisionSourceCategory;
  symbolQuery: string;
};

export const DEFAULT_PAPER_ORDER_HISTORY_FILTERS: PaperOrderHistoryFilters = {
  status: "ALL",
  source: "ALL",
  symbolQuery: "",
};

function readString(record: PaperOrderRecord, key: string): string | null {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function readNumber(record: PaperOrderRecord, key: string): number | null {
  const value = record[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function readStringArray(record: PaperOrderRecord, key: string): string[] {
  const value = record[key];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function stableRowId(record: PaperOrderRecord): string {
  return (
    readString(record, "order_id") ??
    readString(record, "intent_id") ??
    readString(record, "client_order_id") ??
    `order-${readNumber(record, "submitted_sequence") ?? 0}`
  );
}

function formatSubmittedAt(record: PaperOrderRecord): { label: string | null; sequence: number | null } {
  const createdTime = readNumber(record, "created_time");
  if (createdTime !== null && createdTime > 0) {
    const millis = createdTime > 1_000_000_000_000_000 ? Math.floor(createdTime / 1_000_000) : createdTime;
    const date = new Date(millis);
    if (!Number.isNaN(date.getTime())) {
      return { label: date.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC"), sequence: null };
    }
  }
  const sequence = readNumber(record, "submitted_sequence");
  if (sequence !== null) {
    return { label: `Seq ${sequence}`, sequence };
  }
  return { label: null, sequence: null };
}

function fillSummary(record: PaperOrderRecord, fillsByOrderId: Map<string, PaperFillSummary[]>): string {
  const orderId = readString(record, "order_id");
  const filledQuantity = readNumber(record, "filled_quantity");
  const relatedFills = orderId ? fillsByOrderId.get(orderId) ?? [] : [];
  if (relatedFills.length > 0) {
    const totalQty = relatedFills.reduce((sum, fill) => sum + fill.quantity, 0);
    const prices = relatedFills.map((fill) => fill.priceMinor);
    const priceRange =
      prices.length === 1 ? `${prices[0]} minor` : `${Math.min(...prices)}–${Math.max(...prices)} minor`;
    return `${totalQty} @ ${priceRange}`;
  }
  if (filledQuantity !== null && filledQuantity > 0) {
    return `${filledQuantity} filled`;
  }
  return "—";
}

function indexFillsByOrderId(fills: PaperOrderRecord[]): Map<string, PaperFillSummary[]> {
  const map = new Map<string, PaperFillSummary[]>();
  for (const fill of fills) {
    const orderId = readString(fill, "order_id");
    const fillId = readString(fill, "fill_id");
    const quantity = readNumber(fill, "fill_quantity");
    const priceMinor = readNumber(fill, "fill_price_minor");
    const direction = readString(fill, "direction") ?? "—";
    if (!orderId || !fillId || quantity === null || priceMinor === null) continue;
    const bucket = map.get(orderId) ?? [];
    bucket.push({ fillId, quantity, priceMinor, direction });
    map.set(orderId, bucket);
  }
  return map;
}

export function buildPaperOrderHistoryRow(
  record: PaperOrderRecord,
  fillsByOrderId: Map<string, PaperFillSummary[]>,
): PaperOrderHistoryRow {
  const orderId = readString(record, "order_id");
  const intentId = readString(record, "intent_id");
  const clientOrderId = readString(record, "client_order_id");
  const correlationId = readString(record, "correlation_id");
  const symbol =
    readString(record, "symbol") ??
    readString(record, "instrument_id") ??
    (typeof record.instrument === "object" &&
    record.instrument &&
    typeof (record.instrument as Record<string, unknown>).symbol === "string"
      ? String((record.instrument as Record<string, unknown>).symbol)
      : null) ??
    "—";
  const side = readString(record, "side") ?? readString(record, "direction") ?? "—";
  const quantity = readNumber(record, "desired_quantity") ?? readNumber(record, "quantity");
  const filledQuantity = readNumber(record, "filled_quantity");
  const orderType = readString(record, "order_type") ?? "MARKET";
  const status = readString(record, "state") ?? "UNKNOWN";
  const reasonCodes = readStringArray(record, "reason_codes");
  const submitted = formatSubmittedAt(record);
  const provenance = parsePersistedPaperDecisionProvenance(
    correlationId,
    clientOrderId,
    symbol === "—" ? null : symbol,
    record.decision_source_snapshot,
  );

  return {
    rowId: stableRowId(record),
    orderId,
    intentId,
    clientOrderId,
    correlationId,
    symbol,
    side,
    quantity,
    filledQuantity,
    orderType,
    status,
    statusLabel: paperOrderStatusLabel(status),
    fillSummary: fillSummary(record, fillsByOrderId),
    submittedAtLabel: submitted.label,
    submittedSequence: submitted.sequence,
    provenance,
    rejectionReason: paperOrderRejectionSummary(status, reasonCodes),
    isOpen: !isTerminalPaperOrderState(status),
    fills: orderId ? fillsByOrderId.get(orderId) ?? [] : [],
  };
}

export function buildPaperOrderHistoryRows(
  orders: PaperOrderRecord[],
  fills: PaperOrderRecord[] = [],
): PaperOrderHistoryRow[] {
  const fillsByOrderId = indexFillsByOrderId(fills);
  return orders
    .map((record) => buildPaperOrderHistoryRow(record, fillsByOrderId))
    .sort((left, right) => {
      const leftSeq = left.submittedSequence ?? -1;
      const rightSeq = right.submittedSequence ?? -1;
      if (leftSeq !== rightSeq) return rightSeq - leftSeq;
      return left.rowId.localeCompare(right.rowId);
    });
}

export function splitPaperOrderHistoryRows(rows: PaperOrderHistoryRow[]): {
  openOrders: PaperOrderHistoryRow[];
  historyOrders: PaperOrderHistoryRow[];
} {
  const openOrders = rows.filter((row) => row.isOpen);
  const historyOrders = rows.filter((row) => !row.isOpen);
  return { openOrders, historyOrders };
}

export function filterPaperOrderHistoryRows(
  rows: PaperOrderHistoryRow[],
  filters: PaperOrderHistoryFilters,
): PaperOrderHistoryRow[] {
  const query = filters.symbolQuery.trim().toUpperCase();
  return rows.filter((row) => {
    if (filters.status === "OPEN" && !row.isOpen) return false;
    if (filters.status === "FILLED" && row.status.toUpperCase() !== "FILLED") return false;
    if (filters.status === "REJECTED") {
      const normalized = row.status.toUpperCase();
      if (!["REJECTED", "RISK_REJECTED", "EXPIRED"].includes(normalized)) return false;
    }
    if (filters.source !== "ALL" && row.provenance.sourceCategory !== filters.source) return false;
    if (query && !row.symbol.toUpperCase().includes(query)) {
      const headline = row.provenance.persistedSourceContext.headline;
      if (!headline || !headline.toUpperCase().includes(query)) return false;
    }
    return true;
  });
}

export function buildPaperOrderHistoryMetrics(rows: PaperOrderHistoryRow[]): PaperOrderHistoryMetrics {
  return {
    openOrders: rows.filter((row) => row.isOpen).length,
    filled: rows.filter((row) => row.status.toUpperCase() === "FILLED").length,
    rejected: rows.filter((row) => ["REJECTED", "RISK_REJECTED"].includes(row.status.toUpperCase())).length,
    paperCommandSourced: rows.filter((row) => row.provenance.sourceCategory === "PAPER_COMMAND").length,
    laneSourced: rows.filter((row) => row.provenance.sourceCategory === "WORKSPACE_LANE").length,
  };
}

export function buildPaperOrderHistoryFromPortfolio(data: PaperPortfolioResponse): {
  rows: PaperOrderHistoryRow[];
  openOrders: PaperOrderHistoryRow[];
  historyOrders: PaperOrderHistoryRow[];
  metrics: PaperOrderHistoryMetrics;
} {
  const rows = buildPaperOrderHistoryRows(
    data.orders as PaperOrderRecord[],
    data.fills as PaperOrderRecord[],
  );
  const { openOrders, historyOrders } = splitPaperOrderHistoryRows(rows);
  return {
    rows,
    openOrders,
    historyOrders,
    metrics: buildPaperOrderHistoryMetrics(rows),
  };
}
