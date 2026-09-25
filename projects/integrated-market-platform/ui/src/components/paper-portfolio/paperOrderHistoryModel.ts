import type { PaperPortfolioResponse } from "../../api/client";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import {
  isTerminalPaperOrderState,
  parsePersistedPaperDecisionProvenance,
  type PaperDecisionSourceCategory,
  type PaperOperationalProvenance,
} from "./paperDecisionProvenance";
import { paperOrderRejectionSummary, paperOrderStatusLabel } from "./paperOrderStatusPresentation";
import { formatShareCount } from "./paperPortfolioPresentation";

export type PaperOrderRecord = Record<string, unknown>;

export type PaperOrderHistoryRow = {
  rowId: string;
  orderId: string | null;
  intentId: string | null;
  clientOrderId: string | null;
  correlationId: string | null;
  symbol: string;
  /** Canonical instrument id when the record carries one, else the symbol. */
  instrumentId: string | null;
  workspaceHref: string | null;
  side: string;
  quantity: number | null;
  filledQuantity: number | null;
  /** Requested minus filled — what is still working. Null when unknown. */
  workingQuantity: number | null;
  orderType: string;
  status: string;
  statusLabel: string;
  /** Compact fill presentation: filled size and price when known. */
  fillSummary: string;
  fillPriceLabel: string | null;
  filledLabel: string;
  submittedAtLabel: string | null;
  submittedAtMs: number | null;
  submittedSequence: number | null;
  provenance: PaperOperationalProvenance;
  rejectionReason: string | null;
  isOpen: boolean;
  /** True only for states the backend cancel path can still act on. */
  cancelEligible: boolean;
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

function formatSubmittedAt(record: PaperOrderRecord): {
  label: string | null;
  ms: number | null;
  sequence: number | null;
} {
  const createdTime = readNumber(record, "created_time");
  if (createdTime !== null && createdTime > 0) {
    const millis = createdTime > 1_000_000_000_000_000 ? Math.floor(createdTime / 1_000_000) : createdTime;
    const date = new Date(millis);
    if (!Number.isNaN(date.getTime())) {
      return {
        label: date.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC"),
        ms: millis,
        sequence: null,
      };
    }
  }
  const sequence = readNumber(record, "submitted_sequence");
  if (sequence !== null) {
    return { label: `Seq ${sequence}`, ms: null, sequence };
  }
  return { label: null, ms: null, sequence: null };
}

/**
 * Backend cancel states: the ledger still owns a working remainder for these.
 * A filled, rejected, expired, or already-cancelled order is terminal and
 * cannot be cancelled — the UI must not offer a control the backend rejects.
 */
const CANCELLABLE_ORDER_STATES = new Set([
  "WORKING",
  "ACTIVATED",
  "PARTIALLY_FILLED",
  "REPLACED",
]);

export function isCancellablePaperOrderState(state: string | undefined | null): boolean {
  return CANCELLABLE_ORDER_STATES.has(String(state ?? "").toUpperCase());
}

/**
 * Fill prices arrive as integer minor units (the platform's own cents
 * convention, as used for cash and buying power). Presenting a raw
 * `2209400` in a primary table column is technical noise; format it the way
 * the rest of the platform formats money.
 */
function formatMinorPrice(minor: number): string {
  return (minor / 100).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatFillPriceLabel(
  record: PaperOrderRecord,
  fillsByOrderId: Map<string, PaperFillSummary[]>,
): { priceLabel: string | null; filledLabel: string } {
  const orderId = readString(record, "order_id");
  const relatedFills = orderId ? fillsByOrderId.get(orderId) ?? [] : [];
  const filledQuantity = readNumber(record, "filled_quantity");
  if (relatedFills.length > 0) {
    const totalQty = relatedFills.reduce((sum, fill) => sum + fill.quantity, 0);
    const prices = relatedFills.map((fill) => fill.priceMinor);
    const priceLabel =
      prices.length === 1
        ? formatMinorPrice(prices[0])
        : `${formatMinorPrice(Math.min(...prices))}–${formatMinorPrice(Math.max(...prices))}`;
    return { priceLabel, filledLabel: formatShareCount(totalQty) };
  }
  if (filledQuantity !== null && filledQuantity > 0) {
    return { priceLabel: null, filledLabel: formatShareCount(filledQuantity) };
  }
  return { priceLabel: null, filledLabel: "—" };
}

function fillSummary(record: PaperOrderRecord, fillsByOrderId: Map<string, PaperFillSummary[]>): string {
  const orderId = readString(record, "order_id");
  const filledQuantity = readNumber(record, "filled_quantity");
  const relatedFills = orderId ? fillsByOrderId.get(orderId) ?? [] : [];
  if (relatedFills.length > 0) {
    const totalQty = relatedFills.reduce((sum, fill) => sum + fill.quantity, 0);
    const prices = relatedFills.map((fill) => fill.priceMinor);
    const priceRange =
      prices.length === 1
        ? formatMinorPrice(prices[0])
        : `${formatMinorPrice(Math.min(...prices))}–${formatMinorPrice(Math.max(...prices))}`;
    return `${formatShareCount(totalQty)} @ ${priceRange}`;
  }
  if (filledQuantity !== null && filledQuantity > 0) {
    return `${formatShareCount(filledQuantity)} filled`;
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
  const instrumentId =
    readString(record, "instrument_id") ??
    (typeof record.instrument === "object" &&
    record.instrument &&
    typeof (record.instrument as Record<string, unknown>).instrument_id === "string"
      ? String((record.instrument as Record<string, unknown>).instrument_id)
      : null);
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
  const handoffInstrument = instrumentId ?? (symbol === "—" ? null : symbol);
  const workingQuantity =
    quantity !== null && filledQuantity !== null ? Math.max(0, quantity - filledQuantity) : null;
  const fill = formatFillPriceLabel(record, fillsByOrderId);

  return {
    rowId: stableRowId(record),
    orderId,
    intentId,
    clientOrderId,
    correlationId,
    symbol,
    instrumentId: handoffInstrument,
    workspaceHref: handoffInstrument ? workspacePathForInstrument(handoffInstrument) : null,
    side,
    quantity,
    filledQuantity,
    workingQuantity,
    orderType,
    status,
    statusLabel: paperOrderStatusLabel(status),
    fillSummary: fillSummary(record, fillsByOrderId),
    fillPriceLabel: fill.priceLabel,
    filledLabel: fill.filledLabel,
    submittedAtLabel: submitted.label,
    submittedAtMs: submitted.ms,
    submittedSequence: submitted.sequence,
    provenance,
    rejectionReason: paperOrderRejectionSummary(status, reasonCodes),
    isOpen: !isTerminalPaperOrderState(status),
    cancelEligible: isCancellablePaperOrderState(status),
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

/**
 * Compact recency for the orders table. Working orders want age; a historic
 * fill wants a plain date, not "3d ago" — a completed order's timestamp is a
 * record, not a countdown.
 */
export function formatOrderAge(
  row: PaperOrderHistoryRow,
  nowMs: number,
): { label: string; title: string } | null {
  if (row.submittedAtMs === null) return null;
  const absolute = new Date(row.submittedAtMs).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
  if (!row.isOpen) {
    // A completed order's timestamp is a record, not a countdown. Show the
    // compact form in the column and keep the full value in the title.
    const compact = new Date(row.submittedAtMs).toISOString().slice(5, 16).replace("T", " ");
    return { label: compact, title: absolute };
  }
  const seconds = Math.max(0, Math.round((nowMs - row.submittedAtMs) / 1000));
  if (seconds < 60) return { label: `${seconds}s`, title: absolute };
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return { label: `${minutes}m`, title: absolute };
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return { label: `${hours}h`, title: absolute };
  return { label: `${Math.floor(hours / 24)}d`, title: absolute };
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
