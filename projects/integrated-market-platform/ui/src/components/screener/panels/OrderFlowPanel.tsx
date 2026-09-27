import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchOrderFlow, type OrderFlowPayload } from "../../../api/screenerPanels";
import { age, compact, EntitlementNote, etClock, money, PanelFrame, PanelMessage, reasonText, selectionGate, signedCompact, usePanelVisible, useSelection } from "./shared";

const METHOD_LABELS: Record<string, string> = {
  PROVIDER_TICKER_DIRECTION: "provider ticker direction", EXCHANGE_NATIVE: "exchange-native side", LEE_READY: "Lee-Ready",
  QUOTE_MATCH: "quote match", TICK_RULE: "tick rule", BVC: "bulk volume", OTHER_INFERENCE: "model", UNCLASSIFIED: "unclassified",
};
const BLOCKED = new Set(["UNAVAILABLE", "NOT_ENTITLED", "DISCONNECTED", "CONNECTING", "SUBSCRIPTION_BUSY"]);

/** Aggressor wording never claims a known buyer or seller unless the side is exchange-native. */
export function sideLabel(aggressor: OrderFlowPayload["tape"][number]["aggressor"]) {
  if (aggressor.state === "UNKNOWN" || !aggressor.side) return "Unknown";
  const side = aggressor.side === "BUY" ? "Buy" : "Sell";
  return aggressor.state === "NATIVE" ? side : `Inf. ${side}`;
}

export function windowLabel(window: OrderFlowPayload["window"]) {
  if (!window) return "";
  return window.basis === "LAST_N_CAPTURED" ? `Last ${window.max_records} captured trades` : `Captured since subscription ${etClock(window.anchor_at)}`;
}

function Summary({ data }: { data: OrderFlowPayload }) {
  const summary = data.summary!;
  const coverage = summary.classified_volume_pct;
  const methods = Object.keys(summary.methods).filter((method) => method !== "UNCLASSIFIED").map((method) => METHOD_LABELS[method] ?? method);
  return <>
    <dl className="screener-flow-stats">
      <div><dt>Trades</dt><dd>{summary.trade_count.toLocaleString()}</dd></div>
      <div><dt>Inf. buy vol</dt><dd className="screener-positive">{compact(summary.buy_volume)}</dd></div>
      <div><dt>Inf. sell vol</dt><dd className="screener-negative">{compact(summary.sell_volume)}</dd></div>
      <div><dt>Unknown vol</dt><dd>{compact(summary.unknown_volume)}</dd></div>
      <div><dt>Net signed</dt><dd className={summary.net_signed_volume > 0 ? "screener-positive" : summary.net_signed_volume < 0 ? "screener-negative" : undefined}>{signedCompact(summary.net_signed_volume)}</dd></div>
      <div><dt>Classified</dt><dd className={coverage != null && coverage < 70 ? "screener-warn" : undefined}>{coverage == null ? "—" : `${coverage.toFixed(0)}%`}</dd></div>
      <div><dt>Rate</dt><dd>{summary.trades_per_minute == null ? "—" : `${summary.trades_per_minute.toFixed(1)}/min`}</dd></div>
    </dl>
    <p className="screener-panel-note">{windowLabel(data.window)} · Direction {methods.length ? `inferred from ${methods.join(", ")}` : "unclassified"}; not a known buyer or seller.
      {summary.large_print_threshold != null ? ` L = print ≥ ${compact(summary.large_print_threshold)} (10× median size).` : ""}</p>
  </>;
}

function Tape({ data }: { data: OrderFlowPayload }) {
  if (!data.tape.length) return <PanelMessage>{data.state === "SESSION_CLOSED" ? "No trades captured this session." : "Subscribed; no trades printed yet."}</PanelMessage>;
  return <div className="screener-panel-scroll" tabIndex={0} aria-label="Recent trades, newest first">
    <table className="screener-panel-table screener-tape">
      <caption className="sr-only">Recent trades for {data.instrument_id}, newest first</caption>
      <thead><tr><th scope="col">Time</th><th scope="col">Price</th><th scope="col">Size</th><th scope="col">Side</th><th scope="col">Cond.</th></tr></thead>
      <tbody>{data.tape.map((trade) => <tr key={trade.trade_id} className={`${trade.aggressor.side?.toLowerCase() ?? "unknown"}${trade.large ? " large" : ""}`}>
        <td>{etClock(trade.event_time).replace(" ET", "")}</td><td>{money(trade.price)}</td>
        <td>{trade.large ? <abbr title="Large print">L </abbr> : null}{trade.size.toLocaleString()}</td>
        <td title={`${trade.aggressor.state} · ${METHOD_LABELS[trade.aggressor.method] ?? trade.aggressor.method}`}>{sideLabel(trade.aggressor)}</td>
        <td>{trade.condition ?? ""}</td></tr>)}</tbody>
    </table>
  </div>;
}

export default function OrderFlowPanel({ api }: IDockviewPanelProps) {
  const { row, settledId } = useSelection();
  const visible = usePanelVisible(api);
  const query = useQuery({
    queryKey: ["screener-order-flow", settledId],
    queryFn: ({ signal }) => fetchOrderFlow(settledId!, signal),
    enabled: Boolean(settledId) && visible,
    refetchInterval: (current) => visible ? (current.state.data?.state === "CURRENT" ? 1_000 : 3_000) : false,
    retry: 1,
  });
  const gate = selectionGate("order_flow", row, settledId);
  const data = query.data && query.data.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  const clock = data?.latest_received_at ? `last print ${etClock(data.latest_event_at)} · rcvd ${age(data.latest_received_at)} ago` : null;
  return <PanelFrame id="order_flow" state={data?.state} detail={data ? `Trades · ${data.provider === "MOOMOO" ? "Moomoo" : data.provider ?? "No provider"}` : null} clock={clock}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">Order Flow request failed. <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row!.symbol}…</PanelMessage>
      : BLOCKED.has(data.state) ? <PanelMessage tone={data.state === "CONNECTING" ? "muted" : "warn"}>{reasonText(data.reason) || data.state}</PanelMessage>
      : <>
        {data.state !== "CURRENT" && <PanelMessage tone="warn">{data.state === "SESSION_CLOSED" ? "Session closed · last captured flow" : reasonText(data.reason)}</PanelMessage>}
        {data.summary && data.summary.trade_count > 0 && <Summary data={data} />}
        <Tape data={data} />
        <EntitlementNote entitlement={data.entitlement} />
      </>)}
  </PanelFrame>;
}
