import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchScreenerOptions, type OptionContractRow, type OptionsFields, type OptionsPayload } from "../../../api/screenerOptions";
import { ago, count, DASH, etTime, expiry, greek, hasChain, iv, OPTIONS_BADGE, OPTIONS_STATE_LABELS, pct, price, ratio, snapshotAge, stateMessage } from "../options/optionsFormat";
import { ErrorDetail, PanelFrame, PanelMessage, selectionGate, useNow, usePanelVisible, useSelection } from "./shared";

/** The chain is a provider snapshot: re-read the endpoint once a minute; the backend refreshes Finviz at its cache TTL. */
export const OPTIONS_POLL_MS = 60_000;
/** Deterministic emphasis thresholds (documented in SCREENER_S7_OPTIONS.md). */
export const HOT_VOLUME_PERCENTILE = 0.9;
export const HOT_VOLUME_MIN_SAMPLES = 5;
export const WIDE_SPREAD_PCT = 25;

type Column = { key: string; label: string; title: string; supplied: (fields: OptionsFields) => boolean;
  cell: (row: OptionContractRow, hot: number | null) => ReactNode; className?: (row: OptionContractRow) => string | undefined };
const wide = (row: OptionContractRow) => row.spread_pct != null && row.spread_pct > WIDE_SPREAD_PCT ? "wide" : undefined;
const BASE: Column[] = [
  { key: "bid", label: "Bid", title: "Bid", supplied: (f) => f.bid, cell: (row) => price(row.bid), className: wide },
  { key: "ask", label: "Ask", title: "Ask", supplied: (f) => f.ask, cell: (row) => price(row.ask), className: wide },
  { key: "volume", label: "Vol", title: "Volume (latest session)", supplied: (f) => f.volume, className: () => "vol",
    cell: (row, hot) => <>{hot != null && row.volume != null && row.volume >= hot ? <strong>{count(row.volume)}</strong> : count(row.volume)}
      {row.volume_oi_ratio != null && row.volume_oi_ratio > 1 ? <abbr title={`Volume / OI ${row.volume_oi_ratio.toFixed(2)}: volume above open interest`}>▲</abbr> : null}</> },
  { key: "oi", label: "OI", title: "Open interest", supplied: (f) => f.open_interest, cell: (row) => count(row.open_interest) },
  { key: "iv", label: "IV", title: "Implied volatility (provider)", supplied: (f) => f.iv, cell: (row) => iv(row.iv) },
  { key: "delta", label: "Δ", title: "Delta (provider)", supplied: (f) => f.delta, cell: (row) => greek(row.delta, 2) },
];
const DETAIL: Column[] = [
  { key: "last", label: "Last", title: "Last trade price", supplied: (f) => f.last, cell: (row) => price(row.last) },
  { key: "mid", label: "Mid", title: "Midpoint (bid + ask) / 2", supplied: (f) => f.bid && f.ask, cell: (row) => price(row.mid) },
  { key: "spread", label: "Sprd", title: "Spread as % of midpoint", supplied: (f) => f.bid && f.ask, cell: (row) => pct(row.spread_pct), className: wide },
  { key: "gamma", label: "Γ", title: "Gamma (provider)", supplied: (f) => f.gamma, cell: (row) => greek(row.gamma, 4) },
  { key: "theta", label: "Θ", title: "Theta (provider)", supplied: (f) => f.theta, cell: (row) => greek(row.theta, 3) },
  { key: "vega", label: "Vega", title: "Vega (provider)", supplied: (f) => f.vega, cell: (row) => greek(row.vega, 3) },
];

/** Volume at or above the expiry's 90th percentile of non-zero volumes; none with fewer than 5 samples. */
export function hotVolumeThreshold(rows: OptionContractRow[]) {
  const volumes = rows.map((row) => row.volume).filter((value): value is number => value != null && value > 0).sort((a, b) => a - b);
  if (volumes.length < HOT_VOLUME_MIN_SAMPLES) return null;
  return volumes[Math.min(volumes.length - 1, Math.floor(volumes.length * HOT_VOLUME_PERCENTILE))];
}

type StrikeRow = { strike: number; call?: OptionContractRow; put?: OptionContractRow };
function byStrike(rows: OptionContractRow[]): StrikeRow[] {
  const map = new Map<number, StrikeRow>();
  for (const row of rows) {
    const entry = map.get(row.strike) ?? { strike: row.strike };
    if (row.type === "CALL") entry.call = row; else entry.put = row;
    map.set(row.strike, entry);
  }
  return [...map.values()].sort((a, b) => a.strike - b.strike);
}

function Summary({ data }: { data: OptionsPayload }) {
  const all = data.summary!;
  const items: Array<[string, string, string]> = [
    ["Call Vol", count(all.call_volume), "Total call volume, all listed expiries"],
    ["Put Vol", count(all.put_volume), "Total put volume, all listed expiries"],
    ["P/C Vol", ratio(all.put_call_volume_ratio), "Put volume ÷ call volume; undefined when call volume is zero or unavailable"],
    ["Call OI", count(all.call_open_interest), "Total call open interest"],
    ["Put OI", count(all.put_open_interest), "Total put open interest"],
    ["P/C OI", ratio(all.put_call_oi_ratio), "Put open interest ÷ call open interest; undefined when call OI is zero or unavailable"],
    ["Contracts", count(all.contracts), "Current (non-expired) contracts"],
    ["Expiries", count(all.expirations), "Listed current expiries"],
  ];
  return <dl className="screener-flow-stats screener-options-stats" aria-label="Chain summary, all expiries">
    {items.map(([label, value, title]) => <div key={label} title={title}><dt>{label}</dt><dd>{value}</dd></div>)}
  </dl>;
}

function ExpiryLine({ data }: { data: OptionsPayload }) {
  const summary = data.expiry_summary;
  const near = summary?.nearest_strike;
  if (!summary) return null;
  return <p className="screener-panel-note screener-options-expiry-line">
    <span>This expiry: Call vol {count(summary.call_volume)} · Put vol {count(summary.put_volume)} · P/C vol {ratio(summary.put_call_volume_ratio)} · P/C OI {ratio(summary.put_call_oi_ratio)}</span>
    {near ? <span title={`Strike closest to the underlying $${price(near.basis_price)}; not an exact at-the-money claim`}> · Nearest strike {near.strike} · IV C {iv(near.call_iv)} / P {iv(near.put_iv)}</span> : null}
    <span> · Median spread {pct(summary.median_spread_pct)} ({count(summary.two_sided)} two-sided)</span>
  </p>;
}

function Chain({ data, detail }: { data: OptionsPayload; detail: boolean }) {
  const fields = data.fields_supplied!;
  const columns = useMemo(() => [...BASE, ...(detail ? DETAIL : [])].filter((column) => column.supplied(fields)), [fields, detail]);
  const rows = useMemo(() => byStrike(data.contracts), [data.contracts]);
  const hot = useMemo(() => hotVolumeThreshold(data.contracts), [data.contracts]);
  const underlying = data.underlying?.price ?? null;
  const nearest = data.expiry_summary?.nearest_strike?.strike ?? null;
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearestRef = useRef<HTMLTableRowElement>(null);
  const anchor = `${data.instrument_id}|${data.selected_expiration}`;
  useEffect(() => {
    // Centre the nearest strike inside the panel only; the page itself never scrolls.
    // Without an underlying price there is no nearest strike: open at the middle strike, not the lowest.
    const container = scrollRef.current, row = nearestRef.current;
    if (container) container.scrollTop = Math.max(0, (row ? row.offsetTop : container.scrollHeight / 2) - container.clientHeight / 2);
  }, [anchor]);
  const callColumns = [...columns].reverse();
  const cells = (row: OptionContractRow | undefined, side: "call" | "put", cols: Column[], itm: boolean) =>
    cols.map((column) => <td key={`${side}-${column.key}`} className={[side, itm ? "itm" : "", row ? column.className?.(row) ?? "" : ""].join(" ").trim() || undefined}>
      {row ? column.cell(row, hot) : DASH}</td>);
  return <div className="screener-panel-scroll screener-options-scroll" ref={scrollRef} tabIndex={0} role="region"
    aria-label={`${data.symbol} option chain, ${expiry(data.selected_expiration)}`}>
    <table className="screener-panel-table screener-options-chain">
      <caption className="sr-only">{data.symbol} calls and puts expiring {expiry(data.selected_expiration)}, by strike. {underlying != null ? `Underlying ${price(underlying)}; nearest strike ${nearest}.` : "Underlying price unavailable."}</caption>
      <thead>
        <tr><th scope="colgroup" colSpan={columns.length} className="side call">Calls</th><th scope="col" rowSpan={2} className="strike">Strike</th>
          <th scope="colgroup" colSpan={columns.length} className="side put">Puts</th></tr>
        <tr>{callColumns.map((column) => <th key={`c-${column.key}`} scope="col" title={`Call ${column.title}`} className="call">
          <span aria-hidden="true">{column.label}</span><span className="sr-only">Call {column.title}</span></th>)}
          {columns.map((column) => <th key={`p-${column.key}`} scope="col" title={`Put ${column.title}`} className="put">
            <span aria-hidden="true">{column.label}</span><span className="sr-only">Put {column.title}</span></th>)}</tr>
      </thead>
      <tbody>{rows.map((row) => {
        const isNearest = row.strike === nearest;
        return <tr key={row.strike} ref={isNearest ? nearestRef : undefined} className={isNearest ? "nearest" : undefined}>
          {cells(row.call, "call", callColumns, underlying != null && row.strike < underlying)}
          <th scope="row" className="strike">{row.strike}{isNearest ? <><span aria-hidden="true" className="screener-options-marker">◆</span><span className="sr-only"> nearest strike to underlying</span></> : null}</th>
          {cells(row.put, "put", columns, underlying != null && row.strike > underlying)}
        </tr>;
      })}</tbody>
    </table>
  </div>;
}

function Footer({ data }: { data: OptionsPayload }) {
  const completeness = data.completeness;
  const clock = data.clock;
  // Source and completeness stay visible; the legend folds away so the chain keeps its height.
  return <div className="screener-options-footer">
    <p className="screener-panel-note">
      {data.provider?.label ?? "Provider"} options export · snapshot, not streaming · fetched {etTime(clock?.fetched_at)}
      {clock?.latest_contract_trade_at ? ` · latest contract trade ${etTime(clock.latest_contract_trade_at)}` : ""}
      {completeness ? ` · ${completeness.usable.toLocaleString("en-US")} of ${completeness.provider_rows.toLocaleString("en-US")} provider rows usable${completeness.expired_excluded ? ` (${completeness.expired_excluded.toLocaleString("en-US")} expired excluded${completeness.dropped ? `, ${completeness.dropped} malformed dropped` : ""})` : completeness.dropped ? ` (${completeness.dropped} malformed dropped)` : ""}` : ""}
    </p>
    <details className="screener-options-legend"><summary>Legend</summary>
      <p className="screener-panel-note">Volume and open interest are observed counts; volume may be opening or closing trades. ▲ volume above open interest · bold: top 10% volume in this expiry · shaded: in the money · italic: spread above {WIDE_SPREAD_PCT}% of mid · ◆ nearest strike to the underlying.</p>
    </details>
  </div>;
}

export default function OptionsPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  // The expiry choice belongs to one instrument; a new selection starts at its nearest expiry.
  const [choice, setChoice] = useState<{ id: string; expiration: string } | null>(null);
  const [detail, setDetail] = useState(false);
  const expiration = choice && choice.id === settledId ? choice.expiration : null;
  const snapshotId = row && row.instrument.instrument_id === settledId ? row.snapshot_id ?? null : null;
  const query = useQuery({
    queryKey: ["screener-options", universe, settledId, "chain", expiration, snapshotId],
    queryFn: ({ signal }) => fetchScreenerOptions(settledId!, { universe, view: "chain", expiration, snapshotId, signal }),
    enabled: Boolean(settledId) && visible, staleTime: 30_000, refetchInterval: visible ? OPTIONS_POLL_MS : false, retry: 1,
    // Only an expiry switch on the same instrument may keep the previous chain on screen.
    placeholderData: (previous) => previous && previous.instrument_id === settledId ? previous : undefined,
  });
  const data = query.data && query.data.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  const now = useNow(5_000, visible && Boolean(data?.clock));
  const age = data ? snapshotAge(data, query.dataUpdatedAt, now) : null;
  const gate = selectionGate("options", row, settledId);
  const status = data ? <>
    <span className={`screener-panel-state state-${OPTIONS_BADGE[data.state].toLowerCase()}`}>{OPTIONS_STATE_LABELS[data.state]}</span>
    {age != null ? <span title={`Fetched ${etTime(data.clock?.fetched_at)}`}>Updated {ago(age)} ago</span> : null}</> : null;
  const chain = data && hasChain(data.state) && data.summary ? data : undefined;
  return <PanelFrame id="options" detail={data?.provider ? `${data.provider.label} · snapshot` : null} clock={status}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">Current option chain unavailable.<ErrorDetail error={query.error} /> <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row!.symbol} options…</PanelMessage>
      : !chain ? <PanelMessage tone={data.state === "NO_CHAIN" ? "muted" : "warn"}>{stateMessage(data)}</PanelMessage>
      : <>
        <div className="screener-panel-controls screener-options-bar">
          <label className="screener-options-expiry">Expiry{" "}
            <select value={chain.selected_expiration ?? ""} onChange={(event) => setChoice({ id: chain.instrument_id, expiration: event.target.value })}>
              {chain.expirations.map((item) => <option key={item.expiration} value={item.expiration}>
                {expiry(item.expiration)} · {item.dte}d · {item.strikes} strikes</option>)}
            </select></label>
          <button type="button" className="screener-options-toggle" aria-pressed={detail} onClick={() => setDetail((value) => !value)}>More columns</button>
          {query.isFetching && query.isPlaceholderData ? <span className="screener-muted" role="status">Loading {expiry(expiration)}…</span> : null}
          <span className="screener-panel-price" title={chain.underlying?.as_of ? `Underlying clock ${etTime(chain.underlying.as_of)}` : undefined}>
            {chain.underlying ? `Underlying ${price(chain.underlying.price)} · ${chain.underlying.state === "LIVE" ? "L1 live" : chain.underlying.state === "DELAYED" ? "delayed" : "snapshot"} · ${chain.underlying.source === "FINVIZ_ELITE" ? "Finviz" : chain.underlying.source}` : "Underlying price unavailable"}</span>
        </div>
        {chain.state !== "CURRENT_SNAPSHOT" ? <p className={`screener-panel-note ${chain.state === "STALE" ? "screener-warn" : ""}`} role="status">{stateMessage(chain)}</p> : null}
        <Summary data={chain} />
        <ExpiryLine data={chain} />
        <Chain data={chain} detail={detail} />
        <Footer data={chain} />
      </>)}
  </PanelFrame>;
}
