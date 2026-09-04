import type { LiveCanarySnapshot } from "../live-now/liveCanarySnapshot";

export type LivePortfolioMetric = {
  id: string;
  label: string;
  value: string;
};

export type LivePortfolioPositionRow = {
  id: string;
  symbol: string;
  quantity: string;
  detail?: string;
};

export type LivePortfolioOrderRow = {
  id: string;
  orderId: string;
  detail?: string;
};

export function livePortfolioMetrics(snapshot?: LiveCanarySnapshot): LivePortfolioMetric[] {
  if (!snapshot) return [];

  return [
    { id: "broker", label: "Broker", value: snapshot.broker ?? "—" },
    { id: "environment", label: "Account environment", value: snapshot.account_environment ?? "—" },
    {
      id: "fingerprint",
      label: "Account fingerprint",
      value: snapshot.account_fingerprint ?? "—",
    },
    { id: "broker-health", label: "Broker health", value: snapshot.broker_health },
    { id: "reconciliation", label: "Reconciliation", value: snapshot.reconciliation_health },
    { id: "program", label: "Program state", value: snapshot.program_state ?? "—" },
    { id: "session", label: "Session state", value: snapshot.session_state ?? "—" },
    {
      id: "authorization",
      label: "Authorization",
      value: snapshot.authorization_status ?? "NONE",
    },
    {
      id: "live-blocked",
      label: "Live blocked",
      value: snapshot.live_blocked ? "YES" : "NO",
    },
  ];
}

export function livePortfolioPositions(snapshot?: LiveCanarySnapshot): LivePortfolioPositionRow[] {
  if (!snapshot?.live_positions?.length) return [];

  return snapshot.live_positions.map((position, index) => {
    const symbol = String(position.symbol ?? position.instrument_id ?? `position-${index + 1}`);
    const quantity =
      position.quantity !== undefined && position.quantity !== null
        ? String(position.quantity)
        : "—";
    const side = position.side ? String(position.side) : undefined;
    return {
      id: `${symbol}-${index}`,
      symbol,
      quantity,
      detail: side,
    };
  });
}

export function livePortfolioOrders(snapshot?: LiveCanarySnapshot): LivePortfolioOrderRow[] {
  if (!snapshot?.open_broker_orders?.length) return [];

  return snapshot.open_broker_orders.map((order, index) => ({
    id: `order-${index}`,
    orderId: String(order.order_id ?? order.broker_order_id ?? `open-${index + 1}`),
    detail:
      order.side || order.quantity
        ? `${String(order.side ?? "—")} · ${String(order.quantity ?? "—")}`
        : undefined,
  }));
}

export function liveProgramCapMetrics(snapshot?: LiveCanarySnapshot): LivePortfolioMetric[] {
  if (!snapshot) return [];

  const usage = snapshot.program_cap_usage ?? {};
  const remaining = snapshot.program_cap_remaining ?? {};

  return [
    {
      id: "sessions-used",
      label: "Sessions completed",
      value: String(usage.sessions_completed ?? 0),
    },
    {
      id: "orders-used",
      label: "Orders submitted",
      value: String(usage.orders_submitted ?? 0),
    },
    {
      id: "notional-used",
      label: "Filled notional (minor)",
      value: String(usage.notional_minor ?? 0),
    },
    {
      id: "sessions-remaining",
      label: "Sessions remaining",
      value: String(remaining.sessions ?? "—"),
    },
    {
      id: "orders-remaining",
      label: "Orders remaining",
      value: String(remaining.orders ?? "—"),
    },
    {
      id: "notional-remaining",
      label: "Notional remaining (minor)",
      value: String(remaining.notional_minor ?? "—"),
    },
  ];
}
