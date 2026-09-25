/**
 * Portfolio presentation (pure). Translates Paper/Demo portfolio contracts
 * into operator language. Does not invent NAV, daily P&L, dollar exposure,
 * or a frontend risk score.
 */
import type { PaperPortfolioResponse } from "../../api/client";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import type { SemanticTone } from "../../state/semanticState";
import {
  derivePaperExceptions,
  formatMinorCurrency,
  type PaperException,
} from "../paper-now/paperDashboardViewModel";

export const PORTFOLIO_SECTIONS = {
  account: "portfolio-account",
  summary: "portfolio-summary",
  attention: "portfolio-attention",
  positions: "portfolio-positions",
  exposure: "portfolio-exposure",
  activity: "portfolio-activity",
  /** Full order lifecycle panel below snapshot fills (Paper Portfolio only). */
  orderHistory: "portfolio-order-history",
  /** Open (working) orders — the operator's active execution state. */
  openOrders: "portfolio-open-orders",
} as const;

export type SignedAmountPresentation = {
  text: string;
  direction: "gain" | "loss" | "flat" | "unavailable";
  spoken: string;
};

export type PortfolioSummaryMetric = {
  id: string;
  label: string;
  value: string;
  available: boolean;
  signed?: SignedAmountPresentation;
};

export type PortfolioAttentionItem = {
  code: string;
  tone: SemanticTone;
  message: string;
  affects: string;
  action?: { label: string; href: string };
};

export type PortfolioPositionRow = {
  instrumentId: string;
  symbol: string;
  /** Absolute share count as the backend reports it. */
  quantity: number;
  /** Pre-formatted absolute size for the Qty cell. */
  quantityLabel: string;
  side: PortfolioPositionSide;
  sideLabel: string;
  averageFill: string;
  mark: string;
  markQuality: string | null;
  markAsOfNs: number | null;
  unrealized: SignedAmountPresentation;
  markProvenance: string;
  workspaceHref: string;
  /** Stable identity for selection + row-detail disclosure. */
  rowId: string;
};

export type PortfolioPositionSide = "long" | "short" | "flat";

/**
 * One glance row that answers "what exposure and active execution state do I
 * have right now?" Every value here is derived from canonical account/risk
 * state already on the payload — nothing is invented.
 */
export type PortfolioGlanceMetric = {
  id: string;
  label: string;
  value: string;
  available: boolean;
  signed?: SignedAmountPresentation;
  emphasis?: "lead";
};

/** Healthy mark qualities. Mirrors the mark vocabulary in `FreshnessIndicator` —
 * `FRESH`/`LIVE`/`SNAPSHOT`/`REPLAY` are current, not problems. */
const HEALTHY_MARK = new Set([
  "PASS",
  "HEALTHY",
  "CURRENT",
  "AVAILABLE",
  "FRESH",
  "LIVE",
  "SNAPSHOT",
  "REPLAY",
  "NOT_APPLICABLE",
]);

export function classifySignedDisplay(value: string | null | undefined): SignedAmountPresentation {
  if (value == null || value.trim() === "" || value === "—") {
    return { text: "Unavailable", direction: "unavailable", spoken: "Unavailable" };
  }
  const text = value.trim();
  const numeric = Number(text.replace(/[$,]/g, "").replace(/^\+/, ""));
  if (!Number.isFinite(numeric)) {
    return { text, direction: "flat", spoken: text };
  }
  if (numeric > 0) return { text, direction: "gain", spoken: `gain ${text}` };
  if (numeric < 0) return { text, direction: "loss", spoken: `loss ${text}` };
  return { text, direction: "flat", spoken: `unchanged ${text}` };
}

export function marksDecay(dataMode: string | undefined): boolean {
  const upper = (dataMode ?? "").toUpperCase();
  return upper !== "FIXTURE_REPLAY" && upper !== "HISTORICAL_CAPTURE" && upper !== "REPLAY";
}

export function paperCapitalHonesty(viewMode: "DEMO" | "PAPER"): {
  tone: SemanticTone;
  sentence: string;
  affects: string;
} {
  if (viewMode === "DEMO") {
    return {
      tone: "replay",
      sentence: "This is a simulated Demo account — not live capital.",
      affects: "Cash, buying power, and P&L are replay/simulated figures.",
    };
  }
  return {
    tone: "paper",
    sentence: "This is a Paper simulation account — not live capital.",
    affects: "Cash, buying power, and P&L are internal-simulation figures.",
  };
}

export function buildPortfolioSummaryMetrics(data: PaperPortfolioResponse): PortfolioSummaryMetric[] {
  const currency = data.account.currency;
  const buyingPower = formatMinorCurrency(data.account.buying_power_minor, currency);
  const startingCash = formatMinorCurrency(data.account.initial_cash_minor, currency);
  const realized = data.pnl?.realized_display ?? data.account.realized_pnl_display;
  const unrealized = data.pnl?.unrealized_display ?? null;
  const total = data.pnl?.total_display ?? realized;
  return [
    { id: "cash", label: "Cash", value: data.account.cash_display, available: true },
    {
      id: "buying-power",
      label: "Buying power",
      value: buyingPower ?? "Unavailable",
      available: buyingPower !== null,
    },
    {
      id: "starting-cash",
      label: "Starting cash",
      value: startingCash ?? "Unavailable",
      available: startingCash !== null,
    },
    {
      id: "realized",
      label: "Realized P&L",
      value: realized,
      available: true,
      signed: classifySignedDisplay(realized),
    },
    {
      id: "unrealized",
      label: "Unrealized P&L",
      value: unrealized ?? "Unavailable",
      available: Boolean(unrealized),
      signed: classifySignedDisplay(unrealized),
    },
    {
      id: "total-pnl",
      label: "Total P&L",
      value: total,
      available: true,
      signed: classifySignedDisplay(total),
    },
  ];
}

function exceptionTone(item: PaperException): SemanticTone {
  return item.severity === 0 ? "critical" : "caution";
}

function exceptionAffects(item: PaperException): string {
  if (item.code === "KILL_SWITCH_ACTIVE") return "Paper session mutations and Workspace submit stay gated by backend risk.";
  if (item.code.startsWith("DATA_")) return "Marks and unrealized P&L may be incomplete.";
  if (item.code.startsWith("RECONCILIATION_")) return "Account truth may not match the simulation ledger.";
  if (item.code.startsWith("RISK_")) return "The last recorded risk decision needs review before a new Paper order.";
  if (item.code.startsWith("ORDER_")) return "An existing simulated order is not in a healthy state.";
  if (item.code.startsWith("MARK_")) return "Unrealized P&L for that position may be inaccurate.";
  return item.detail ?? "Review the reported contract state.";
}

function exceptionAction(item: PaperException): { label: string; href: string } | undefined {
  if (item.code.startsWith("DATA_") || item.code.startsWith("MARK_")) {
    return { label: "Open Control", href: "/control#control-providers" };
  }
  if (item.code === "KILL_SWITCH_ACTIVE" || item.code.startsWith("RISK_")) {
    return { label: "Open Workspace", href: "/workspace" };
  }
  return undefined;
}

export function buildPortfolioAttention(data: PaperPortfolioResponse): PortfolioAttentionItem[] {
  return derivePaperExceptions(data).map((item) => ({
    code: item.code,
    tone: exceptionTone(item),
    message: item.message,
    affects: exceptionAffects(item),
    action: exceptionAction(item),
  }));
}

export function buildPortfolioPositions(data: PaperPortfolioResponse): PortfolioPositionRow[] {
  return data.positions.map((row) => {
    const side = classifyPositionSide(row.side, row.quantity);
    return {
      instrumentId: row.instrument_id,
      rowId: `${row.instrument_id}:${side}`,
      symbol: row.symbol,
      quantity: Math.abs(row.quantity),
      quantityLabel: formatShareCount(Math.abs(row.quantity)),
      side,
      sideLabel: POSITION_SIDE_LABEL[side],
      averageFill: row.average_fill_display?.trim() ? row.average_fill_display : "Unavailable",
      mark: row.mark_display?.trim() ? row.mark_display : "Unavailable",
      markQuality: row.mark_quality ?? null,
      markAsOfNs: row.mark_as_of_ns ?? null,
      unrealized: classifySignedDisplay(row.unrealized_pnl_display),
      markProvenance: row.mark_provider ?? row.mark_source ?? "Unavailable",
      workspaceHref: workspacePathForInstrument(row.instrument_id),
    };
  });
}

const POSITION_SIDE_LABEL: Record<PortfolioPositionSide, string> = {
  long: "Long",
  short: "Short",
  flat: "Flat",
};

/**
 * The backend is the authority on side, but a signed quantity is an equally
 * canonical statement of direction. Trust the explicit side when it maps to a
 * known direction, and fall back to the sign of the quantity otherwise.
 */
export function classifyPositionSide(side: string | undefined, quantity: number): PortfolioPositionSide {
  const normalized = (side ?? "").trim().toUpperCase();
  if (normalized === "LONG" || normalized === "BUY" || normalized === "BULL") return "long";
  if (normalized === "SHORT" || normalized === "SELL" || normalized === "BEAR") return "short";
  if (normalized === "FLAT" || normalized === "NONE") return "flat";
  if (quantity > 0) return "long";
  if (quantity < 0) return "short";
  return "flat";
}

/** Thousands-separated integer share count. Never a locale-dependent float. */
export function formatShareCount(quantity: number): string {
  if (!Number.isFinite(quantity)) return "—";
  return Math.round(quantity).toLocaleString("en-US");
}

export function positionNeedsAttention(row: PortfolioPositionRow): boolean {
  const quality = row.markQuality?.toUpperCase();
  return Boolean(quality && !HEALTHY_MARK.has(quality));
}

/**
 * The single answer to "what exposure and active execution state do I have
 * right now?" — net/gross exposure, working orders, and the three canonical
 * P&L figures on one row. This deliberately replaces the previous Summary +
 * Risk summary pair, which repeated buying power and total P&L twice.
 */
export function buildPortfolioGlanceMetrics(data: PaperPortfolioResponse): PortfolioGlanceMetric[] {
  const { account, risk, exposure } = data;
  const realized = data.pnl?.realized_display ?? account.realized_pnl_display;
  const unrealized = data.pnl?.unrealized_display ?? null;
  const total = data.pnl?.total_display ?? realized;
  const metrics: PortfolioGlanceMetric[] = [];

  metrics.push({
    id: "positions",
    label: "Positions",
    value: String(data.positions.length),
    available: true,
    emphasis: "lead",
  });
  metrics.push({
    id: "open-orders",
    label: "Working orders",
    value: String(risk.open_order_count ?? 0),
    available: true,
    emphasis: "lead",
  });
  if (exposureAvailable(exposure)) {
    metrics.push({
      id: "net-exposure",
      label: "Net exposure",
      value: `${formatShareCount(exposure.net_shares)} sh`,
      available: true,
    });
    metrics.push({
      id: "gross-exposure",
      label: "Gross exposure",
      value: `${formatShareCount(exposure.gross_shares)} sh`,
      available: true,
    });
  }
  metrics.push({
    id: "realized",
    label: "Realized P&L",
    value: realized,
    available: true,
    signed: classifySignedDisplay(realized),
  });
  metrics.push({
    id: "unrealized",
    label: "Unrealized P&L",
    value: unrealized ?? "Unavailable",
    available: Boolean(unrealized),
    signed: classifySignedDisplay(unrealized),
  });
  metrics.push({
    id: "total-pnl",
    label: "Total P&L",
    value: total,
    available: true,
    signed: classifySignedDisplay(total),
  });
  return metrics;
}

export function exposureAvailable(
  exposure: PaperPortfolioResponse["exposure"],
): exposure is { gross_shares: number; net_shares: number } {
  return Boolean(exposure);
}
