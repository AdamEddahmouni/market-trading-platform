import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchFuturesContext, type FuturesContextPayload } from "../../../api/screenerPanels";
import { Age, ErrorDetail, etDay, PanelFrame, PanelMessage, reasonText, selectionGate, usePanelVisible, useSelection } from "./shared";

const RELATIONSHIPS: Record<string, string> = { BROAD_MARKET: "Broad market", SECTOR: "Sector", STYLE_FACTOR: "Style factor",
  UNDERLYING: "Underlying", MACRO_FACTOR: "Macro factor" };

function Item({ item }: { item: FuturesContextPayload["futures"]["items"][number] }) {
  const current = item.contract.state === "CURRENT";
  return <li className="screener-futures-row">
    <div className="screener-futures-id"><strong>{current ? item.contract.contract_id : item.root}</strong>
      <span className="screener-panel-chip">{RELATIONSHIPS[item.relationship_type] ?? item.relationship_type.replace(/_/g, " ").toLowerCase()}</span>
      <span className="screener-muted">{item.name}</span></div>
    <p>{item.relationship_reason}</p>
    {item.quote ? <div className="screener-futures-quote"><span>{item.quote.price.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
      {item.quote.change_pct != null && <span className={item.quote.change_pct >= 0 ? "screener-positive" : "screener-negative"}>{`${item.quote.change_pct > 0 ? "+" : ""}${item.quote.change_pct.toFixed(2)}%`}</span>}
      <span className={`screener-state ${item.quote.state.toLowerCase()}`}>{item.quote.state === "LIVE" ? "Live" : "Stale"} · {item.quote.price_basis === "MID" ? "mid · " : ""}{item.quote.provider}{item.quote.as_of ? <> · {etDay(item.quote.as_of)} (<Age iso={item.quote.as_of} /> ago)</> : ""}</span></div>
      : <div className="screener-futures-quote"><span className="screener-state unavailable">Price unavailable — {reasonText(item.unavailable_reason) || "no current feed"}</span></div>}
    <span className="screener-panel-note">{current ? `Contract ${item.contract.contract_id} · last trade ${item.contract.last_trade_date}` : `Contract ${item.contract.state.toLowerCase()} · ${reasonText(item.contract.reason)}`}</span>
  </li>;
}

export default function FuturesContextPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  const query = useQuery({
    queryKey: ["screener-futures-context", universe, settledId],
    queryFn: ({ signal }) => universe === "US_EQUITIES" ? fetchFuturesContext(settledId!, signal) : fetchFuturesContext(settledId!, signal, universe),
    enabled: Boolean(settledId) && visible, staleTime: 20_000, refetchInterval: visible ? 30_000 : false, retry: 1,
  });
  const gate = selectionGate("futures", row, settledId);
  const data = query.data && query.data.instrument.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  const priced = data?.futures.items.filter((item) => item.quote).length ?? 0;
  return <PanelFrame id="futures" detail={data ? `${data.futures.mapping_version} · context only` : null}
    state={data ? (priced ? "CURRENT" : "UNAVAILABLE") : null} clock={data ? `${priced}/${data.futures.items.length} priced` : null}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">Futures context request failed.<ErrorDetail error={query.error} /> <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row!.symbol}…</PanelMessage>
      : <>
        <p className="screener-panel-note">Related because {row!.symbol} is classified {data.instrument.sector ?? "without a sector"}{data.instrument.industry ? ` / ${data.instrument.industry}` : ""}.</p>
        <ul className="screener-futures-list">{data.futures.items.map((item) => <Item key={item.root} item={item} />)}</ul>
        <p className="screener-panel-note">{data.futures.causal_note}</p>
      </>)}
  </PanelFrame>;
}
