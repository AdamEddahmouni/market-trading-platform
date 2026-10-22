import type { PaperBoundary, PaperValuation } from "../../api/schemas";
import { humanizeEnum } from "../../state/semanticState";

/** Presentation only. Every number is a server projection of the Paper ledger. */

export const UNAVAILABLE = "Unavailable";

export function formatMoney(minor: number | null | undefined, currency: string): string {
  if (minor === null || minor === undefined || !Number.isFinite(minor)) return UNAVAILABLE;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(minor / 100);
  } catch {
    return UNAVAILABLE;
  }
}

export type SignedMoney = { text: string; direction: "gain" | "loss" | "flat" | "unavailable"; label: string };

/** Sign is carried in the text and the accessible label, never by colour alone. */
export function formatSignedMoney(minor: number | null | undefined, currency: string): SignedMoney {
  if (minor === null || minor === undefined || !Number.isFinite(minor)) {
    return { text: UNAVAILABLE, direction: "unavailable", label: "unavailable" };
  }
  const magnitude = formatMoney(Math.abs(minor), currency);
  if (minor > 0) return { text: `+${magnitude}`, direction: "gain", label: `gain of ${magnitude}` };
  if (minor < 0) return { text: `−${magnitude}`, direction: "loss", label: `loss of ${magnitude}` };
  return { text: magnitude, direction: "flat", label: `${magnitude}, no gain or loss` };
}

export function formatReturn(bps: number | null | undefined): string {
  if (bps === null || bps === undefined || !Number.isFinite(bps)) return UNAVAILABLE;
  const sign = bps > 0 ? "+" : bps < 0 ? "−" : "";
  return `${sign}${(Math.abs(bps) / 100).toFixed(2)}%`;
}

export function formatNs(ns: number | null | undefined): string {
  if (!ns || !Number.isFinite(ns)) return UNAVAILABLE;
  return new Date(Math.floor(ns / 1_000_000)).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZoneName: "short",
  });
}

export function markAge(asOfNs: number | null | undefined, nowMs: number): string {
  if (!asOfNs) return UNAVAILABLE;
  const seconds = Math.max(0, Math.round((nowMs - asOfNs / 1_000_000) / 1000));
  if (seconds < 90) return `${seconds}s old`;
  if (seconds < 5400) return `${Math.round(seconds / 60)}m old`;
  return `${Math.round(seconds / 3600)}h old`;
}

const QUALITY_DETAIL: Record<string, string> = {
  CURRENT: "Every open position is valued at its own current mark.",
  DEGRADED: "At least one mark is stale, delayed or restored from disk. Equity is shown, but it is not a current valuation.",
  PARTIAL: "At least one open position has no mark. Total equity and unrealized P&L are unavailable; nothing is valued at zero.",
  UNAVAILABLE: "No open position has a mark. Total equity and unrealized P&L are unavailable; nothing is valued at zero.",
};

export function valuationQuality(valuation: PaperValuation): { label: string; detail: string; current: boolean } {
  const detail = QUALITY_DETAIL[valuation.quality] ?? "Valuation quality is not recognised; treat equity as not current.";
  const names = [...valuation.missing_mark_instruments.map((id) => `${id} (no mark)`), ...valuation.degraded_instruments.map((id) => `${id} (not current)`)];
  return {
    label: valuation.quality,
    detail: names.length ? `${detail} Affected: ${names.join(", ")}.` : detail,
    current: valuation.quality === "CURRENT",
  };
}

function executionLabel(mode: string): string {
  if (mode === "INTERNAL_SIMULATION") return "Internal Paper simulation";
  if (mode === "BROKER_PAPER") return "Broker paper account";
  return `${humanizeEnum(mode)} (simulated)`;
}

export type BoundaryModel = {
  headline: string;
  dataLine: string;
  executionLine: string;
  capitalLine: string;
  ordersBlocked: boolean;
};

/** Market-data identity and execution identity are described independently. */
export function boundaryModel(boundary: PaperBoundary): BoundaryModel {
  const { market_data: data, execution, capital } = boundary;
  const provider = data.provider || "provider unavailable";
  const simulated = "SIMULATED PAPER EXECUTION";
  let headline: string;
  let dataLine: string;
  let ordersBlocked = false;
  if (data.state === "MARKET_DATA_UNAVAILABLE") {
    headline = `MARKET DATA UNAVAILABLE + ${simulated}`;
    dataLine = `This experiment uses ${humanizeEnum(data.mode)} data, but the platform is running ${humanizeEnum(data.running_mode)}. Orders are blocked until the experiment's data mode is running again.`;
    ordersBlocked = true;
  } else if (data.mode === "LIVE_OBSERVATIONAL" && data.state === "AVAILABLE") {
    headline = `LIVE/CURRENT MARKET DATA + ${simulated}`;
    dataLine = `Market data: live observational feed from ${provider}.`;
  } else if (data.mode === "LIVE_OBSERVATIONAL") {
    headline = `LIVE MARKET DATA NOT YET VERIFIED + ${simulated}`;
    dataLine = `Market data: live observational feed from ${provider}, not yet verified healthy since restart. Execution is deferred until it is.`;
    ordersBlocked = true;
  } else {
    headline = `${humanizeEnum(data.mode).toUpperCase()} DATA (NOT LIVE MARKET DATA) + ${simulated}`;
    dataLine = `Market data: ${humanizeEnum(data.mode)} from ${provider}. This is not a live market feed.`;
  }
  return {
    headline,
    dataLine,
    executionLine: `Execution: ${executionLabel(execution.mode)} (${execution.provider}). Fills are simulated, never exchange or broker fills.`,
    capitalLine: capital.live_capital ? "Capital state is inconsistent — do not trade." : "Live capital: No. All capital is simulated.",
    ordersBlocked,
  };
}

const DECISION_SOURCE: Record<string, string> = {
  AI_DECISION_GOVERNED: "Governed AI decision",
  MANUAL_TEST: "Operator ticket (no governed decision)",
};

export function decisionSourceLabel(source: string): string {
  return DECISION_SOURCE[source] ?? humanizeEnum(source);
}

export function perShareCost(minor: number, currency: string, unit: string): string {
  return minor === 0 ? `${formatMoney(0, currency)} ${unit} (none charged)` : `${formatMoney(minor, currency)} ${unit}`;
}
