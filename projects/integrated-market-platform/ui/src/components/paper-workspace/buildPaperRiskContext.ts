import type { PaperPortfolioResponse } from "../../api/client";
import { paperRiskMetrics } from "../paper-now/paperDashboardViewModel";

export type PaperRiskContextItem = {
  id: string;
  label: string;
  value: string;
  detail?: string;
  unavailable?: boolean;
};

export type PaperRiskContextModel = {
  phase: "loading" | "ready" | "error" | "unavailable";
  items: PaperRiskContextItem[];
  warnings: string[];
  paperActionsAvailable: boolean;
  symbolPosition: string | null;
  openOrdersForSymbol: number;
};

function recordString(value: unknown, keys: string[]): string | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const row = value as Record<string, unknown>;
  for (const key of keys) {
    if (typeof row[key] === "string" && row[key]) return row[key] as string;
  }
  return undefined;
}

export function buildPaperRiskContext(
  portfolio: PaperPortfolioResponse | undefined,
  symbol: string,
  paperActionsAvailable: boolean,
  phase: "loading" | "ready" | "error",
): PaperRiskContextModel {
  if (phase === "loading") {
    return {
      phase: "loading",
      items: [],
      warnings: [],
      paperActionsAvailable,
      symbolPosition: null,
      openOrdersForSymbol: 0,
    };
  }

  if (phase === "error" || !portfolio) {
    return {
      phase: phase === "error" ? "error" : "unavailable",
      items: [],
      warnings: ["Risk context is unavailable. Workspace evidence remains readable, but Paper order submission is disabled."],
      paperActionsAvailable: false,
      symbolPosition: null,
      openOrdersForSymbol: 0,
    };
  }

  const normalizedSymbol = symbol.trim().toUpperCase();
  const positions = portfolio.positions ?? [];
  const orders = portfolio.orders ?? [];
  const position = positions.find(
    (row) =>
      (row.symbol ?? "").toUpperCase() === normalizedSymbol ||
      (row.instrument_id ?? "").toUpperCase() === normalizedSymbol,
  );
  const openOrdersForSymbol = orders.filter((order) => {
    const orderSymbol = recordString(order, ["symbol", "instrument_id"])?.toUpperCase();
    return orderSymbol === normalizedSymbol;
  }).length;

  const items: PaperRiskContextItem[] = [
    {
      id: "session",
      label: "Paper session",
      value: portfolio.account.session_id ? "Open" : "Unavailable",
      detail: `${portfolio.account.execution_mode.replace(/_/g, " ")} · ${portfolio.account.execution_authority.replace(/_/g, " ")}`,
    },
    {
      id: "authority",
      label: "Paper actions",
      value: paperActionsAvailable ? "Available" : "Unavailable",
      unavailable: !paperActionsAvailable,
    },
    ...paperRiskMetrics(portfolio)
      .filter((metric) => ["buying-power", "reserved-cash", "equity", "gross-exposure", "gross-notional", "open-orders", "largest-position"].includes(metric.id))
      .map((metric) => ({
        id: metric.id,
        label: metric.label,
        value: metric.value,
        detail: metric.detail,
        unavailable: !metric.available,
      })),
  ];

  if (position) {
    items.push({
      id: "symbol-position",
      label: `${normalizedSymbol} position`,
      value: `${position.quantity} sh (${position.side})`,
      detail: position.mark_display ?? undefined,
    });
  }

  const warnings: string[] = [];
  if (!paperActionsAvailable) {
    warnings.push("Paper authority unavailable — preview and submit are disabled.");
  }
  if (portfolio.risk.kill_switch_active) {
    warnings.push("Kill switch is active.");
  }
  if (portfolio.account.valuation_quality === "INCOMPLETE") {
    warnings.push(`Valuation incomplete${portfolio.account.valuation_reasons?.length ? ` — ${portfolio.account.valuation_reasons.join(", ")}` : "."}`);
  }
  const reconciliation = (portfolio.reconciliation_status ?? portfolio.risk.reconciliation_status).toUpperCase();
  if (!["PASS", "HEALTHY", "CLEAN", "RECONCILED", "INTERNAL_AUTHORITATIVE"].includes(reconciliation)) {
    warnings.push(`Reconciliation: ${reconciliation}.`);
  }

  return {
    phase: "ready",
    items,
    warnings,
    paperActionsAvailable,
    symbolPosition: position ? `${position.quantity} sh` : null,
    openOrdersForSymbol,
  };
}
