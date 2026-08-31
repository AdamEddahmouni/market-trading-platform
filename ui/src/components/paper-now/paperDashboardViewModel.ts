import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";

export type PaperRiskMetric = { id: string; label: string; value: string; detail?: string; available: boolean; percent?: number };
export type PaperException = { code: string; severity: 0 | 1 | 2; message: string; detail?: string };
export type LimitUtilization = { raw: number; limit: number; percent: number; available: boolean };

const HEALTHY = new Set(["PASS", "HEALTHY", "CURRENT", "AVAILABLE"]);
const RECONCILED = new Set(["PASS", "HEALTHY", "CLEAN", "RECONCILED", "INTERNAL_AUTHORITATIVE"]);
const PROBLEM_ORDER_STATE = /(BLOCKED|REJECTED|WAITING|FAILED)/;

function recordString(value: unknown, keys: string[]): string | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const row = value as Record<string, unknown>;
  for (const key of keys) if (typeof row[key] === "string" && row[key]) return row[key] as string;
  return undefined;
}

export function sortPaperCandidates(items: AttentionItem[]): AttentionItem[] {
  return [...items].sort((left, right) => left.priority_rank - right.priority_rank);
}

export function nextPaperCandidateId(items: AttentionItem[], currentId: string | null): string | null {
  const eligible = sortPaperCandidates(items).filter((item) => Boolean(item.instrument_id?.trim()));
  if (currentId && eligible.some((item) => item.attention_id === currentId)) return currentId;
  return eligible[0]?.attention_id ?? null;
}

export function formatMinorCurrency(minor: number, currency: string): string | null {
  if (!Number.isFinite(minor) || !currency) return null;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(minor / 100);
  } catch { return null; }
}

function utilization(raw: number, limit: number): LimitUtilization {
  const available = Number.isFinite(raw) && Number.isFinite(limit) && limit > 0;
  return { raw, limit, available, percent: available ? Math.min(100, Math.max(0, (Math.abs(raw) / limit) * 100)) : 0 };
}

export function paperRiskMetrics(portfolio: PaperPortfolioResponse): PaperRiskMetric[] {
  const largest = Math.max(0, ...portfolio.positions.map((position) => Math.abs(position.quantity)));
  const positionUse = utilization(largest, portfolio.risk.limits.max_position_shares);
  const orderUse = utilization(portfolio.risk.open_order_count, portfolio.risk.limits.max_open_orders);
  const buyingPower = formatMinorCurrency(portfolio.account.buying_power_minor, portfolio.account.currency);
  return [
    { id: "total-pnl", label: "Total P&L", value: portfolio.pnl?.total_display ?? portfolio.account.realized_pnl_display, available: true },
    { id: "buying-power", label: "Buying power", value: buyingPower ?? "Unavailable", available: buyingPower !== null },
    { id: "gross-exposure", label: "Gross exposure", value: `${portfolio.exposure?.gross_shares ?? 0} sh`, available: true },
    { id: "largest-position", label: "Largest position", value: positionUse.available ? `${positionUse.raw} / ${positionUse.limit} sh` : "Unavailable", detail: positionUse.available ? "Position share limit" : "Position limit unavailable", available: positionUse.available, percent: positionUse.available ? positionUse.percent : undefined },
    { id: "open-orders", label: "Open orders", value: orderUse.available ? `${orderUse.raw} / ${orderUse.limit}` : "Unavailable", detail: orderUse.available ? "Open-order limit" : "Open-order limit unavailable", available: orderUse.available, percent: orderUse.available ? orderUse.percent : undefined },
  ];
}

export function derivePaperExceptions(portfolio: PaperPortfolioResponse): PaperException[] {
  const rows: Array<PaperException & { sourceOrder: number }> = [];
  let sourceOrder = 0;
  const add = (item: PaperException) => rows.push({ ...item, sourceOrder: sourceOrder++ });
  if (portfolio.risk.kill_switch_active) add({ code: "KILL_SWITCH_ACTIVE", severity: 0, message: "Kill switch is active." });
  const health = portfolio.data_health.state.toUpperCase();
  if (!HEALTHY.has(health)) add({ code: `DATA_${health}`, severity: 0, message: `Data health is ${health}.`, detail: portfolio.data_health.detail });
  const reconciliation = (portfolio.reconciliation_status ?? portfolio.risk.reconciliation_status).toUpperCase();
  if (!RECONCILED.has(reconciliation)) add({ code: `RECONCILIATION_${reconciliation}`, severity: 0, message: `Reconciliation is ${reconciliation}.` });
  const decision = recordString(portfolio.risk.last_decision, ["risk_status", "decision", "status"]);
  if (decision && decision.toUpperCase() !== "PASS") add({ code: `RISK_${decision.toUpperCase()}`, severity: 1, message: `Last risk decision: ${decision}.`, detail: recordString(portfolio.risk.last_decision, ["reason_code", "reason", "decision_code"]) });
  portfolio.orders.forEach((order) => {
    const state = recordString(order, ["state", "status", "order_state"]);
    if (state && PROBLEM_ORDER_STATE.test(state.toUpperCase())) add({ code: `ORDER_${state.toUpperCase()}`, severity: 1, message: `Order ${recordString(order, ["order_id", "id"]) ?? "state"}: ${state}.` });
  });
  portfolio.positions.forEach((position) => {
    const quality = position.mark_quality?.toUpperCase();
    if (quality && !HEALTHY.has(quality)) add({ code: `MARK_${quality}`, severity: 2, message: `${position.symbol} mark is ${quality}.` });
  });
  return rows.sort((left, right) => left.severity - right.severity || left.sourceOrder - right.sourceOrder).slice(0, 5).map(({ sourceOrder: _sourceOrder, ...item }) => item);
}
