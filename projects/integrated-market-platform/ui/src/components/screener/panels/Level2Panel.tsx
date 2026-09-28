import { useLayoutEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchDepth, type DepthPayload } from "../../../api/screenerPanels";
import { age, EntitlementNote, etClock, money, PanelFrame, PanelMessage, reasonText, selectionGate, usePanelVisible, useSelection } from "./shared";

// Ladder values are shown only for these states; STALE and SESSION_CLOSED are dimmed and labelled.
const SHOWN = new Set(["CURRENT", "PARTIAL", "STALE", "SESSION_CLOSED"]);
const DIMMED = new Set(["STALE", "SESSION_CLOSED"]);

function Ladder({ data }: { data: DepthPayload }) {
  const maxSize = Math.max(1, ...data.bids.map((level) => level.size), ...data.asks.map((level) => level.size));
  const bar = (size: number) => `${Math.max(2, (size / maxSize) * 100)}%`;
  const asks = [...data.asks].reverse();
  const scrollRef = useRef<HTMLDivElement>(null);
  const spreadRef = useRef<HTMLTableRowElement>(null);
  // Open centred on the inside market; later updates keep the trader's scroll position.
  useLayoutEffect(() => {
    const box = scrollRef.current, spread = spreadRef.current;
    if (box && spread) box.scrollTop = Math.max(0, spread.offsetTop - (box.clientHeight - spread.offsetHeight) / 2);
  }, [data.instrument_id]);
  return <div ref={scrollRef} className={`screener-panel-scroll${DIMMED.has(data.state) ? " dimmed" : ""}`} tabIndex={0} aria-label="Order book ladder">
    <table className="screener-panel-table screener-ladder">
      <caption className="sr-only">{`${data.instrument_id} displayed depth: ${data.asks.length} ask and ${data.bids.length} bid levels${DIMMED.has(data.state) ? `, ${data.state === "STALE" ? "stale" : "session closed, last captured"}` : ""}`}</caption>
      <thead><tr><th scope="col">Side</th><th scope="col">Price</th><th scope="col">Size</th><th scope="col">Cum</th><th scope="col"><span className="sr-only">Relative size</span></th></tr></thead>
      <tbody>
        {asks.map((level, index) => <tr key={`a${level.price}`} className={`ask${index === asks.length - 1 ? " best" : ""}`}>
          <th scope="row">{index === asks.length - 1 ? "Best ask" : "Ask"}</th><td>{money(level.price)}</td><td>{level.size.toLocaleString()}</td>
          <td>{level.cumulative_size.toLocaleString()}</td><td aria-hidden="true"><span className="screener-ladder-bar" style={{ width: bar(level.size) }} /></td></tr>)}
        <tr className="spread" ref={spreadRef}><th scope="row">Spread</th><td colSpan={4}>{data.spread == null ? "No two-sided spread" : `${money(data.spread)}${data.spread_bps != null ? ` · ${data.spread_bps.toFixed(1)} bps` : ""}${data.mid != null ? ` · mid ${money(data.mid)}` : ""}`}</td></tr>
        {data.bids.map((level, index) => <tr key={`b${level.price}`} className={`bid${index === 0 ? " best" : ""}`}>
          <th scope="row">{index === 0 ? "Best bid" : "Bid"}</th><td>{money(level.price)}</td><td>{level.size.toLocaleString()}</td>
          <td>{level.cumulative_size.toLocaleString()}</td><td aria-hidden="true"><span className="screener-ladder-bar" style={{ width: bar(level.size) }} /></td></tr>)}
      </tbody>
    </table>
  </div>;
}

function Imbalance({ data }: { data: DepthPayload }) {
  if (!data.imbalance.length) return null;
  return <p className="screener-panel-note">Displayed-liquidity imbalance (bid share of resting size): {data.imbalance.map((item) =>
    `Top ${item.levels}${item.complete ? "" : ` (${item.bid_levels}/${item.ask_levels} levels)`} ${(item.bid_share * 100).toFixed(0)}% bid`).join(" · ")}. Resting orders, not executed trades.</p>;
}

export default function Level2Panel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  const query = useQuery({
    queryKey: ["screener-depth", universe, settledId],
    queryFn: ({ signal }) => universe === "US_EQUITIES" ? fetchDepth(settledId!, signal) : fetchDepth(settledId!, signal, universe),
    enabled: Boolean(settledId) && visible,
    refetchInterval: (current) => visible ? (["CURRENT", "PARTIAL", "STALE"].includes(current.state.data?.state ?? "") ? 1_000 : 3_000) : false,
    retry: 1,
  });
  const gate = selectionGate("level2", row, settledId);
  const data = query.data && query.data.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  const completeness = data?.completeness ? `MBP ${data.completeness.bid_levels}×${data.completeness.ask_levels} levels` : "MBP";
  const clock = data?.latest_received_at ? `book ${etClock(data.latest_event_at)} · rcvd ${age(data.latest_received_at)} ago${data.freshness ? ` · TTL ${data.freshness.ttl_ms / 1000}s` : ""}` : null;
  return <PanelFrame id="level2" state={data?.state} detail={data ? `${completeness} · ${data.provider === "MOOMOO" ? "Moomoo" : data.provider ?? "No provider"}` : null} clock={clock}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">Level 2 request failed. <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row!.symbol}…</PanelMessage>
      : !SHOWN.has(data.state) || (!data.bids.length && !data.asks.length) ? <>
        <PanelMessage tone={data.state === "CONNECTING" ? "muted" : "warn"}>{data.state === "SESSION_CLOSED" && !data.latest_received_at ? "Session closed · no book captured for this subscription" : reasonText(data.reason) || data.state}</PanelMessage>
        <EntitlementNote entitlement={data.entitlement} /></>
      : <>
        {data.state !== "CURRENT" && <PanelMessage tone="warn">{data.state === "SESSION_CLOSED" ? `Session closed · last captured book, received ${age(data.latest_received_at)} ago` : data.state === "STALE" ? `Stale · no book update for ${age(data.latest_received_at)}` : reasonText(data.reason)}</PanelMessage>}
        <Ladder data={data} />
        <Imbalance data={data} />
        <EntitlementNote entitlement={data.entitlement} />
        <p className="screener-panel-note">Provider MBP depth; venue coverage is not identified by the provider and is not the full consolidated market.</p>
      </>)}
  </PanelFrame>;
}
