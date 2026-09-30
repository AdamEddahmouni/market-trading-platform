import { Component, createContext, useContext, useEffect, useState, type ErrorInfo, type ReactNode } from "react";
import type { IDockviewPanelProps } from "dockview-react";
import type { PanelId, ScreenerFilter, ScreenerQuote, ScreenerRow, ScreenerUniverse } from "../../../api/screener";
import type { PanelDemand, PanelState } from "../../../api/screenerPanels";
import { PANEL_TITLES } from "./registry";

/** One canonical selection drives every panel; panels never pick their own ticker. */
export type SpecialistSelection = {
  row: ScreenerRow | null;
  universe: ScreenerUniverse;
  supportedPanels: ReadonlySet<PanelId>;
  /** The selection after the settle delay; requests are only made for it. */
  settledId: string | null;
  quote: ScreenerQuote | undefined;
  filters: ScreenerFilter[];
  demand: PanelDemand | null;
  actions: PanelActions;
};
export type PanelActions = {
  close: (id: PanelId) => void;
  move: (id: PanelId, direction: "left" | "right" | "split") => void;
  resize: (id: PanelId, delta: number) => void;
  /** Open (or focus) another panel, e.g. a hand-off from one lens to the panel that owns its evidence. */
  open?: (id: PanelId) => void;
};
const noop = () => undefined;
export const SpecialistContext = createContext<SpecialistSelection>({
  row: null, universe: "US_EQUITIES", supportedPanels: new Set<PanelId>(["order_flow", "cvd", "level2", "charts", "futures", "options"]),
  settledId: null, quote: undefined, filters: [], demand: null, actions: { close: noop, move: noop, resize: noop },
});
export const useSelection = () => useContext(SpecialistContext);

/** True while the panel's tab is showing; hidden tabs stop polling but keep their subscription. */
export function usePanelVisible(api: IDockviewPanelProps["api"]) {
  const [visible, setVisible] = useState(api.isVisible);
  useEffect(() => {
    setVisible(api.isVisible);
    const listener = api.onDidVisibilityChange((event) => setVisible(event.isVisible));
    return () => listener.dispose();
  }, [api]);
  return visible;
}

const etTime = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const etShort = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });
const compactFormat = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
export const etClock = (iso: string | null | undefined) => iso ? `${etTime.format(new Date(iso))} ET` : "—";
export const etDay = (iso: string | null | undefined) => iso ? `${etShort.format(new Date(iso))} ET` : "—";
export const compact = (value: number) => compactFormat.format(value);
export const signedCompact = (value: number) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${compactFormat.format(Math.abs(value))}`;
export const money = (value: number) => value >= 1 ? value.toFixed(2) : value.toFixed(4);
const utcTime = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const utcShort = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });
export const utcClock = (iso: string | null | undefined) => iso ? `${utcTime.format(new Date(iso))} UTC` : "—";
export const utcDay = (iso: string | null | undefined) => iso ? `${utcShort.format(new Date(iso))} UTC` : "—";
/** Crypto trades 24/7 on venue clocks: its panels read UTC; US markets read ET. */
export const marketClock = (universe: ScreenerUniverse) => universe === "CRYPTO"
  ? { clock: utcClock, day: utcDay, suffix: " UTC", zone: "UTC" as const }
  : { clock: etClock, day: etDay, suffix: " ET", zone: "America/New_York" as const };
const PROVIDER_LABELS: Record<string, string> = { MOOMOO: "Moomoo", IBKR: "IBKR", KRAKEN: "Kraken" };
export const providerLabel = (provider: string | null | undefined) => provider ? PROVIDER_LABELS[provider] ?? provider : "No provider";
/** Pair prices keep the venue's price increment (sub-cent assets included); US prices keep the dollar format. */
export function pricePrecision(row: ScreenerRow | null, value: number) {
  const step = (row?.price_increment?.split(".")[1] ?? "").replace(/0+$/, "").length;
  return Math.min(10, Math.max(step, value >= 1 ? 2 : value >= 0.01 ? 4 : 8));
}
/** Crypto sizes are fractional base units (0.00012 BTC); US sizes stay whole-unit formatted. */
export const marketSize = (value: number, universe: ScreenerUniverse) =>
  value.toLocaleString("en-US", universe === "CRYPTO" ? { maximumFractionDigits: 8 } : undefined);
/** Aggregated volume: Crypto keeps four significant digits below 1,000 base units so 0.0123 BTC never reads 0. */
export const marketVolume = (value: number, universe: ScreenerUniverse) =>
  universe === "CRYPTO" && value !== 0 && Math.abs(value) < 1_000 ? value.toLocaleString("en-US", { maximumSignificantDigits: 4 }) : compact(value);
export const signedMarketVolume = (value: number, universe: ScreenerUniverse) =>
  `${value > 0 ? "+" : value < 0 ? "−" : ""}${marketVolume(Math.abs(value), universe)}`;
/** Sub-0.1 bps spreads (deep crypto books) keep three decimals instead of rounding to 0.0. */
export const spreadBps = (bps: number) => (bps !== 0 && Math.abs(bps) < 0.1 ? bps.toFixed(3) : bps.toFixed(1));
export function marketPrice(value: number, row: ScreenerRow | null, universe: ScreenerUniverse) {
  if (universe !== "CRYPTO") return money(value);
  const digits = pricePrecision(row, value);
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
export function age(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return null;
  const ms = Math.max(0, now - Date.parse(iso));
  return ms < 1000 ? `${ms}ms` : ms < 60_000 ? `${Math.round(ms / 1000)}s` : ms < 3_600_000 ? `${Math.round(ms / 60_000)}m` : `${Math.round(ms / 3_600_000)}h`;
}

export const STATE_LABELS: Record<PanelState, string> = {
  CURRENT: "Current", SESSION_CLOSED: "Session closed", STALE: "Stale", PARTIAL: "Partial", INVALID: "Invalid",
  DISCONNECTED: "Disconnected", NOT_ENTITLED: "Not entitled", UNAVAILABLE: "Unavailable", CONNECTING: "Connecting",
  SUBSCRIPTION_BUSY: "Busy",
};
const REASONS: Record<string, string> = {
  LIVE_RUNTIME_UNAVAILABLE: "Live market data runtime is not running", NO_CURRENT_FEED: "No current provider feed",
  ENTITLEMENT_MISSING: "Provider entitlement missing for this data", PROVIDER_QUOTA_EXHAUSTED: "Provider subscription quota exhausted",
  PROVIDER_SUBSCRIBE_REFUSED: "Provider refused the subscription", SUBSCRIPTION_BUSY: "Subscription slots busy; retrying shortly",
  QUOTA_EXHAUSTED: "Subscription quota exhausted", NOT_SUBSCRIBED: "Acquiring subscription", AWAITING_DATA: "Subscribed; waiting for data",
  NO_CAPTURED_DATA: "No data captured for this session", FEED_SILENT: "Provider feed has gone quiet",
  AWAITING_BOOK_SNAPSHOT: "Waiting for a current book snapshot", LAST_CAPTURED_BOOK: "Last captured book",
  NO_BOOK_UPDATE_WITHIN_TTL: "No book update within the freshness limit", ONE_SIDED_BOOK: "One side of the book is empty",
  CROSSED_BOOK: "Book is crossed and is not displayed", MALFORMED_LEVELS: "Book levels failed validation",
  DISCONNECTED: "Provider disconnected", RECONNECTING: "Provider reconnecting", DISABLED: "Provider disabled",
  CONNECTING: "Provider connecting", NOT_ENTITLED: "No futures quote entitlement", CONTRACT_EXPIRED: "Provider main contract has expired",
  PROVIDER_UNAVAILABLE: "Provider unavailable", MAIN_CONTRACT_UNKNOWN: "Current contract unresolved",
  CONTRACT_REFERENCE_UNAVAILABLE: "Contract reference unavailable", OPEND_UNAVAILABLE: "OpenD is not reachable",
  BAR_SOURCE_UNAVAILABLE: "Current bars unavailable", STALE_BAR_SOURCE: "Bar source is stale", INSUFFICIENT_BARS: "Not enough completed bars",
  MOOMOO_SUBSCRIPTION_BUSY: "Chart data slots busy; retrying shortly", MOOMOO_QUOTE_NOT_ENTITLED: "No quote entitlement for bars",
  MARKET_DATA_UNAVAILABLE: "Market data unavailable",
  MAINTENANCE: "Venue is in maintenance; market data paused", CHECKSUM_MISMATCH: "Book failed the venue checksum; resyncing",
  CRYPTO_BARS_UNAVAILABLE: "Venue bars unavailable", CRYPTO_NOT_CONFIGURED: "Crypto market data is not enabled",
};
export const reasonText = (code: string | null | undefined) => (code && (REASONS[code] ?? code.replace(/_/g, " ").toLowerCase())) || "";

export function StateBadge({ state, label }: { state: PanelState | string; label?: string }) {
  return <span className={`screener-panel-state state-${state.toLowerCase()}`}>{label ?? STATE_LABELS[state as PanelState] ?? state}</span>;
}

type FrameProps = {
  id: PanelId;
  detail?: ReactNode;
  state?: PanelState | string | null;
  /** Plain-language label for a state outside the market-data vocabulary (e.g. S12 disclosure states). */
  stateLabel?: string;
  clock?: ReactNode;
  /** False for a workstation-wide panel (Setup): the header names no instrument. */
  instrumentScoped?: boolean;
  children: ReactNode;
};

/** Compact panel header: title, instrument · class · provider, state, and the panel's own clock. */
export function PanelFrame({ id, detail, state, stateLabel, clock, instrumentScoped = true, children }: FrameProps) {
  const { row: selected, actions } = useSelection();
  const row = instrumentScoped ? selected : null;
  const title = PANEL_TITLES[id];
  return <section className="screener-panel" id={`screener-panel-${id}`} tabIndex={-1} aria-label={`${title}${row ? ` for ${row.symbol}` : ""}`}>
    <header className="screener-panel-header">
      <div className="screener-panel-title"><h2>{title}</h2>
        <span className="screener-panel-meta">{instrumentScoped ? (row ? row.symbol : "No selection") : "Workstation"}{detail ? <> · {detail}</> : null}</span></div>
      <div className="screener-panel-status">{state ? <StateBadge state={state} label={stateLabel} /> : null}{clock ? <span className="screener-panel-clock">{clock}</span> : null}</div>
      <div className="screener-panel-actions" role="group" aria-label={`${title} layout`}>
        <button type="button" onClick={() => actions.move(id, "left")} aria-label={`Move ${title} to the previous group`} title="Move to previous group">‹</button>
        <button type="button" onClick={() => actions.move(id, "right")} aria-label={`Move ${title} to the next group`} title="Move to next group">›</button>
        <button type="button" onClick={() => actions.move(id, "split")} aria-label={`Split ${title} into its own column`} title="Own column">⫿</button>
        <button type="button" onClick={() => actions.resize(id, -48)} aria-label={`Narrow ${title}`} title="Narrow">−</button>
        <button type="button" onClick={() => actions.resize(id, 48)} aria-label={`Widen ${title}`} title="Widen">+</button>
        <button type="button" onClick={() => actions.close(id)} aria-label={`Close ${title}`} title="Close">×</button>
      </div>
    </header>
    <div className="screener-panel-body">{children}</div>
  </section>;
}

/** A stale or missing capability probe is stated, never presented as verified entitlement. */
export function EntitlementNote({ entitlement }: { entitlement?: string }) {
  return entitlement === "UNVERIFIED" ? <p className="screener-panel-note">Entitlement not verified by a current capability probe; the provider's own answer is shown.</p> : null;
}

/** Placeholder body for no selection, loading, and blocked states. */
export function PanelMessage({ children, tone = "muted", role }: { children: ReactNode; tone?: "muted" | "warn" | "error"; role?: "status" | "alert" }) {
  return <p className={`screener-panel-message ${tone}`} role={role ?? "status"}>{children}</p>;
}

type BoundaryState = { error: Error | null };
/** A failure inside one panel stays inside that panel. */
export class PanelErrorBoundary extends Component<{ id: PanelId; children: ReactNode }, BoundaryState> {
  state: BoundaryState = { error: null };
  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Contained: the table, preview, and other panels keep running.
  }
  render() {
    if (!this.state.error) return this.props.children;
    return <section className="screener-panel" id={`screener-panel-${this.props.id}`} tabIndex={-1}>
      <PanelMessage tone="error" role="alert">{PANEL_TITLES[this.props.id]} failed to render. <button type="button" onClick={() => this.setState({ error: null })}>Retry</button></PanelMessage>
    </section>;
  }
}

/** Shared gate for every panel: nothing is requested without a settled selection. */
export function selectionGate(id: PanelId, row: ScreenerRow | null, settledId: string | null) {
  if (!row) return <PanelMessage>Select an instrument to view {PANEL_TITLES[id]}.</PanelMessage>;
  if (settledId !== row.instrument.instrument_id) return <PanelMessage>Loading {row.symbol}…</PanelMessage>;
  return null;
}
