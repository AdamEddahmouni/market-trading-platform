import { useEffect, useMemo, useState, type Ref } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ScreenerFilter, ScreenerRow } from "../../../api/screener";
import { fetchCryptoPreview } from "../../../api/screenerCrypto";
import PreviewChart from "../PreviewChart";
import { pricePrecision } from "../panels/shared";
import { classifyZones } from "../srClassify";
import { PreviewNewsSection } from "../news/PreviewNewsSection";
import "./crypto.css";
import { LOCAL_SUFFIX, LOCAL_ZONE } from "../localZone";

type Props = { row: ScreenerRow | null; filters: ScreenerFilter[]; screenLabel: string | null;
  overlay: boolean; width: number; paneRef?: Ref<HTMLElement>; onClose: () => void;
  newsSupported?: boolean; onOpenNews?: () => void };
type Timeframe = "1m" | "5m" | "15m";
const frames: Timeframe[] = ["1m", "5m", "15m"];
const stampFormat = new Intl.DateTimeFormat("en-US", { timeZone: LOCAL_ZONE, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const stamp = (value: string | null | undefined) => value ? `${stampFormat.format(new Date(value))} ${LOCAL_SUFFIX}` : "unavailable";
const number = (value: number | null | undefined, digits = 2) => value == null ? "—" : value.toLocaleString("en-US", { maximumFractionDigits: digits });

export function CryptoQuickPreview({ row, filters, screenLabel, overlay, width, paneRef, onClose, newsSupported = false, onOpenNews }: Props) {
  const id = row?.instrument.instrument_id ?? null;
  const [settledId, setSettledId] = useState(id);
  const [timeframe, setTimeframe] = useState<Timeframe>("1m");
  useEffect(() => { const timer = window.setTimeout(() => setSettledId(id), 180); return () => window.clearTimeout(timer); }, [id]);
  const filterKey = JSON.stringify(filters);
  const preview = useQuery({ queryKey: ["screener-crypto-preview", settledId, timeframe, filterKey],
    queryFn: ({ signal }) => fetchCryptoPreview(settledId!, timeframe, filters, signal),
    enabled: Boolean(settledId) && settledId === id, staleTime: 15_000, refetchInterval: 30_000, retry: 1 });
  const data = preview.data?.instrument.instrument_id === id ? preview.data : undefined;
  const current = (field: string) => data?.quote.fields[field]?.value ?? data?.fields[field]?.value ?? row?.fields[field]?.value ?? null;
  const last = current("price");
  const precision = pricePrecision(row, last ?? 1);
  const zones = useMemo(() => data ? classifyZones(data.levels.zones, data.levels.price?.value ?? null, data.levels.min_strength) : null, [data]);
  return <aside className={`screener-preview crypto-preview${overlay ? " overlay" : ""}`} aria-label="Quick preview" ref={paneRef}
    tabIndex={-1} style={overlay ? undefined : { width }} onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
    <header className="screener-preview-header"><span className="screener-preview-kicker">Quick Preview · Crypto Spot</span>
      <button type="button" className="screener-preview-close" onClick={onClose} aria-label="Close quick preview">×</button></header>
    {!row ? <p className="screener-preview-empty">Select a spot pair to inspect its venue market.</p> : <>
      <div className="screener-preview-identity"><h2>{row.symbol}</h2>
        <p className="crypto-preview-subtitle">{row.base_asset}/{row.quote_asset} · {row.venue} · SPOT · 24/7</p>{screenLabel && <small>{screenLabel}</small>}</div>
      {preview.isPending || !data ? <p role="status" className="screener-preview-empty">{preview.isError ? "Crypto preview unavailable" : "Loading selected pair…"}</p> : <>
        <section className="crypto-preview-section" aria-label="Current pair market"><h3>Market · {row.quote_asset} per {row.base_asset}</h3>
          <dl className="screener-key-data"><div><dt>Last</dt><dd>{number(current("price"), precision)} {row.quote_asset}</dd></div>
            <div><dt>UTC day change</dt><dd className={(current("change_pct") ?? 0) > 0 ? "positive" : (current("change_pct") ?? 0) < 0 ? "negative" : undefined}>
              {current("change_pct") == null ? "—" : `${current("change_pct")! > 0 ? "+" : ""}${number(current("change_pct"))}%`}</dd></div>
            <div className="wide"><dt>24h base volume</dt><dd>{number(current("base_volume"), 6)} {row.base_asset}</dd></div>
            <div className="wide"><dt>24h quote volume</dt><dd>{number(current("quote_volume"))} {row.quote_asset}</dd></div>
            <div className="wide"><dt>Bid / ask</dt><dd>{number(current("bid"), precision)} / {number(current("ask"), precision)}</dd></div>
            <div className="wide"><dt>Spread</dt><dd>{current("spread_pct") == null ? "—" : `${number(current("spread_pct"), 4)}%`}</dd></div>
            <div className="wide"><dt>24h high / low</dt><dd>{number(current("high_24h"), precision)} / {number(current("low_24h"), precision)}</dd></div></dl>
          <p className="screener-preview-meta">Kraken public spot · REST quote {data.quote.state.toLowerCase()} · universe snapshot {stamp(data.snapshot_as_of)}</p>
          <p className="screener-preview-meta">Quote values remain in {row.quote_asset}. UTC day change uses the midnight UTC open.</p>
        </section>
        <section className="crypto-preview-section" aria-label="Spot chart"><h3>24/7 chart</h3><div role="group" aria-label="Chart timeframe" className="screener-segment">
          {frames.map((item) => <button key={item} type="button" aria-pressed={timeframe === item} onClick={() => setTimeframe(item)}>{item}</button>)}</div>
          {data.bars.state === "CURRENT" && data.bars.bars.length > 0
            ? <PreviewChart bars={data.bars.bars} forming={data.bars.forming} support={zones?.support ?? null} resistance={zones?.resistance ?? null}
                label={`${row.symbol} · ${timeframe} · Kraken spot · ${LOCAL_SUFFIX}`} timeZone={LOCAL_ZONE} precision={precision} />
            : <p role="status">Bars unavailable · {data.bars.reason ?? data.bars.state}</p>}
          <p className="screener-preview-meta">{data.bars.bar_count} complete bars · last close {stamp(data.bars.latest_complete_bar_end)}</p>
        </section>
        <section className="crypto-preview-section" aria-label="Pair structure"><h3>Structure</h3>
          <dl className="screener-key-data"><div><dt>Status</dt><dd>{data.instrument.status}</dd></div>
            <div><dt>Price increment</dt><dd>{data.instrument.price_increment ?? "unavailable"} {row.quote_asset}</dd></div>
            <div><dt>Base increment</dt><dd>{data.instrument.base_increment ?? "unavailable"} {row.base_asset}</dd></div>
            <div><dt>Quote increment</dt><dd>{data.instrument.quote_increment ?? "unavailable"} {row.quote_asset}</dd></div>
            <div className="wide"><dt>Minimum order</dt><dd>{data.instrument.min_order_size ?? "unavailable"} {row.base_asset}</dd></div></dl></section>
        <section className="crypto-preview-section" aria-label="Source and clocks"><h3>Source · clock</h3>
          <p className="screener-preview-meta">Provider Kraken public spot REST · catalog {stamp(data.instrument.catalog_as_of)}</p>
          <p className="screener-preview-meta">Quote received {stamp(data.quote.fields.price?.as_of)} · the venue ticker carries no event timestamp</p>
          <p className="screener-preview-meta">Bars received {stamp(data.bars.received_at)}</p></section>
        <section className="crypto-preview-section" aria-label="Why it matched"><h3>Why it matched</h3>{data.why.matched.items.length
          ? <ul>{data.why.matched.items.map((item) => <li key={item.filter_id}>{item.text}</li>)}</ul> : <p>No active filters.</p>}</section>
      </>}
      {newsSupported && <PreviewNewsSection row={row} settledId={settledId} universe="CRYPTO" onOpenNews={onOpenNews} />}
    </>}
  </aside>;
}
