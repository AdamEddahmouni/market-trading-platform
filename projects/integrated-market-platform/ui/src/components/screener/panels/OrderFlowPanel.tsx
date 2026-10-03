import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchOrderFlow, type OrderFlowPayload } from "../../../api/screenerPanels";
import type { ScreenerRow, ScreenerUniverse } from "../../../api/screener";
import { Age, EntitlementNote, ErrorDetail, etClock, marketClock, marketPrice, marketSize, marketVolume, PanelFrame, PanelMessage, providerLabel, reasonText, selectionGate, signedMarketVolume, usePanelVisible, useSelection } from "./shared";
import { OpenDConnect } from "../setup/Remedy";
import FlowHistory from "./FlowHistory";

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

export function windowLabel(window: OrderFlowPayload["window"], clock: (iso: string | null | undefined) => string = etClock) {
  if (!window) return "";
  return window.basis === "LAST_N_CAPTURED" ? `Last ${window.max_records} captured trades` : `Captured since subscription ${clock(window.anchor_at)}`;
}

type Market = { universe: ScreenerUniverse; row: ScreenerRow | null };

function Summary({ data, market }: { data: OrderFlowPayload; market: Market }) {
  const summary = data.summary!;
  const coverage = summary.classified_volume_pct;
  const methods = Object.keys(summary.methods).filter((method) => method !== "UNCLASSIFIED").map((method) => METHOD_LABELS[method] ?? method);
  // Only when every classified print carries the venue's own taker side is the direction observed, not inferred.
  const native = summary.native_count > 0 && summary.inferred_count === 0;
  const prefix = native ? "Taker" : "Inf.";
  return <>
    <dl className="screener-flow-stats">
      <div><dt>Trades</dt><dd>{summary.trade_count.toLocaleString()}</dd></div>
      <div><dt>{prefix} buy vol</dt><dd className="screener-positive">{marketVolume(summary.buy_volume, market.universe)}</dd></div>
      <div><dt>{prefix} sell vol</dt><dd className="screener-negative">{marketVolume(summary.sell_volume, market.universe)}</dd></div>
      <div><dt>Unknown vol</dt><dd>{marketVolume(summary.unknown_volume, market.universe)}</dd></div>
      <div><dt>Net signed</dt><dd className={summary.net_signed_volume > 0 ? "screener-positive" : summary.net_signed_volume < 0 ? "screener-negative" : undefined}>{signedMarketVolume(summary.net_signed_volume, market.universe)}</dd></div>
      <div><dt>Classified</dt><dd className={coverage != null && coverage < 70 ? "screener-warn" : undefined}>{coverage == null ? "—" : `${coverage.toFixed(0)}%`}</dd></div>
      <div><dt>Rate</dt><dd>{summary.trades_per_minute == null ? "—" : `${summary.trades_per_minute.toFixed(1)}/min`}</dd></div>
    </dl>
    <p className="screener-panel-note">{windowLabel(data.window, marketClock(market.universe).clock)} · {native
      ? `Direction is the venue-reported taker side${summary.unknown_count ? `; ${summary.unknown_count} prints unclassified` : ""}${market.universe === "CRYPTO" && market.row ? `. Volume in ${market.row.base_asset}` : ""}.`
      : `Direction ${methods.length ? `inferred from ${methods.join(", ")}` : "unclassified"}; not a known buyer or seller.`}
      {summary.large_print_threshold != null ? ` L = print ≥ ${marketVolume(summary.large_print_threshold, market.universe)} (10× median size).` : ""}</p>
  </>;
}

function Tape({ data, market }: { data: OrderFlowPayload; market: Market }) {
  const { clock, suffix } = marketClock(market.universe);
  if (!data.tape.length) return <PanelMessage>{data.state === "SESSION_CLOSED" ? "No trades captured this session." : "Subscribed; no trades printed yet."}</PanelMessage>;
  return <div className="screener-panel-scroll" tabIndex={0} aria-label="Recent trades, newest first">
    <table className="screener-panel-table screener-tape">
      <caption className="sr-only">Recent trades for {market.row?.symbol ?? data.instrument_id}, newest first</caption>
      <thead><tr><th scope="col">Time</th><th scope="col">Price</th><th scope="col">Size</th><th scope="col">Side</th><th scope="col">Cond.</th></tr></thead>
      <tbody>{data.tape.map((trade) => <tr key={trade.trade_id} className={`${trade.aggressor.side?.toLowerCase() ?? "unknown"}${trade.large ? " large" : ""}`}>
        <td>{clock(trade.event_time).replace(suffix, "")}</td><td>{marketPrice(trade.price, market.row, market.universe)}</td>
        <td>{trade.large ? <abbr title="Large print">L </abbr> : null}{marketSize(trade.size, market.universe)}</td>
        <td title={`${trade.aggressor.state} · ${METHOD_LABELS[trade.aggressor.method] ?? trade.aggressor.method}`}>{sideLabel(trade.aggressor)}</td>
        <td>{trade.condition ?? ""}</td></tr>)}</tbody>
    </table>
  </div>;
}

export default function OrderFlowPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  const query = useQuery({
    queryKey: ["screener-order-flow", universe, settledId],
    queryFn: ({ signal }) => universe === "US_EQUITIES" ? fetchOrderFlow(settledId!, signal) : fetchOrderFlow(settledId!, signal, universe),
    enabled: Boolean(settledId) && visible,
    refetchInterval: (current) => visible ? (current.state.data?.state === "CURRENT" ? 1_000 : 3_000) : false,
    retry: 1,
  });
  const gate = selectionGate("order_flow", row, settledId);
  const data = query.data && query.data.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  const market = { universe, row };
  const clock = data?.latest_received_at ? <>last print {marketClock(universe).clock(data.latest_event_at)} · rcvd <Age iso={data.latest_received_at} staleMs={10_000} /> ago</> : null;
  return <PanelFrame decisionInputs={data?.decision_inputs} id="order_flow" state={data?.state} detail={data ? `Trades · ${providerLabel(data.provider)}` : null} clock={clock}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">Order Flow request failed.<ErrorDetail error={query.error} /> <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row!.symbol}…</PanelMessage>
      : BLOCKED.has(data.state) ? <PanelMessage tone={data.state === "CONNECTING" ? "muted" : "warn"}>{reasonText(data.reason) || data.state}<OpenDConnect reason={data.reason} /></PanelMessage>
      : <>
        {data.state !== "CURRENT" && <PanelMessage tone="warn">{data.state === "SESSION_CLOSED" ? "Session closed · last captured flow" : reasonText(data.reason)}</PanelMessage>}
        {data.summary && data.summary.trade_count > 0 && <Summary data={data} market={market} />}
        <FlowHistory key={`${universe}:${settledId}`} instrument={settledId!} universe={universe} visible={visible} mode="delta" />
        <Tape data={data} market={market} />
        <EntitlementNote entitlement={data.entitlement} />
      </>)}
  </PanelFrame>;
}
