import { lazy, memo, Suspense, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchScreenerPreview, type ScreenerFilter, type ScreenerPreview, type ScreenerQuote, type ScreenerRow, type ScreenerUniverse } from "../../api/screener";
import { BondQuickPreview } from "./bonds/BondQuickPreview";
import { CryptoQuickPreview } from "./crypto/CryptoQuickPreview";
import { PreviewOptions } from "./options/PreviewOptions";
import { PreviewSqueeze } from "./squeeze/PreviewSqueeze";
import { classifyZones, type ClassifiedZone } from "./srClassify";

const PreviewChart = lazy(() => import("./PreviewChart"));

const TIMEFRAMES = ["1m", "5m", "15m"] as const;
const SELECTION_SETTLE_MS = 180;
const SCOPES = [{ id: "EXTENDED", label: "Extended" }, { id: "RTH", label: "RTH" }] as const;
const TABS = [{ id: "why", label: "Why" }, { id: "key", label: "Key Data" }, { id: "futures", label: "Futures" }, { id: "options", label: "Options" }, { id: "squeeze", label: "Squeeze" }] as const;
type Tab = (typeof TABS)[number]["id"];
const etTime = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const etShort = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });
const REASONS: Record<string, string> = {
  NOT_ENTITLED: "No futures quote entitlement", CONTRACT_EXPIRED: "Provider main contract has expired",
  PROVIDER_UNAVAILABLE: "Provider unavailable", MAIN_CONTRACT_UNKNOWN: "Current contract unresolved",
  CONTRACT_REFERENCE_UNAVAILABLE: "Contract reference unavailable", NO_CURRENT_FEED: "No current feed",
  OPEND_UNAVAILABLE: "OpenD is not reachable", BAR_SOURCE_UNAVAILABLE: "Current bars unavailable",
  STALE_BAR_SOURCE: "Bar source is stale", INSUFFICIENT_BARS: "Not enough completed bars",
  MALFORMED_BARS: "Bar data failed validation", INVALID_PRICE: "No valid current price",
  MARKET_DATA_UNAVAILABLE: "Market data unavailable", MOOMOO_SUBSCRIPTION_BUSY: "Chart data slots busy; retrying shortly",
  MOOMOO_QUOTE_NOT_ENTITLED: "No quote entitlement for bars", MOOMOO_SDK_MISSING: "Moomoo SDK missing",
  MOOMOO_AUTH_FAILURE: "Moomoo quote login required", MOOMOO_PROTOCOL_ERROR: "Provider request failed",
};
const reasonText = (code: string | null | undefined) => (code && (REASONS[code] ?? code.replace(/_/g, " ").toLowerCase())) || "Unavailable";
const CLASS_LABELS: Record<string, string> = { OBSERVED: "Observed", DERIVED: "Derived", UNAVAILABLE: "Unavailable",
  INSUFFICIENT_EVIDENCE: "Insufficient evidence", AI_SYNTHESIS: "AI synthesis" };
const money = (value: number) => value >= 1 ? value.toFixed(2) : value.toFixed(4);
const pct = (value: number, signed = false) => `${signed && value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const time = (iso: string | null | undefined, short = false) => iso ? `${(short ? etShort : etTime).format(new Date(iso))} ET` : "—";
function keyValue(unit: string, field: string, value: number | null) {
  if (value == null) return "—";
  if (unit === "boolean") return value ? "Yes" : "No";
  if (unit === "days") return `${Math.round(value)} days`;
  if (unit === "contracts") return compact.format(value);
  if (unit === "points") return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  if (unit === "USD") return field === "market_cap" ? `$${compact.format(value)}` : `$${money(value)}`;
  if (unit === "percent") return pct(value, field === "change_pct");
  if (unit === "shares") return compact.format(value);
  if (unit === "ratio") return `${value.toFixed(2)}×`;
  return value.toFixed(field === "rsi_14" ? 1 : 2);
}
function barStateLabel(state: string) {
  return ({ CURRENT: "Current", SESSION_CLOSED: "Session closed · last session", STALE: "Stale", UNAVAILABLE: "Unavailable" } as Record<string, string>)[state] ?? state;
}

export type QuickPreviewProps = {
  row: ScreenerRow | null;
  universe: ScreenerUniverse;
  quote: ScreenerQuote | undefined;
  filters: ScreenerFilter[];
  screenLabel: string | null;
  overlay: boolean;
  width: number;
  paneRef?: React.Ref<HTMLElement>;
  onClose: () => void;
  onOpen: (row: ScreenerRow) => void;
  /** S7: the universe offers selected-underlying options context. */
  optionsSupported?: boolean;
  onOpenOptions?: () => void;
  squeezeSupported?: boolean;
  onOpenSqueeze?: () => void;
  /** S9: the universe offers the Rates & Curve specialist panel. */
  ratesSupported?: boolean;
  onOpenRates?: () => void;
};

function SrBar({ price, support, resistance, testing }: { price: number | null; support: ClassifiedZone | null; resistance: ClassifiedZone | null; testing: ClassifiedZone | null }) {
  if (price == null || (!support && !resistance && !testing)) return null;
  const low = Math.min(support?.lower ?? price * 0.98, testing?.lower ?? price, price);
  const high = Math.max(resistance?.upper ?? price * 1.02, testing?.upper ?? price, price);
  const span = high - low || 1;
  const at = (value: number) => `${Math.min(100, Math.max(0, (value - low) / span * 100))}%`;
  const band = (zone: ClassifiedZone, kind: string) => <span className={`screener-sr-zone ${kind}`}
    style={{ left: at(zone.lower), width: `calc(${at(zone.upper)} - ${at(zone.lower)} + 3px)` }} />;
  return <div className="screener-sr-track" aria-hidden="true">
    <span className="screener-sr-rail" />
    {support && band(support, "support")}{resistance && band(resistance, "resistance")}{testing && band(testing, "testing")}
    <span className="screener-sr-price" style={{ left: at(price) }} />
  </div>;
}

function SrSide({ kind, zone }: { kind: "support" | "resistance"; zone: ClassifiedZone | null }) {
  const title = kind === "support" ? "Support" : "Resistance";
  return <div className={`screener-sr-side ${kind}`}>
    <span className="screener-sr-label">{title}</span>
    {zone ? <><strong>${money(zone.lower)}–{money(zone.upper)}</strong>
      <span>{zone.distance_pct.toFixed(2)}% {kind === "support" ? "below" : "above"}</span>
      <span className="screener-muted">Strength {zone.strength}</span></>
      : <span className="screener-muted">No {kind} zone</span>}
  </div>;
}

function Levels({ preview, price, priceSource }: { preview: ScreenerPreview; price: number | null; priceSource: string }) {
  const levels = preview.levels;
  const scope = levels.session_scope === "RTH" ? "RTH" : "Extended";
  const classified = useMemo(() => classifyZones(levels.zones, price, levels.min_strength), [levels.zones, price, levels.min_strength]);
  const header = <div className="screener-preview-subhead"><span>Auto S/R · {levels.timeframe} · {scope}</span>
    <span className="screener-muted" title={`${levels.method}. ${levels.strength_semantics}`}>{levels.method}</span></div>;
  if (levels.state === "UNAVAILABLE") {
    return <section className="screener-sr" aria-label="Automatic support and resistance">{header}
      <p className="screener-preview-note">Levels unavailable · {reasonText(levels.reason)}</p></section>;
  }
  const summary = [classified.support ? `Support zone ${money(classified.support.lower)} to ${money(classified.support.upper)}, ${classified.support.distance_pct.toFixed(2)}% below` : "No support zone",
    classified.testing ? `price is inside zone ${money(classified.testing.lower)} to ${money(classified.testing.upper)}` : null,
    classified.resistance ? `resistance zone ${money(classified.resistance.lower)} to ${money(classified.resistance.upper)}, ${classified.resistance.distance_pct.toFixed(2)}% above` : "no resistance zone"]
    .filter(Boolean).join("; ");
  return <section className="screener-sr" aria-label="Automatic support and resistance">{header}
    <SrBar price={price} {...classified} />
    <div className="screener-sr-sides">
      <SrSide kind="support" zone={classified.support} />
      <div className="screener-sr-side current"><span className="screener-sr-label">{priceSource.startsWith("Last bar close") ? "Last bar close" : "Current"}</span>
        <strong>{price == null ? "—" : `$${money(price)}`}</strong><span className="screener-muted">{priceSource}</span>
        {classified.testing && <span className="screener-sr-testing">Testing zone</span>}</div>
      <SrSide kind="resistance" zone={classified.resistance} />
    </div>
    <p className="sr-only">{summary}.</p>
    <p className="screener-preview-meta">Levels calculated {time(levels.calculated_at)} · bars to {time(levels.input_latest_bar_end, true)} · {levels.input_bar_count} bars</p>
  </section>;
}

function WhyPanel({ preview, screenLabel, universe }: { preview: ScreenerPreview; screenLabel: string | null; universe: ScreenerUniverse }) {
  const matched = preview.why.matched;
  const groups = ["OBSERVED", "DERIVED", "UNAVAILABLE", "INSUFFICIENT_EVIDENCE"].map((name) =>
    [name, preview.why.moving.items.filter((item) => item.class === name)] as const).filter(([, items]) => items.length);
  return <div className="screener-why">
    <h3>Why it matched{screenLabel ? <span className="screener-muted"> · {screenLabel}</span> : null}</h3>
    {matched.state === "NO_ACTIVE_FILTERS" ? <p className="screener-preview-note">No filters are active; every instrument in the universe is listed.</p> :
      <ul className="screener-why-list">{matched.items.map((item) => <li key={item.filter_id} className={item.passed ? "pass" : "fail"}>
        <span aria-hidden="true">{item.passed ? "✓" : "✕"}</span><span className="sr-only">{item.passed ? "Passes: " : "Does not pass: "}</span>{item.text}</li>)}</ul>}
    <h3>Why it may be moving</h3>
    {groups.map(([name, items]) => <div key={name} className={`screener-evidence ${name.toLowerCase()}`}>
      <h4>{CLASS_LABELS[name]}</h4>
      <ul>{items.map((item, index) => <li key={`${item.kind}-${index}`} title={`${item.source}${item.as_of ? ` · ${time(item.as_of, true)}` : ""}`}>{item.text}</li>)}</ul>
    </div>)}
    <p className="screener-preview-meta">Observed and derived items are context, not causal attribution.{universe === "US_EQUITIES" ? ` Headlines since ${time(preview.why.moving.headline_window_start, true)}.` : ""}</p>
  </div>;
}

function KeyData({ preview, quote }: { preview: ScreenerPreview; quote: ScreenerQuote | undefined }) {
  return <dl className="screener-key-data">{preview.key_data.map((item) => {
    const live = quote?.state === "LIVE" ? quote.fields[item.field] : undefined;
    const field = live && live.value != null ? { value: live.value, source: live.source, state: live.state } : item;
    return <div key={item.field} title={`${field.source ?? "No source"} · ${field.state}${"as_of" in field && field.as_of ? ` · ${time(field.as_of, true)}` : ""}`}>
      <dt>{item.label}</dt><dd className={field.state === "LIVE" ? "live" : undefined}>{keyValue(item.unit, item.field, field.value)}</dd></div>;
  })}
    {preview.instrument.asset_class === "EQUITY" && <><div className="wide"><dt>Sector</dt><dd>{preview.instrument.sector ?? "—"}</dd></div>
    <div className="wide"><dt>Industry</dt><dd>{preview.instrument.industry ?? "—"}</dd></div></>}
    {preview.instrument.asset_class === "FUTURE" && <><div className="wide"><dt>Root</dt><dd>{preview.instrument.root ?? "—"}</dd></div>
    <div className="wide"><dt>Expiry</dt><dd>{preview.instrument.expiry ?? "—"}</dd></div></>}
  </dl>;
}

function Futures({ preview }: { preview: ScreenerPreview }) {
  return <div className="screener-futures">
    <ul>{preview.futures.items.map((item) => <li key={item.root}>
      <div className="screener-futures-head"><strong>{item.contract.state === "CURRENT" ? item.contract.contract_id : item.root}</strong>
        <span className="screener-muted">{item.name}</span></div>
      <p>{item.relationship_reason}</p>
      {item.quote ? <div className="screener-futures-quote"><span>{item.quote.price.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
        {item.quote.change_pct != null && <span className={item.quote.change_pct >= 0 ? "screener-positive" : "screener-negative"}>{pct(item.quote.change_pct, true)}</span>}
        <span className={`screener-state ${item.quote.state.toLowerCase()}`}>{item.quote.state === "LIVE" ? "Live" : "Stale"} · {item.quote.price_basis === "MID" ? "mid · " : ""}{item.quote.provider}{item.quote.age_ms != null ? ` · ${item.quote.age_ms < 1000 ? `${item.quote.age_ms}ms` : `${Math.round(item.quote.age_ms / 1000)}s`}` : ""}</span></div>
        : <div className="screener-futures-quote"><span className="screener-state unavailable">Price unavailable · {reasonText(item.unavailable_reason)}</span></div>}
      {item.contract.state === "CURRENT" && <span className="screener-preview-meta">Last trade {item.contract.last_trade_date}</span>}
    </li>)}</ul>
    <p className="screener-preview-meta">{preview.futures.causal_note}</p>
  </div>;
}

function QuickPreviewInner({ row, universe, quote, filters, screenLabel, overlay, width, paneRef, onClose, onOpen, optionsSupported = false, onOpenOptions, squeezeSupported = false, onOpenSqueeze }: QuickPreviewProps) {
  const [tab, setTab] = useState<Tab>("why");
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>("5m");
  const [scope, setScope] = useState<"EXTENDED" | "RTH">("EXTENDED");
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const id = row?.instrument.instrument_id ?? null;
  // Arrowing past rows should not open a provider bar subscription for each one.
  const [requestId, setRequestId] = useState(id);
  useEffect(() => {
    const timer = window.setTimeout(() => setRequestId(id), SELECTION_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [id]);
  const filterKey = JSON.stringify(filters);
  // Snapshot-evaluated rows explain the values they were filtered and ordered by.
  const snapshotId = row?.snapshot_id ?? null;
  const preview = useQuery({
    queryKey: ["screener-preview", universe, requestId, timeframe, scope, filterKey, snapshotId],
    queryFn: ({ signal }) => fetchScreenerPreview(requestId!, timeframe, scope, filters, signal, universe, snapshotId),
    enabled: Boolean(requestId) && requestId === id, staleTime: 10_000, retry: 1,
    refetchInterval: (query) => query.state.data?.bars.provider_reason === "MOOMOO_SUBSCRIPTION_BUSY" ? 5_000 : 15_000,
    // Keep the previous payload only while the same instrument changes timeframe/scope.
    placeholderData: (previous) => previous && previous.instrument.instrument_id === id &&
      (previous.universe ?? "US_EQUITIES") === universe ? previous : undefined,
  });
  const data = preview.data && preview.data.instrument.instrument_id === id &&
    (preview.data.universe ?? "US_EQUITIES") === universe ? preview.data : undefined;
  const livePrice = quote?.state === "LIVE" ? quote.fields.price?.value ?? null : null;
  const delayedPrice = quote?.state === "DELAYED" ? quote.fields.price?.value ?? null : null;
  // Quote clock (header) and bar clock (S/R marker) stay separate: the header
  // never shows a bar close as if it were the snapshot price.
  const headerPrice = livePrice ?? delayedPrice ?? row?.fields.price?.value ?? null;
  const price = livePrice ?? data?.levels.price?.value ?? row?.fields.price?.value ?? null;
  const priceSource = livePrice != null ? `L1 live${quote?.age_ms != null ? ` · ${quote.age_ms}ms` : ""}` : data?.levels.price?.source === "LAST_BAR_CLOSE" ? `Last bar close · ${time(data.levels.price.as_of, true)}` : "Snapshot";
  const classified = useMemo(() => data ? classifyZones(data.levels.zones, price, data.levels.min_strength) : null, [data, price]);
  const change = quote?.state === "LIVE" || quote?.state === "DELAYED" ? quote.fields.change_pct?.value ?? row?.fields.change_pct?.value ?? null : row?.fields.change_pct?.value ?? null;
  const tabs = TABS.filter((item) => (item.id !== "futures" || universe === "US_EQUITIES") && (item.id !== "options" || optionsSupported) && (item.id !== "squeeze" || squeezeSupported));
  const onTabKey = (event: KeyboardEvent) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = tabs.findIndex((item) => item.id === tab);
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    setTab(tabs[next].id); tabRefs.current[tabs[next].id]?.focus();
  };
  useEffect(() => {
    if ((universe !== "US_EQUITIES" && tab === "futures") || (!optionsSupported && tab === "options") || (!squeezeSupported && tab === "squeeze")) setTab("why");
  }, [universe, tab, optionsSupported, squeezeSupported]);
  const bars = data?.bars;
  const chartLabel = bars && bars.bars.length ? `${data.instrument.symbol} ${bars.timeframe} candles, ${bars.bar_count} completed bars to ${time(bars.latest_complete_bar_end, true)}, last close ${money(bars.bars[bars.bars.length - 1].close)}` : "";
  return <aside className={`screener-preview${overlay ? " overlay" : ""}`} aria-label="Quick preview" ref={paneRef as React.Ref<HTMLElement>} tabIndex={-1}
    style={overlay ? undefined : { width }}
    onKeyDown={(event) => { if (event.key === "Escape" && !(event.target instanceof HTMLInputElement)) { event.stopPropagation(); onClose(); } }}>
    <header className="screener-preview-header">
      <span className="screener-preview-kicker">Quick Preview</span>
      <button type="button" className="screener-preview-close" onClick={onClose} aria-label="Close quick preview">×</button>
    </header>
    {!row ? <p className="screener-preview-empty">Select a row to preview it. Arrow keys move the selection; Enter opens the instrument.</p> : <>
      <div className="screener-preview-identity">
        <div><h2>{row.symbol}</h2><span className="screener-muted">{row.company}</span></div>
        <div className="screener-preview-quote">
          <strong>{headerPrice == null ? "—" : `${universe === "FUTURES" ? "" : "$"}${money(headerPrice)}`}</strong>
          {change != null && <span className={change > 0 ? "screener-positive" : change < 0 ? "screener-negative" : ""} title={universe === "US_EQUITIES" ? "Finviz snapshot change" : "Provider quote change"}>{pct(change, true)}</span>}
          <span className={`screener-state ${livePrice != null ? "live" : delayedPrice != null ? "delayed" : "snapshot"}`}>{livePrice != null ? "L1 live" : delayedPrice != null ? "Delayed" : quote?.state === "STALE" ? "L1 stale" : universe === "FUTURES" ? "Quote unavailable" : universe === "US_ETFS" && data?.market_session === "CLOSED" ? "Session closed · no current quote" : universe === "US_ETFS" ? "Quote awaiting provider" : "Snapshot"}</span>
        </div>
      </div>
      {universe === "FUTURES" && <p className="screener-preview-meta">Root {row.root ?? "—"} · {row.exchange ?? "Exchange unavailable"} · expires {row.expiry ?? "unknown"}</p>}
      <div className="screener-preview-controls">
        {universe !== "FUTURES" && <><div role="group" aria-label="Chart timeframe" className="screener-segment">{TIMEFRAMES.map((item) =>
          <button key={item} type="button" aria-pressed={timeframe === item} onClick={() => setTimeframe(item)}>{item}</button>)}</div>
        <div role="group" aria-label="Session scope" className="screener-segment">{SCOPES.map((item) =>
          <button key={item.id} type="button" aria-pressed={scope === item.id} onClick={() => setScope(item.id)}>{item.label}</button>)}</div></>}
      </div>
      {preview.isError && !data ? <p className="screener-preview-note" role="alert">Preview unavailable for {row.symbol}. <button type="button" onClick={() => void preview.refetch()}>Retry</button></p> :
        !data ? <p className="screener-preview-note" aria-live="polite">Loading {row.symbol}…</p> : <>
          <section className="screener-preview-chart-wrap" aria-label="Current chart">
            {bars && bars.bars.length ? <Suspense fallback={<div className="screener-preview-chart" />}>
              <PreviewChart bars={bars.bars} forming={bars.forming} support={classified?.support ?? null} resistance={classified?.resistance ?? null} label={chartLabel} />
            </Suspense> : <div className="screener-preview-chart unavailable" role="status">Chart unavailable · {reasonText(bars?.provider_reason ?? bars?.reason)}</div>}
            <p className="screener-preview-meta">{bars?.timeframe} · {bars?.session_scope === "RTH" ? "RTH" : bars?.session_scope === "PROVIDER_SPECIFIC" ? "Futures session" : "Extended"} · {barStateLabel(bars?.state ?? "UNAVAILABLE")}{universe !== "FUTURES" ? " · Moomoo OpenD" : ""}{bars?.latest_complete_bar_end ? ` · last bar ${time(bars.latest_complete_bar_end, true)}` : ""}</p>
          </section>
          <Levels preview={data} price={price} priceSource={priceSource} />
          <div className="screener-preview-tabs" role="tablist" aria-label="Preview details" onKeyDown={onTabKey}>
            {tabs.map((item) => <button key={item.id} ref={(element) => { tabRefs.current[item.id] = element; }} type="button" role="tab"
              id={`screener-preview-tab-${item.id}`} aria-controls={`screener-preview-panel-${item.id}`} aria-selected={tab === item.id}
              tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)}>{item.label}</button>)}
          </div>
          <div className="screener-preview-panel" role="tabpanel" id={`screener-preview-panel-${tab}`} aria-labelledby={`screener-preview-tab-${tab}`} tabIndex={0}>
            {tab === "why" ? <WhyPanel preview={data} screenLabel={screenLabel} universe={universe} /> : tab === "key" ? <KeyData preview={data} quote={quote} />
              : tab === "options" ? <PreviewOptions row={row} universe={universe} onOpenPanel={() => onOpenOptions?.()} />
                : tab === "squeeze" ? <PreviewSqueeze row={row} settledId={requestId} filters={filters} onOpenPanel={() => onOpenSqueeze?.()} /> : <Futures preview={data} />}
          </div>
        </>}
      <footer className="screener-preview-footer"><button type="button" className="screener-control screener-primary" onClick={() => onOpen(row)}>Open Instrument</button></footer>
    </>}
  </aside>;
}

/** Bonds get a fixed-income preview (terms, auction, curve reference); no equity concepts render for them. */
function QuickPreviewSwitch(props: QuickPreviewProps) {
  if (props.universe === "CRYPTO") {
    return <CryptoQuickPreview row={props.row} filters={props.filters} screenLabel={props.screenLabel} overlay={props.overlay}
      width={props.width} paneRef={props.paneRef} onClose={props.onClose} />;
  }
  if (props.universe === "BONDS") {
    return <BondQuickPreview row={props.row} filters={props.filters} screenLabel={props.screenLabel} overlay={props.overlay}
      width={props.width} paneRef={props.paneRef} onClose={props.onClose} ratesSupported={props.ratesSupported ?? false}
      onOpenRates={props.onOpenRates} />;
  }
  return <QuickPreviewInner {...props} />;
}

export const QuickPreview = memo(QuickPreviewSwitch);
