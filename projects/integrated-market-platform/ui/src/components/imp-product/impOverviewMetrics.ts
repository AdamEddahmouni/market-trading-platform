import type { PaperPortfolioResponse } from "../../api/client";
import { resolveSemanticState } from "../../state/semanticState";

export type OverviewKpiCell = {
  id: string;
  label: string;
  value: string;
  detail?: string;
  tone?: "neutral" | "positive" | "negative" | "muted";
};

export type OverviewKpiState = "loading" | "ready" | "error" | "unavailable";

function unavailableCell(id: string, label: string): OverviewKpiCell {
  return { id, label, value: "—", detail: "Unavailable", tone: "muted" };
}

export function overviewKpisFromPortfolio(
  portfolio: PaperPortfolioResponse | undefined,
  state: OverviewKpiState,
): OverviewKpiCell[] {
  const labels = [
    { id: "cash", label: "Cash" },
    { id: "total-pnl", label: "Total P&L" },
    { id: "unrealized", label: "Open P&L" },
    { id: "positions", label: "Positions" },
    { id: "open-orders", label: "Open orders" },
  ];
  if (state === "loading") {
    return labels.map(({ id, label }) => ({ id, label, value: "…", tone: "muted" }));
  }
  if (state === "error" || !portfolio) {
    return labels.map(({ id, label }) => unavailableCell(id, label));
  }
  const unrealized = portfolio.pnl?.unrealized_display;
  return [
    { id: "cash", label: "Cash", value: portfolio.account.cash_display },
    {
      id: "total-pnl",
      label: "Total P&L",
      value: portfolio.pnl?.total_display ?? portfolio.account.realized_pnl_display,
    },
    {
      id: "unrealized",
      label: "Open P&L",
      value: unrealized && unrealized.trim() ? unrealized : "—",
      detail: unrealized ? undefined : "No open marks",
      tone: unrealized ? "neutral" : "muted",
    },
    {
      id: "positions",
      label: "Positions",
      value: String(portfolio.positions?.length ?? 0),
      detail: portfolio.exposure ? `${portfolio.exposure.gross_shares} gross sh` : undefined,
    },
    {
      id: "open-orders",
      label: "Open orders",
      value: String(portfolio.risk?.open_order_count ?? 0),
      detail: portfolio.data_health?.state,
    },
  ];
}

export function overviewKpisFromLiveContext(input: {
  state: OverviewKpiState;
  attentionCount?: number;
  dataMode?: string;
  executionAuthority?: string;
  providerName?: string;
  connectionState?: string;
  opportunityFeedStatus?: string;
}): OverviewKpiCell[] {
  const { state } = input;
  const slots = [
    { id: "data-mode", label: "Data mode" },
    { id: "authority", label: "Execution" },
    { id: "provider", label: "Provider" },
    { id: "connection", label: "Connection" },
    { id: "attention", label: "Attention queue" },
  ];
  if (state === "loading") {
    return slots.map(({ id, label }) => ({ id, label, value: "…", tone: "muted" }));
  }
  if (state === "error") {
    return slots.map(({ id, label }) => unavailableCell(id, label));
  }
  return [
    {
      id: "data-mode",
      label: "Data mode",
      value: input.dataMode
        ? resolveSemanticState("session", input.dataMode, {
            params: { provider: input.providerName },
          }).label
        : "—",
      detail: "Observational only",
    },
    {
      id: "authority",
      label: "Execution",
      value: input.executionAuthority
        ? resolveSemanticState("executionAuthority", input.executionAuthority).label
        : "—",
      detail: "Live execution off",
      tone: "muted",
    },
    {
      id: "provider",
      label: "Provider",
      value: input.providerName ?? "—",
    },
    {
      id: "connection",
      label: "Connection",
      value: input.connectionState
        ? resolveSemanticState("providerHealth", input.connectionState, {
            params: { provider: input.providerName },
          }).label
        : "—",
      detail: input.opportunityFeedStatus ? `Radar ${input.opportunityFeedStatus}` : undefined,
    },
    {
      id: "attention",
      label: "Attention queue",
      value: input.attentionCount != null ? String(input.attentionCount) : "—",
    },
  ];
}
