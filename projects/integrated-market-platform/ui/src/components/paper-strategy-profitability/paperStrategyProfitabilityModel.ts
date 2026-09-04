import type {
  PaperStrategyProfitabilityItem,
  PaperStrategyProfitabilityResponse,
} from "../../api/schemas";

export type PaperStrategyProfitabilityRow = {
  allocationId: string;
  strategyId: string;
  instrumentId: string;
  quantity: number;
  fillCount: number;
  fillIds: string[];
  attributedPnlMinor: number | null;
  attributionId: string | null;
  settlementState: string;
  lineageIds: string[];
};

export type PaperStrategyProfitabilityModel = {
  rows: PaperStrategyProfitabilityRow[];
  allocationCount: number;
  settledCount: number;
  ledgerRealizedPnlMinor: number;
  ledgerUnrealizedPnlMinor: number;
  strategyAttribution: {
    realizedPnlMinor: number | null;
    isAdditive: false;
    label: string;
  };
};

export function buildPaperStrategyProfitabilityModel(
  payload: PaperStrategyProfitabilityResponse,
): PaperStrategyProfitabilityModel {
  const rows = payload.items.map(toRow);
  return {
    rows,
    allocationCount: rows.length,
    settledCount: rows.filter((row) => row.settlementState === "SETTLED").length,
    ledgerRealizedPnlMinor: payload.account_ledger_pnl.realized_pnl_minor,
    ledgerUnrealizedPnlMinor: payload.account_ledger_pnl.unrealized_pnl_minor,
    strategyAttribution: {
      realizedPnlMinor: null,
      isAdditive: false,
      label: "Latest complete snapshots · non-additive",
    },
  };
}

function toRow(item: PaperStrategyProfitabilityItem): PaperStrategyProfitabilityRow {
  const forecast = item.forecast as { target?: { instrument_id?: string } } | null;
  const strategyMatch = item.strategy_match as { strategy_id?: string } | null;
  const attribution = item.attribution;
  const fillIds = item.fills
    .map((fill) => getString(fill, "fill_id"))
    .filter(Boolean);
  const lineageIds = [
    item.allocation.allocation_decision_id,
    getString(item.strategy_match, "match_id"),
    getString(item.forecast, "forecast_id"),
    attribution?.attribution_id ?? "",
  ].filter(Boolean);

  return {
    allocationId: item.allocation.allocation_decision_id,
    strategyId: strategyMatch?.strategy_id ?? "Strategy unavailable",
    instrumentId: forecast?.target?.instrument_id ?? "Instrument unavailable",
    quantity: attribution?.allocation_quantity ?? 0,
    fillCount: item.fills.length,
    fillIds,
    attributedPnlMinor: attribution?.trading_outcome.realized_pnl_minor ?? null,
    attributionId: attribution?.attribution_id ?? null,
    settlementState: item.settlement.state,
    lineageIds,
  };
}

function getString(value: Record<string, unknown> | null, key: string): string {
  const candidate = value?.[key];
  return typeof candidate === "string" ? candidate : "";
}
