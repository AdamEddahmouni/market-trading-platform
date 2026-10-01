import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import { useInfiniteQuery, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { ColumnPinningState, ColumnSizingState, VisibilityState } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useLocation, useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import { deleteScreenerScreen, fetchScreener, fetchScreenerConfig, type ScreenerPageParam, persistLastScreenerConfig, persistScreenerPanelLayout, persistScreenerPreviewLayout, releaseScreenerWindow, releaseScreenerWindowOnUnload, saveScreenerScreen, updateScreenerWindow, type PanelId, type PanelLayout, type ScreenerFilter, type ScreenerField, type ScreenerQuote, type ScreenerRow, type ScreenerScreen, type ScreenerUniverse } from "../../api/screener";
import { QuickPreview } from "./QuickPreview";
import { PanelLauncher } from "./panels/PanelLauncher";
import { Age, marketPrice, reloadableLazy, ScreenerErrorBoundary } from "./panels/shared";
import { ALWAYS_PANELS, clampDockHeight, DEFAULT_PANEL_LAYOUT, DOCK_HEIGHT_DEFAULT, lastScreenFor, panelLayoutFor } from "./panels/registry";
import { NewsBadge } from "./news/NewsBadge";
import type { NewsActivityRow } from "../../api/screenerNews";
import type { DockHandle } from "./panels/ScreenerDock";
import { exitNewsUpdates, isNewsMode, resetNewsFilterUpdates } from "./news/newsParams";
import { readLastSeen } from "./news/newsSeen";
import { exitIntelUpdates, INTEL_LABELS, intelView, resetIntelUpdates, type IntelView } from "./participants/participantParams";
import "./screener.css";

// Dockview and the specialist panels load only when a panel is first opened.
// Reloadable: after a failed chunk load (network, new deployment) Retry imports it again.
const ScreenerDock = reloadableLazy(() => import("./panels/ScreenerDock"));
// S11: the News view loads only when News mode is first entered.
const NewsView = reloadableLazy(() => import("./news/NewsView"));
// S12: the intelligence views (Institutional, Congress, Positioning) load only when first entered.
const IntelligenceView = reloadableLazy(() => import("./participants/IntelligenceView"));
const UNIVERSE_LABELS: Record<ScreenerUniverse, string> = { US_EQUITIES: "US Equities", FUTURES: "Futures", US_ETFS: "ETFs", BONDS: "Bonds", CRYPTO: "Crypto" };
const DOCK_TABLE_RESERVE = 420;
/** Best-effort layout write: never throws, even if the client call does not return a promise. */
const flushPanelLayout = (layout: PanelLayout, universe: ScreenerUniverse) => { void Promise.resolve().then(() => persistScreenerPanelLayout(layout, universe)).catch(() => undefined); };
/** One news-activity request per grid page: its row ids are stable while the page is loaded. */
const ACTIVITY_BUCKET = 200;

const PREVIEW_MIN = 320;
const PREVIEW_MAX = 720;
const TABLE_MIN = 560;
const NARROW_QUERY = "(max-width: 1279px)";
const clampPreview = (width: number, bodyWidth: number) =>
  Math.round(Math.max(PREVIEW_MIN, Math.min(PREVIEW_MAX, bodyWidth ? bodyWidth - TABLE_MIN : PREVIEW_MAX, width)));
function useNarrow() {
  const query = typeof window !== "undefined" && window.matchMedia ? window.matchMedia(NARROW_QUERY) : null;
  const [narrow, setNarrow] = useState(Boolean(query?.matches));
  useEffect(() => {
    if (!query) return;
    const update = () => setNarrow(query.matches);
    query.addEventListener?.("change", update);
    return () => query.removeEventListener?.("change", update);
  }, []);
  return narrow;
}

type ColumnKey = "symbol" | "company" | "sector" | "industry" | "country" | "price" | "change_pct" | "volume" | "avg_volume" | "rel_volume" | "float_shares" | "shares_outstanding" | "market_cap" | "short_float_pct" | "short_ratio" | "rsi_14" | "eps_ttm" | "pe" | "fwd_pe" | "perf_week" | "earnings_date" | "recommendation" | "bid" | "ask" | "spread_pct" | "root" | "exchange" | "contract_month" | "expiry" | "dte" | "lead" | "tick_size" | "multiplier" | "open_interest"
  | "security_type" | "term" | "coupon" | "issue_date" | "maturity" | "years_to_maturity" | "maturity_bucket" | "tips" | "frn"
  | "auction_date" | "auction_yield" | "auction_real_yield" | "auction_discount_margin" | "bid_to_cover" | "outstanding"
  | "reference_tenor" | "reference_rate" | "indicative_rate"
  | "category" | "issuer" | "isin" | "coupon_type" | "fund_count" | "fund_par_held" | "fund_value_pct" | "report_date"
  | "observed_price" | "observed_yield" | "benchmark_spread" | "observed_date"
  | "base_asset" | "quote_asset" | "venue" | "status" | "base_volume" | "quote_volume" | "high_24h" | "low_24h" | "trade_count";
type SortKey = ColumnKey;
type ColumnDefinition = { key: ColumnKey; label: string; width: number; format: "text" | "price" | "percent" | "compact" | "decimal" | "fixed2" | "rate" | "billions" | "millions" | "per100" | "bp"; title?: string };
const definitions: ColumnDefinition[] = [
  { key: "symbol", label: "Symbol", width: 190, format: "text" },
  { key: "company", label: "Company", width: 180, format: "text" },
  { key: "sector", label: "Sector", width: 140, format: "text" },
  { key: "industry", label: "Industry", width: 170, format: "text" },
  { key: "country", label: "Country", width: 90, format: "text" },
  { key: "price", label: "Price", width: 92, format: "price" },
  { key: "change_pct", label: "Chg %", width: 86, format: "percent" },
  { key: "volume", label: "Volume", width: 103, format: "compact" },
  { key: "avg_volume", label: "Avg Volume", width: 108, format: "compact" },
  { key: "rel_volume", label: "RVOL", width: 76, format: "decimal" },
  { key: "float_shares", label: "Float", width: 93, format: "compact" },
  { key: "shares_outstanding", label: "Shares Out", width: 105, format: "compact" },
  { key: "market_cap", label: "Mkt Cap", width: 95, format: "compact" },
  { key: "short_float_pct", label: "Short Float", width: 94, format: "percent" },
  { key: "short_ratio", label: "Short Ratio", width: 100, format: "decimal" },
  { key: "bid", label: "Bid", width: 90, format: "price" },
  { key: "ask", label: "Ask", width: 90, format: "price" },
  { key: "spread_pct", label: "Spread %", width: 97, format: "percent" },
  { key: "rsi_14", label: "RSI (14)", width: 84, format: "decimal" },
  { key: "eps_ttm", label: "EPS TTM", width: 90, format: "price" },
  { key: "pe", label: "P/E", width: 72, format: "decimal" },
  { key: "fwd_pe", label: "Fwd P/E", width: 82, format: "decimal" },
  { key: "perf_week", label: "Week %", width: 85, format: "percent" },
  { key: "earnings_date", label: "Earnings", width: 108, format: "text" },
  { key: "recommendation", label: "Recommendation", width: 125, format: "text" },
  { key: "root", label: "Root", width: 80, format: "text" },
  { key: "exchange", label: "Exchange", width: 105, format: "text" },
  { key: "contract_month", label: "Month", width: 98, format: "text" },
  { key: "expiry", label: "Expiry", width: 105, format: "text" },
  { key: "dte", label: "DTE", width: 70, format: "decimal" },
  { key: "lead", label: "Lead", width: 70, format: "decimal" },
  { key: "tick_size", label: "Tick", width: 75, format: "decimal" },
  { key: "multiplier", label: "Multiplier", width: 95, format: "decimal" },
  { key: "open_interest", label: "Open Int.", width: 95, format: "compact" },
  // S9 Bonds: terms and auction facts are catalog values; curve and bill-rate columns are reference context.
  { key: "security_type", label: "Type", width: 70, format: "text" },
  { key: "term", label: "Orig. Term", width: 104, format: "text" },
  { key: "coupon", label: "Coupon", width: 82, format: "rate" },
  { key: "issue_date", label: "Issued", width: 100, format: "text" },
  { key: "maturity", label: "Maturity", width: 100, format: "text" },
  { key: "years_to_maturity", label: "Yrs", width: 64, format: "fixed2" },
  { key: "maturity_bucket", label: "Bucket", width: 76, format: "text" },
  { key: "tips", label: "TIPS", width: 58, format: "text" },
  { key: "frn", label: "FRN", width: 56, format: "text" },
  { key: "auction_date", label: "Last Auction", width: 106, format: "text" },
  { key: "auction_yield", label: "Auction Yld", width: 96, format: "rate", title: "Latest auction high yield (bills: investment rate). An auction fact, not a current yield." },
  { key: "auction_real_yield", label: "Auction Real", width: 98, format: "rate", title: "TIPS latest auction high yield, in real terms." },
  { key: "auction_discount_margin", label: "Auction DM", width: 94, format: "rate", title: "FRN latest auction high discount margin." },
  { key: "bid_to_cover", label: "Bid/Cover", width: 86, format: "decimal", title: "Latest auction bid-to-cover ratio; an auction fact, not a signal." },
  { key: "outstanding", label: "Outstanding", width: 100, format: "billions", title: "Amount outstanding at the latest MSPD month end." },
  { key: "reference_tenor", label: "Ref. Tenor", width: 86, format: "text", title: "Nearest published Treasury par-curve tenor." },
  { key: "reference_rate", label: "Ref. Par Yld", width: 96, format: "rate", title: "Treasury par-curve point for the matched tenor: a benchmark, not this security's yield." },
  { key: "indicative_rate", label: "Closing Bid", width: 94, format: "rate", title: "Treasury daily bill rates: indicative closing bid (coupon-equivalent), on-the-run bills only." },
  // S16: categories inside the one Bonds universe, fund-reported (Form N-PORT) terms and holdings, and dated observations.
  { key: "category", label: "Category", width: 96, format: "text" },
  { key: "issuer", label: "Issuer", width: 170, format: "text" },
  { key: "isin", label: "ISIN", width: 124, format: "text" },
  { key: "coupon_type", label: "Cpn Type", width: 92, format: "text" },
  { key: "fund_count", label: "Funds", width: 70, format: "decimal", title: "SEC-registered fund series that reported holding this CUSIP (Form N-PORT)." },
  { key: "fund_par_held", label: "Fund Par", width: 92, format: "millions", title: "Principal reported held across funds' latest filings; not the amount outstanding." },
  { key: "fund_value_pct", label: "Fund Value", width: 94, format: "per100", title: "Median fund fair value per 100 of par at the funds' report dates: stale, never a price." },
  { key: "report_date", label: "Reported", width: 100, format: "text", title: "Latest N-PORT report date for this CUSIP (published about 60 days later)." },
  { key: "observed_price", label: "Obs. Price", width: 92, format: "per100", title: "Latest Treasury buyback or Fed outright purchase price (Fed bill purchases: from the accepted discount rate): a dated observation, not a quote." },
  { key: "observed_yield", label: "Obs. Yield", width: 92, format: "rate", title: "Yield at the observed operation price, on the operation's settlement date." },
  { key: "benchmark_spread", label: "Spread", width: 82, format: "bp", title: "Observed yield minus the same-day interpolated par curve; dated, not current." },
  { key: "observed_date", label: "Obs. Date", width: 100, format: "text", title: "Date of the observed operation price." },
  { key: "base_asset", label: "Base", width: 76, format: "text" },
  { key: "quote_asset", label: "Quote", width: 76, format: "text" },
  { key: "venue", label: "Venue", width: 86, format: "text" },
  { key: "status", label: "Status", width: 86, format: "text" },
  { key: "base_volume", label: "24h Base Vol", width: 108, format: "compact" },
  { key: "quote_volume", label: "24h Quote Vol", width: 112, format: "compact" },
  { key: "high_24h", label: "24h High", width: 92, format: "price" },
  { key: "low_24h", label: "24h Low", width: 92, format: "price" },
  { key: "trade_count", label: "24h Trades", width: 94, format: "compact" },
];
const columnByKey = Object.fromEntries(definitions.map((item) => [item.key, item])) as Record<ColumnKey, ColumnDefinition>;
const textKeys = ["company", "sector", "industry", "country", "earnings_date", "recommendation", "root", "exchange", "contract_month", "expiry",
  "security_type", "term", "issue_date", "maturity", "maturity_bucket", "tips", "frn", "auction_date", "reference_tenor",
  "category", "issuer", "isin", "coupon_type", "report_date", "observed_date",
  "base_asset", "quote_asset", "venue", "status"] as const;
type TextKey = (typeof textKeys)[number];
const textColumns = new Set<string>(textKeys);
const leftAligned = new Set<string>(["symbol", ...textKeys.filter((key) => !["earnings_date", "recommendation"].includes(key))]);
const views: Record<string, ColumnKey[]> = {
  Overview: ["symbol", "price", "change_pct", "volume", "rel_volume", "float_shares", "market_cap", "short_float_pct", "bid", "ask", "spread_pct", "rsi_14"],
  Performance: ["symbol", "price", "change_pct", "perf_week", "volume", "rel_volume", "rsi_14", "market_cap"],
  Technical: ["symbol", "price", "change_pct", "rsi_14", "perf_week", "volume", "rel_volume"],
  Volume: ["symbol", "price", "volume", "avg_volume", "rel_volume", "float_shares", "change_pct"],
  "Short Squeeze": ["symbol", "price", "change_pct", "rel_volume", "volume", "float_shares", "short_float_pct", "short_ratio", "bid", "ask", "spread_pct"],
  Fundamentals: ["symbol", "company", "sector", "industry", "market_cap", "eps_ttm", "pe", "fwd_pe", "earnings_date", "recommendation"],
  Custom: ["symbol", "price", "change_pct", "volume"],
};
const allKeys = definitions.map((item) => item.key);
const sortKeys = new Set(allKeys.filter((key) => !["sector", "industry", "country", "earnings_date", "recommendation"].includes(key)));
const sortFromUrl = (value: string | null): SortKey | null => value && sortKeys.has(value as ColumnKey) ? value as SortKey : null;
const universeFromUrl = (value: string | null): ScreenerUniverse =>
  value === "FUTURES" || value === "US_ETFS" || value === "BONDS" || value === "CRYPTO" ? value : "US_EQUITIES";
const DEFAULT_SORT: Record<ScreenerUniverse, SortKey> = { US_EQUITIES: "volume", FUTURES: "root", US_ETFS: "symbol", BONDS: "maturity", CRYPTO: "symbol" };
export const canonicalScreenerView = (value: string | null, universe: ScreenerUniverse, aliases?: Record<string, string>) =>
  value && universe === "US_EQUITIES" ? (aliases?.[value] ?? (value === "Short" ? "Short Squeeze" : value)) : value;
const viewVisibility = (view: string, choices: Record<string, readonly string[]> = views): VisibilityState =>
  Object.fromEntries(allKeys.map((key) => [key, (choices[view] ?? choices.Overview ?? []).includes(key)]));
const snapshotOf = (screen: ScreenerScreen) => ({ filters: screen.filters, view: screen.view,
  sort: screen.sort, columns: screen.columns });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const quoteKeys = new Set(["price", "volume", "bid", "ask", "spread_pct", "base_volume", "quote_volume"]);
// Load the next server page this many rows before the loaded end is scrolled into view.
const PREFETCH_ROWS = 60;
const resultSetChanged = (error: unknown) => (error as { code?: string } | null)?.code === "SCREENER_RESULT_SET_CHANGED";
// Crypto reads venue UTC everywhere (panels, preview); US universes keep the local wall clock.
const clock = (value: string, universe?: ScreenerUniverse) => universe === "CRYPTO"
  ? `${new Date(value).toISOString().slice(11, 19)} UTC` : new Date(value).toLocaleTimeString();
const COVERAGE_ORDER = ["TREASURY", "CORPORATE", "AGENCY", "MUNICIPAL", "SECURITIZED"];
const coverageRank = (category: string) => (COVERAGE_ORDER.indexOf(category) + 1) || COVERAGE_ORDER.length + 1;
function fieldFor(row: ScreenerRow, key: ColumnKey, quote?: ScreenerQuote) {
  const current = quote?.fields[key];
  if (quoteKeys.has(key) && (current?.state === "LIVE" || current?.state === "DELAYED" || current?.state === "SNAPSHOT") && current.value !== null) return current;
  return row.fields[key];
}
function valueText(field: ScreenerField | undefined, format: (typeof definitions)[number]["format"], signed = false) {
  if (!field || field.value === null) return "—";
  if (format === "price") return field.value.toFixed(2);
  if (format === "percent") return `${signed && field.value > 0 ? "+" : ""}${field.value.toFixed(2)}%`;
  if (format === "rate") return `${field.value.toFixed(3)}%`;
  if (format === "fixed2") return field.value.toFixed(2);
  if (format === "billions") return `$${field.value.toLocaleString("en-US", { maximumFractionDigits: 1 })}B`;
  if (format === "millions") return `$${field.value.toLocaleString("en-US", { maximumFractionDigits: 1 })}M`;
  if (format === "per100") return field.value.toFixed(3);
  if (format === "bp") return `${field.value > 0 ? "+" : ""}${field.value.toFixed(1)} bp`;
  return format === "compact" ? compact.format(field.value) : decimal.format(field.value);
}
const helper = createColumnHelper<ScreenerRow>();

export function ScreenerPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const initialParams = useMemo(() => new URLSearchParams(location.search), []);
  const [universe, setUniverse] = useState<ScreenerUniverse>(() => universeFromUrl(initialParams.get("universe")));
  const [search, setSearch] = useState(initialParams.get("q") ?? "");
  const [sort, setSort] = useState<SortKey>(sortFromUrl(initialParams.get("sort")) ?? DEFAULT_SORT[universe]);
  const [descending, setDescending] = useState(initialParams.has("dir") ? initialParams.get("dir") !== "asc" : universe === "US_EQUITIES");
  const [view, setView] = useState(() => {
    const requested = canonicalScreenerView(initialParams.get("view"), universe);
    return requested && views[requested] ? requested : "Overview";
  });
  const [filters, setFilters] = useState<ScreenerFilter[]>([]);
  const [selectedScreenId, setSelectedScreenId] = useState(initialParams.get("screen") ?? "");
  const [savedBase, setSavedBase] = useState("");
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(() => viewVisibility(view));
  const [columnOrder, setColumnOrder] = useState<string[]>(() => [...(views[view] ?? views.Overview),
    ...allKeys.filter((key) => !(views[view] ?? views.Overview).includes(key))]);
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [columnPinning, setColumnPinning] = useState<ColumnPinningState>({ left: ["symbol"], right: [] });
  const [filterOpen, setFilterOpen] = useState(false);
  const [columnOpen, setColumnOpen] = useState(false);
  const [screenOpen, setScreenOpen] = useState(false);
  const [filterSearch, setFilterSearch] = useState("");
  const [columnSearch, setColumnSearch] = useState("");
  const [editFilterId, setEditFilterId] = useState<string | null>(null);
  const [draftField, setDraftField] = useState("");
  const [draftOperator, setDraftOperator] = useState("gt");
  const [draftValue, setDraftValue] = useState("");
  const [draftSecond, setDraftSecond] = useState("");
  const [saveMode, setSaveMode] = useState<"save" | "save-as" | "rename" | null>(null);
  const [saveName, setSaveName] = useState("");
  const [configError, setConfigError] = useState("");
  const [filterNotice, setFilterNotice] = useState("");
  const [restored, setRestored] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  // The selected row survives page boundaries: Preview and panels never depend on page presence.
  const [selectedCache, setSelectedCache] = useState<ScreenerRow | null>(null);
  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selected;
  const [quotes, setQuotes] = useState<Record<string, ScreenerQuote>>({});
  const [quoteError, setQuoteError] = useState(false);
  const [windowSession, setWindowSession] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const clientId = useRef(crypto.randomUUID().replace(/-/g, ""));
  const quoteQueue = useRef<Promise<void>>(Promise.resolve());
  const previousUniverse = useRef(universe);
  const forceNextRefresh = useRef(false);
  const transientTrigger = useRef<HTMLElement | null>(null);
  const initialized = useRef(false);
  const loadedScreen = useRef<string | null>(null);
  const config = useQuery({ queryKey: ["main-screener-config"], queryFn: fetchScreenerConfig, staleTime: 60_000 });
  const activeSpec = config.data?.universes?.find((item) => item.id === universe);
  const activeViews = activeSpec?.views ?? views;
  const availableKeys = activeSpec?.default_columns ? allKeys.filter((key) => activeSpec.views.Custom?.includes(key) ||
    Object.values(activeSpec.views).some((fields) => fields.includes(key))) : allKeys;
  // Sort/filter support is server metadata: a live-window column may display but never order the universe.
  const fieldCaps = activeSpec?.fields;
  // The universe's own label/unit for a shared field (Crypto change is a UTC-day change).
  const catalogEntry = (name: string) => {
    const entry = config.data?.catalog.find((item) => item.field === name);
    const own = fieldCaps?.[name];
    return entry && own?.label ? { ...entry, label: own.label, unit: own.unit ?? entry.unit } : entry;
  };
  const availableFilters = config.data?.catalog.filter((item) => (item.universes ?? ["US_EQUITIES"]).includes(universe))
    .map((item) => catalogEntry(item.field) ?? item) ?? [];
  const isSortable = (key: string) => Boolean(fieldCaps?.[key]?.sortable);
  const effectiveSort = fieldCaps && !isSortable(sort) ? (activeSpec?.default_sort ?? "volume") as SortKey : sort;
  const snapshotQuery = Boolean(fieldCaps) && (fieldCaps?.[effectiveSort]?.execution === "SNAPSHOT" && universe !== "US_EQUITIES" ||
    filters.some((rule) => universe !== "US_EQUITIES" && fieldCaps?.[rule.field]?.execution === "SNAPSHOT"));
  // News & Analysis is universe-agnostic; the server lists it for every universe.
  const supportedPanels = new Set([...(activeSpec?.panels ?? (universe === "US_EQUITIES" ? ["order_flow", "cvd", "level2", "charts", "futures", "options", "short_squeeze", "news"] : ["news"])), ...ALWAYS_PANELS] as PanelId[]);
  // News is a view inside the active universe (URL `news=1`), never a universe.
  // S12 intelligence views live inside the active universe (URL `intel=…`), only where the registry lists them.
  const intel = intelView(location.search, activeSpec?.intelligence_views);
  const newsMode = isNewsMode(location.search) && !intel;
  // "N new" on the News tab: stories published since this viewer last left News for the universe.
  // Re-read on leaving News (the view writes the mark on unmount); the first visit has no mark and no badge.
  const newsLastSeen = useMemo(() => newsMode ? null : readLastSeen(universe), [universe, newsMode]);
  const newsNew = useQuery({
    queryKey: ["screener-news-new", universe, newsLastSeen],
    // Dynamic import keeps the News contracts out of the Screener's first chunk.
    queryFn: async ({ signal }) => (await import("../../api/screenerNews")).fetchScreenerNews(
      { universe, window: "72h", limit: 1, since: newsLastSeen }, signal),
    enabled: Boolean(newsLastSeen) && supportedPanels.has("news"), staleTime: 30_000, refetchInterval: 60_000, retry: false,
  });
  const newsNewCount = newsLastSeen && newsNew.data?.universe === universe ? newsNew.data.new_count ?? 0 : 0;
  // Universe capabilities come from the registry: a reference-only universe never hands off to a Workspace,
  // and a universe without streaming quotes never opens a quote window.
  const referenceOnly = activeSpec?.tradability === "REFERENCE_ONLY";
  const streamingQuotes = activeSpec?.quote_capability !== "NO_STREAMING_QUOTE";
  useEffect(() => {
    if (!activeSpec || initialized.current || selectedScreenId || universe === "US_EQUITIES") return;
    // A direct link's view is only known to be valid once the universe's views arrive from the server.
    const requested = canonicalScreenerView(new URLSearchParams(location.search).get("view"), universe, activeSpec.view_aliases);
    const initialView = requested && requested !== "Custom" && activeSpec.views[requested] ? requested : "Overview";
    const initialColumns = initialView === "Overview" ? activeSpec.default_columns : activeSpec.views[initialView];
    setView(initialView);
    setColumnVisibility(viewVisibility(initialView, activeSpec.views));
    setColumnOrder([...initialColumns, ...allKeys.filter((key) => !initialColumns.includes(key))]);
  }, [activeSpec, selectedScreenId, universe]);
  const narrow = useNarrow();
  const [previewOpen, setPreviewOpen] = useState(true);
  const [previewWidth, setPreviewWidth] = useState(400);
  const bodyRef = useRef<HTMLDivElement>(null);
  const previewRef = useRef<HTMLElement>(null);
  const layoutRestored = useRef(false);
  const layoutTimer = useRef<number | undefined>(undefined);
  // Specialist panel dock. Arrangement changes are written to a ref and persisted
  // without React state, so moving or resizing panels never re-renders the table.
  const [openPanels, setOpenPanels] = useState<PanelId[]>([]);
  const [pendingPanel, setPendingPanel] = useState<PanelId | null>(null);
  const [dockHeight, setDockHeight] = useState(DOCK_HEIGHT_DEFAULT);
  const dockHeightRef = useRef(DOCK_HEIGHT_DEFAULT);
  const panelLayout = useRef<PanelLayout>({ ...DEFAULT_PANEL_LAYOUT });
  // The universe whose layout `panelLayout` holds. Each universe keeps its own dock arrangement.
  const panelUniverse = useRef<ScreenerUniverse | null>(null);
  // The dock mounts only once its universe's layout is loaded (it reads the layout on mount).
  const [dockUniverse, setDockUniverse] = useState<ScreenerUniverse | null>(null);
  // Bumped by the dock boundary's "Reset layout" to remount the dock on a default arrangement.
  const [dockGeneration, setDockGeneration] = useState(0);
  const panelTimer = useRef<number | undefined>(undefined);
  const dockHandle = useRef<DockHandle | null>(null);
  const dockRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (config.isPending || panelUniverse.current === universe) return;
    const previous = panelUniverse.current;
    // Write the previous universe's pending change under its own universe before switching.
    if (previous !== null && panelTimer.current !== undefined) {
      window.clearTimeout(panelTimer.current);
      panelTimer.current = undefined;
      flushPanelLayout(panelLayout.current, previous);
    }
    panelUniverse.current = universe;
    const saved = panelLayoutFor(config.data, universe);
    if (saved) {
      panelLayout.current = { ...saved, dock_height: clampDockHeight(saved.dock_height) };
      setOpenPanels(saved.open_panels);
    } else if (previous !== null) {
      panelLayout.current = { ...DEFAULT_PANEL_LAYOUT };
      setOpenPanels([]);
    }
    // A panel launched before the first layout arrived stays pending; a switch drops the old universe's request.
    if (previous !== null) setPendingPanel(null);
    setDockHeight(panelLayout.current.dock_height);
    dockHeightRef.current = panelLayout.current.dock_height;
    setDockUniverse(universe);
  }, [config.isPending, config.data, universe]);
  const persistPanels = useCallback(() => {
    const target = panelUniverse.current;
    if (target === null) return;
    // Keep the cached config current: returning to the Screener (or to this universe) within
    // this session must restore the latest arrangement, never the one fetched at first load.
    const latest = panelLayout.current;
    queryClient.setQueryData(["main-screener-config"], (old: typeof config.data) => old
      ? { ...old, panel_layouts: { ...old.panel_layouts, [target]: latest } } : old);
    if (!config.data?.persistence_available) return;
    window.clearTimeout(panelTimer.current);
    panelTimer.current = window.setTimeout(() => { panelTimer.current = undefined; flushPanelLayout(panelLayout.current, target); }, 500);
  }, [config.data?.persistence_available]);
  // A layout change still waiting on the debounce is written once on unmount, never by a timer that outlives the page.
  useEffect(() => () => {
    if (panelTimer.current === undefined || panelUniverse.current === null) return;
    window.clearTimeout(panelTimer.current);
    panelTimer.current = undefined;
    flushPanelLayout(panelLayout.current, panelUniverse.current);
  }, []);
  // The dock boundary's recovery: drop only this universe's saved arrangement, keep the open panels.
  const resetDockAfterError = useCallback(() => {
    panelLayout.current = { ...panelLayout.current, dockview_layout: null };
    persistPanels();
    setDockGeneration((current) => current + 1);
  }, [persistPanels]);
  const onPanelLayout = useCallback((next: Pick<PanelLayout, "open_panels" | "active_panel" | "dockview_layout">) => {
    panelLayout.current = { ...panelLayout.current, ...next };
    persistPanels();
  }, [persistPanels]);
  const onOpenPanels = useCallback((ids: PanelId[]) => {
    setOpenPanels((current) => current.join() === ids.join() ? current : ids);
    if (!ids.length) { panelLayout.current = { ...panelLayout.current, open_panels: [], active_panel: null, dockview_layout: null }; persistPanels(); }
  }, [persistPanels]);
  const launchPanel = useCallback((id: PanelId) => {
    if (dockHandle.current) { dockHandle.current.openOrFocus(id); return; }
    setPendingPanel(id);
    setOpenPanels((current) => current.includes(id) ? current : [...current, id]);
  }, []);
  const openOptionsPanel = useCallback(() => launchPanel("options"), [launchPanel]);
  const openSqueezePanel = useCallback(() => launchPanel("short_squeeze"), [launchPanel]);
  const openRatesPanel = useCallback(() => launchPanel("rates_curve"), [launchPanel]);
  const openNewsPanel = useCallback(() => launchPanel("news"), [launchPanel]);
  const openNewsFor = useCallback((instrumentId: string) => { setSelected(instrumentId); launchPanel("news"); }, [launchPanel]);
  const openParticipantPanel = useCallback((lens: "institutional" | "congress_gov") => launchPanel(lens), [launchPanel]);
  const resetPanels = useCallback(() => {
    dockHandle.current?.reset();
    setDockHeight(DOCK_HEIGHT_DEFAULT);
    dockHeightRef.current = DOCK_HEIGHT_DEFAULT;
    panelLayout.current = { ...panelLayout.current, dock_height: DOCK_HEIGHT_DEFAULT };
    persistPanels();
  }, [persistPanels]);
  // The ref, not the render-time value, is the source for relative steps, so fast
  // key repeats never lose a step to a stale closure.
  const commitDockHeight = (height: number) => {
    // The table keeps at least ~200 px: matches the dock's CSS max-height.
    const next = clampDockHeight(Math.min(height, window.innerHeight - DOCK_TABLE_RESERVE));
    dockHeightRef.current = next;
    setDockHeight(next);
    panelLayout.current = { ...panelLayout.current, dock_height: next };
    persistPanels();
  };
  const onDockSplitterPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const startY = event.clientY, startHeight = dockHeightRef.current, dock = dockRef.current;
    let latest = startHeight;
    const move = (moveEvent: PointerEvent) => {
      latest = clampDockHeight(Math.min(startHeight + startY - moveEvent.clientY, window.innerHeight - DOCK_TABLE_RESERVE));
      if (dock) dock.style.height = `${latest}px`; // no React render per pointer move
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); commitDockHeight(latest); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const onDockSplitterKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const steps: Record<string, number> = { ArrowUp: 16, ArrowDown: -16 };
    if (!(event.key in steps) && event.key !== "Home" && event.key !== "End") return;
    event.preventDefault();
    commitDockHeight(event.key === "Home" ? 1200 : event.key === "End" ? 0 : dockHeightRef.current + steps[event.key]);
  };
  const dockVisible = (openPanels.length > 0 || pendingPanel !== null) && dockUniverse === universe;
  useEffect(() => {
    const layout = config.data?.preview_layout;
    if (!layout || layoutRestored.current) return;
    layoutRestored.current = true;
    setPreviewOpen(layout.open); setPreviewWidth(clampPreview(layout.width, 0));
  }, [config.data?.preview_layout]);
  const persistLayout = (open: boolean, width: number) => {
    if (!config.data?.persistence_available) return;
    window.clearTimeout(layoutTimer.current);
    layoutTimer.current = window.setTimeout(() => { void persistScreenerPreviewLayout({ open, width }).catch(() => undefined); }, 400);
  };
  const urlUpdate = (updates: Record<string, string | null>, replace = false) => {
    const params = new URLSearchParams(location.search);
    for (const [key, value] of Object.entries(updates)) value ? params.set(key, value) : params.delete(key);
    navigate({ pathname: "/screener", search: params.toString() }, { replace });
  };
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const nextUniverse = universeFromUrl(params.get("universe"));
    // Columns, view, and sort come back as this universe last had them; filters never carry across.
    const remembered = nextUniverse !== universe && !params.get("screen") ? lastScreenFor(config.data, nextUniverse) : null;
    if (nextUniverse !== universe) {
      const spec = config.data?.universes?.find((item) => item.id === nextUniverse);
      setUniverse(nextUniverse); setSelected(null); setSelectedCache(null); setQuotes({}); setQuoteError(false);
      if (filters.length) setFilterNotice("Filters were cleared when the universe changed.");
      setFilters([]);
      const rememberedView = remembered ? canonicalScreenerView(remembered.view, nextUniverse, spec?.view_aliases) : null;
      if (remembered && rememberedView) {
        setView(rememberedView); setSort(remembered.sort.field as SortKey);
        setColumnVisibility(Object.fromEntries(allKeys.map((key) => [key, remembered.columns.visible.includes(key)])));
        setColumnOrder([...remembered.columns.order, ...allKeys.filter((key) => !remembered.columns.order.includes(key))]);
        setColumnSizing(remembered.columns.widths); setColumnPinning({ left: remembered.columns.pinned, right: [] });
      } else {
        setView("Overview"); setSort((spec?.default_sort ?? DEFAULT_SORT[nextUniverse]) as SortKey);
        setColumnVisibility(viewVisibility("Overview", spec?.views ?? views));
        setColumnOrder(spec ? [...spec.default_columns, ...allKeys.filter((key) => !spec.default_columns.includes(key))] : allKeys);
        setColumnSizing({}); setColumnPinning({ left: ["symbol"], right: [] });
      }
    }
    setSearch(params.get("q") ?? "");
    setSelectedScreenId(params.get("screen") ?? "");
    const key = params.get("sort");
    const urlSort = sortFromUrl(key);
    if (urlSort && (!config.data?.universes || (config.data.universes.find((item) => item.id === nextUniverse)?.views &&
      Object.values(config.data.universes.find((item) => item.id === nextUniverse)!.views).some((fields) => fields.includes(urlSort))))) setSort(urlSort);
    setDescending(params.has("dir") ? params.get("dir") !== "asc" : remembered?.sort.descending ?? nextUniverse === "US_EQUITIES");
    const nextSpec = config.data?.universes?.find((item) => item.id === nextUniverse);
    const nextView = canonicalScreenerView(params.get("view"), nextUniverse, nextSpec?.view_aliases);
    const nextViews = nextSpec?.views ?? views;
    if (nextView && nextViews[nextView] && nextView !== view) {
      setView(nextView);
      setColumnVisibility(viewVisibility(nextView, nextViews));
    }
  }, [location.search]);
  useEffect(() => {
    if (!config.data) return;
    const params = new URLSearchParams(location.search);
    const id = selectedScreenId;
    const saved = config.data.saved.find((item) => item.id === id);
    const preset = config.data.presets.find((item) => item.id === id && item.status === "SUPPORTED");
    if (id && loadedScreen.current !== id && (saved || preset)) {
      const screenUniverse = saved?.universe ?? preset!.universe ?? "US_EQUITIES";
      const screenSpec = config.data.universes?.find((item) => item.id === screenUniverse);
      const screenViews = screenSpec?.views ?? views;
      if (screenUniverse !== universe) {
        setUniverse(screenUniverse); setSelected(null); setQuotes({});
        urlUpdate({ universe: screenUniverse }, true);
      }
      // A preset's baseline uses the same universe-scoped column set as the live
      // snapshot, so an untouched preset never reads as modified.
      const screenKeys = allKeys.filter((key) => Object.values(screenViews).some((fields) => fields.includes(key)));
      const source = saved ?? { filters: preset!.filters, view: "Overview", sort: { field: "volume", descending: true },
        columns: { visible: screenKeys.filter((key) => screenViews.Overview.includes(key)), order: screenKeys, widths: {}, pinned: ["symbol"] } };
      const sourceView = canonicalScreenerView(source.view, screenUniverse, screenSpec?.view_aliases) ?? "Overview";
      setFilters(source.filters);
      const requestedView = canonicalScreenerView(params.get("view"), screenUniverse, screenSpec?.view_aliases);
      const nextView = requestedView && screenViews[requestedView] ? requestedView : sourceView;
      const overrideColumns = requestedView && requestedView !== sourceView && requestedView !== "Custom" && screenViews[requestedView];
      setView(nextView);
      setSort(sortFromUrl(params.get("sort")) ?? source.sort.field as SortKey);
      setDescending(params.has("dir") ? params.get("dir") !== "asc" : source.sort.descending);
      setColumnVisibility(overrideColumns ? viewVisibility(nextView, screenViews) : Object.fromEntries(allKeys.map((key) => [key, source.columns.visible.includes(key)])));
      setColumnOrder(overrideColumns ? [...screenViews[nextView], ...allKeys.filter((key) => !screenViews[nextView].includes(key))] : source.columns.order);
      setColumnSizing(overrideColumns ? {} : source.columns.widths);
      setColumnPinning({ left: source.columns.pinned, right: [] });
      setSavedBase(JSON.stringify(snapshotOf({ ...source, view: sourceView } as ScreenerScreen)));
      loadedScreen.current = id;
    } else if (!id && (!initialized.current || loadedScreen.current !== null) && lastScreenFor(config.data, universe)) {
      const last = lastScreenFor(config.data, universe)!;
      setFilters(last.filters);
      const requestedView = canonicalScreenerView(params.get("view"), universe, activeSpec?.view_aliases);
      const lastView = canonicalScreenerView(last.view, universe, activeSpec?.view_aliases) ?? "Overview";
      const nextView = requestedView && activeViews[requestedView] ? requestedView : lastView;
      const overrideColumns = requestedView && requestedView !== lastView && requestedView !== "Custom" && activeViews[requestedView];
      setView(nextView); setSort(sortFromUrl(params.get("sort")) ?? last.sort.field as SortKey);
      setDescending(params.has("dir") ? params.get("dir") !== "asc" : last.sort.descending);
      setColumnVisibility(overrideColumns ? viewVisibility(nextView, activeViews) : Object.fromEntries(allKeys.map((key) => [key, last.columns.visible.includes(key)])));
      setColumnOrder(overrideColumns ? [...activeViews[nextView], ...allKeys.filter((key) => !activeViews[nextView].includes(key))] : last.columns.order);
      setColumnSizing(overrideColumns ? {} : last.columns.widths);
      setColumnPinning({ left: last.columns.pinned, right: [] });
      setSavedBase("");
      loadedScreen.current = null;
    } else if (!id && loadedScreen.current !== null) {
      setFilters([]); setView("Overview"); setSort((activeSpec?.default_sort ?? "volume") as SortKey); setDescending(true);
      setColumnVisibility(viewVisibility("Overview", activeViews)); setColumnOrder(allKeys);
      setColumnSizing({}); setColumnPinning({ left: ["symbol"], right: [] });
      setSavedBase(""); loadedScreen.current = null;
    }
    initialized.current = true; setRestored(true);
  }, [config.data, selectedScreenId]);
  const queryInput = { universe, search, sort: effectiveSort, descending, filters };
  const query = useInfiniteQuery({
    // Every page belongs to this canonical query identity; a change starts a new chain.
    queryKey: ["main-screener", universe, search, effectiveSort, descending, filters],
    initialPageParam: { offset: 0, resultSet: null } as ScreenerPageParam,
    queryFn: ({ pageParam, signal }) => {
      const first = pageParam.offset === 0;
      const force = first && forceNextRefresh.current;
      if (first) forceNextRefresh.current = false;
      return fetchScreener(queryInput, pageParam, { refresh: force, selected: first ? selectedRef.current : null, signal });
    },
    getNextPageParam: (last) => last.has_more && last.result_set_id
      ? { offset: (last.offset ?? 0) + last.rows.length, resultSet: last.result_set_id } : undefined,
    enabled: !config.isPending,
    // A changed result set restarts the chain instead of retrying; other errors keep the client default.
    retry: (count, error) => {
      if (resultSetChanged(error)) return false;
      const fallback = queryClient.getDefaultOptions().queries?.retry;
      return typeof fallback === "function" ? fallback(count, error) : typeof fallback === "number" ? count < fallback : fallback !== false && count < 3;
    },
    staleTime: 30_000, refetchInterval: 120_000,
  });
  const firstPage = query.data?.pages[0];
  const rows = useMemo(() => {
    const seen = new Set<string>();
    const merged: ScreenerRow[] = [];
    for (const page of query.data?.pages ?? []) {
      for (const row of page.rows) {
        if (seen.has(row.instrument.instrument_id)) continue;
        seen.add(row.instrument.instrument_id); merged.push(row);
      }
    }
    return merged;
  }, [query.data]);
  const resultCount = firstPage?.source_error ? null : firstPage?.result_count ?? null;
  // First and last grid page on screen (as row offsets), set from the virtualizer below.
  const [visibleRange, setVisibleRange] = useState<[number, number]>([0, 0]);
  // A later page whose pinned snapshot is gone restarts the chain at page 1; loaded rows stay until it lands.
  useEffect(() => {
    if (query.isFetchNextPageError && resultSetChanged(query.error)) void query.refetch();
  }, [query.isFetchNextPageError, query.error]);
  // News badge: story counts for the grid pages on screen, fetched per page so scrolling within a page reuses one request.
  const newsBadges = supportedPanels.has("news") && !newsMode && !intel;
  const [firstVisible, lastVisibleIndex] = visibleRange;
  const activityBuckets = useMemo(() => {
    if (!newsBadges || !rows.length) return [];
    const buckets: string[][] = [];
    for (let bucket = Math.floor(firstVisible / ACTIVITY_BUCKET); bucket <= Math.floor(Math.min(lastVisibleIndex, rows.length - 1) / ACTIVITY_BUCKET); bucket += 1) {
      buckets.push(rows.slice(bucket * ACTIVITY_BUCKET, (bucket + 1) * ACTIVITY_BUCKET).map((row) => row.instrument.instrument_id));
    }
    return buckets;
  }, [newsBadges, rows, firstVisible, lastVisibleIndex]);
  const activityQueries = useQueries({ queries: activityBuckets.map((ids) => ({
    queryKey: ["screener-news-activity", universe, ids.join(",")],
    // Dynamic import keeps the News contracts out of the Screener's first chunk.
    queryFn: async ({ signal }: { signal: AbortSignal }) => (await import("../../api/screenerNews")).fetchNewsActivity(universe, ids, signal),
    staleTime: 60_000, refetchInterval: 120_000, retry: false,
  })) });
  const newsActivity = useMemo(() => {
    const merged: Record<string, NewsActivityRow> = {};
    const pending = new Set<string>();
    activityQueries.forEach((item, index) => {
      if (item.data?.universe === universe) Object.assign(merged, item.data.instruments);
      else if (item.isPending) for (const id of activityBuckets[index] ?? []) pending.add(id);
    });
    return { rows: merged, pending };
    // The query results array is new each render; its data identities are what matter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activityQueries.map((item) => item.dataUpdatedAt).join(","), activityBuckets, universe]);
  const columns = useMemo(() => definitions.map((definition) => helper.display({
    id: definition.key, header: definition.key === "symbol" && referenceOnly ? "Security · CUSIP" : definition.key === "symbol" && universe === "CRYPTO" ? "Pair" : definition.key === "change_pct" && universe === "CRYPTO" ? "UTC day %" : definition.label, size: definition.width,
    cell: ({ row }) => {
      const item = row.original;
      if (definition.key === "symbol") return <span className="screener-symbol"><strong>{item.symbol}</strong>
        {newsBadges && <NewsBadge row={newsActivity.rows[item.instrument.instrument_id]} pending={newsActivity.pending.has(item.instrument.instrument_id)}
          symbol={item.symbol} onOpen={() => openNewsFor(item.instrument.instrument_id)} />}<small>{universe === "CRYPTO" ? item.venue : item.company}</small></span>;
      if (textColumns.has(definition.key)) {
        const value = item[definition.key as TextKey] ?? null;
        const reason = definition.key === "reference_tenor" && !value && item.reference_reason ? item.reference_reason.replace(/_/g, " ").toLowerCase() : null;
        return <span title={reason ?? definition.title ?? value ?? "Unavailable"}>{value || "—"}</span>;
      }
      if (definition.key === "lead") return <span>{item.lead ? "Lead" : "—"}</span>;
      const field = fieldFor(item, definition.key, quotes[item.instrument.instrument_id]);
      const tone = definition.key === "change_pct" && field?.value != null
        ? field.value > 0 ? "screener-positive" : field.value < 0 ? "screener-negative" : "" : "";
      const detail = field ? [field.source, field.state, field.basis, field.as_of ? `as of ${field.as_of}` : null].filter(Boolean).join(" · ") : "Unavailable";
      return <span className={tone} title={definition.title ? `${definition.title}\n${detail}` : detail}>{universe === "CRYPTO" && definition.format === "price" && field?.value != null
        ? marketPrice(field.value, item, universe) : valueText(field, definition.format, definition.key === "change_pct")}</span>;
    },
  })), [quotes, referenceOnly, universe, newsBadges, newsActivity]);
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel(), getRowId: (row) => row.instrument.instrument_id,
    state: { columnVisibility, columnOrder, columnSizing, columnPinning },
    onColumnVisibilityChange: setColumnVisibility, onColumnOrderChange: setColumnOrder,
    onColumnSizingChange: setColumnSizing, onColumnPinningChange: setColumnPinning,
    columnResizeMode: "onChange" });
  const loaderRow = query.hasNextPage ? 1 : 0;
  // Rows the grid can never reach: the source stopped paging short of its own count, or paging failed.
  const unreachable = resultCount !== null && rows.length < resultCount;
  const truncated = !unreachable || query.isPending ? null
    : query.isFetchNextPageError ? `Showing ${rows.length.toLocaleString()} of ${resultCount!.toLocaleString()}: loading more failed`
    : !query.hasNextPage ? `Showing ${rows.length.toLocaleString()} of ${resultCount!.toLocaleString()}: the source returned no further pages`
    : null;
  const virtualizer = useVirtualizer({ count: rows.length + loaderRow, getScrollElement: () => scrollRef.current, estimateSize: () => 34, overscan: 5 });
  const virtualRows = virtualizer.getVirtualItems();
  const indices = virtualRows.map((item) => item.index).join(",");
  const lastVirtual = virtualRows.length ? virtualRows[virtualRows.length - 1].index : -1;
  const firstVirtual = virtualRows.length ? virtualRows[0].index : 0;
  // Page granularity is enough: only a scroll into another 200-row page changes the badge request.
  useEffect(() => {
    const next: [number, number] = [Math.floor(firstVirtual / ACTIVITY_BUCKET) * ACTIVITY_BUCKET, Math.floor(Math.max(lastVirtual, 0) / ACTIVITY_BUCKET) * ACTIVITY_BUCKET];
    setVisibleRange((current) => current[0] === next[0] && current[1] === next[1] ? current : next);
  }, [firstVirtual, lastVirtual]);
  useEffect(() => {
    if (!query.hasNextPage || query.isFetchingNextPage || query.isFetchNextPageError || query.isRefetching) return;
    if (lastVirtual >= rows.length - PREFETCH_ROWS) void query.fetchNextPage();
  }, [lastVirtual, rows.length, query.hasNextPage, query.isFetchingNextPage, query.isFetchNextPageError, query.isRefetching]);
  // Loaded rows are not subscribed: only visible rows plus the selection acquire L1.
  const visible = useMemo(() => {
    const ids = virtualRows.slice(0, 26).map((item) => rows[item.index]?.instrument.instrument_id).filter((id): id is string => Boolean(id));
    if (selected) ids.unshift(selected);
    return [...new Set(ids)].slice(0, 32);
  }, [indices, rows, selected]);
  useEffect(() => {
    if (previousUniverse.current === universe) return;
    previousUniverse.current = universe;
    setQuotes({}); setQuoteError(false); setWindowSession(null);
    quoteQueue.current = quoteQueue.current.then(async () => { await releaseScreenerWindow(clientId.current); }).catch(() => undefined);
  }, [universe]);
  const windowKey = visible.join(",");
  useEffect(() => {
    if (!windowKey || !streamingQuotes) return;
    let cancelled = false;
    const refresh = () => {
      quoteQueue.current = quoteQueue.current.then(async () => {
        if (cancelled) return;
        try {
          const payload = universe === "US_EQUITIES"
            ? await updateScreenerWindow(clientId.current, visible)
            : await updateScreenerWindow(clientId.current, visible, universe);
          if (!cancelled) { setQuotes(payload.quotes); setQuoteError(false); setWindowSession(payload.market_session); }
        } catch {
          if (!cancelled) { setQuotes({}); setQuoteError(true); }
        }
      });
    };
    refresh();
    const timer = window.setInterval(refresh, universe === "CRYPTO" ? 15_000 : 3_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [windowKey, universe, streamingQuotes]);
  useEffect(() => () => {
    void quoteQueue.current
      .then(() => releaseScreenerWindow(clientId.current))
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    const release = () => releaseScreenerWindowOnUnload(clientId.current);
    window.addEventListener("pagehide", release);
    return () => window.removeEventListener("pagehide", release);
  }, []);
  useEffect(() => {
    const shortcut = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey ||
          event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  // A selection filtered or searched out of the settled result set is cleared, so
  // the preview never shows an instrument the table no longer lists. A selection
  // that is still matched but not in a loaded page (the server reports its
  // position) stays selected.
  useEffect(() => {
    if (!selected || !query.isSuccess || query.isFetching || rows.some((row) => row.instrument.instrument_id === selected)) return;
    if (firstPage?.selected_id === selected && firstPage.selected_index != null) return;
    setSelected(null);
  }, [rows, selected, query.isSuccess, query.isFetching, firstPage]);
  const selectedIndex = rows.findIndex((row) => row.instrument.instrument_id === selected);
  const selectedRow = selectedIndex >= 0 ? rows[selectedIndex]
    : selectedCache?.instrument.instrument_id === selected ? selectedCache : null;
  useEffect(() => {
    if (selectedIndex >= 0) setSelectedCache(rows[selectedIndex]);
    else if (!selected) setSelectedCache(null);
  }, [selectedIndex >= 0 ? rows[selectedIndex] : null, selected]);
  const activate = (index: number) => {
    const row = rows[index];
    if (!row) return;
    setSelected(row.instrument.instrument_id);
    virtualizer.scrollToIndex(index, { align: "auto" });
  };
  const open = useCallback((row: ScreenerRow) => {
    // A reference-only identity (e.g. a Treasury CUSIP) is never routed to a Workspace as if it were a ticker;
    // its reference detail is the Quick Preview.
    if (referenceOnly || row.instrument.tradability === "REFERENCE_ONLY" || row.instrument.tradability === "DISCOVERY_ONLY") {
      setSelected(row.instrument.instrument_id); setPreviewOpen(true);
      return;
    }
    navigate(workspacePathForInstrument(row.instrument.instrument_id, row.instrument.asset_class === "FUTURE" ? "futures" : ""));
  }, [navigate, referenceOnly]);
  const closePreview = useCallback(() => {
    setPreviewOpen(false); persistLayout(false, previewWidth);
    scrollRef.current?.focus();
  }, [previewWidth, config.data?.persistence_available]);
  const togglePreview = () => { const next = !previewOpen; setPreviewOpen(next); persistLayout(next, previewWidth); };
  const commitWidth = (width: number) => {
    const next = clampPreview(width, bodyRef.current?.clientWidth ?? 0);
    setPreviewWidth(next); persistLayout(true, next);
    return next;
  };
  const onSplitterPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const startX = event.clientX, startWidth = previewWidth, pane = previewRef.current;
    let latest = startWidth;
    const move = (moveEvent: PointerEvent) => {
      latest = clampPreview(startWidth + startX - moveEvent.clientX, bodyRef.current?.clientWidth ?? 0);
      if (pane) pane.style.width = `${latest}px`; // no React render per pointer move
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); commitWidth(latest); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const onSplitterKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const steps: Record<string, number> = { ArrowLeft: 16, ArrowRight: -16, Home: PREVIEW_MAX, End: -PREVIEW_MAX };
    if (!(event.key in steps)) return;
    event.preventDefault();
    commitWidth(event.key === "Home" ? PREVIEW_MAX : event.key === "End" ? PREVIEW_MIN : previewWidth + steps[event.key]);
  };
  const onGridKeyDown = (event: KeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      activate(Math.min(rows.length - 1, Math.max(0, selectedIndex < 0 ? 0 : selectedIndex + (event.key === "ArrowDown" ? 1 : -1))));
    } else if (event.key === "Enter" && selectedIndex >= 0) open(rows[selectedIndex]);
    else if (event.key === "Escape") setSelected(null);
  };
  const sortBy = (key: SortKey) => {
    const nextDescending = sort === key ? !descending : key !== "symbol";
    setSort(key); setDescending(nextDescending);
    urlUpdate({ sort: key, dir: nextDescending ? "desc" : "asc" });
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  };
  const chooseView = (next: string) => {
    setView(next);
    if (next !== "Custom") {
      setColumnVisibility(viewVisibility(next, activeViews));
      setColumnOrder([...activeViews[next], ...allKeys.filter((key) => !activeViews[next].includes(key))]);
      setColumnSizing({}); setColumnPinning({ left: ["symbol"], right: [] });
    }
    // A column view always leaves News mode and any intelligence view.
    urlUpdate({ view: next, ...exitNewsUpdates(), ...exitIntelUpdates() });
  };
  const beginFilter = (field: string, existing?: ScreenerFilter) => {
    const definition = catalogEntry(field);
    if (!definition) return;
    setDraftField(field);
    setDraftOperator(existing?.operator ?? definition.operators[0]);
    setDraftValue(existing ? String(Array.isArray(existing.value) ? existing.value[0] : existing.value) : "");
    setDraftSecond(existing && Array.isArray(existing.value) ? String(existing.value[1]) : "");
    setEditFilterId(existing?.id ?? null);
  };
  const applyFilter = () => {
    const definition = catalogEntry(draftField);
    if (!definition) return;
    let value: ScreenerFilter["value"];
    if (definition.type === "number") {
      const first = Number(draftValue); const second = Number(draftSecond);
      if (!draftValue.trim() || !Number.isFinite(first) || (draftOperator === "between" && (!draftSecond.trim() || !Number.isFinite(second) || second < first))) return;
      value = draftOperator === "between" ? [first, second] : first;
    } else {
      if (!draftValue.trim()) return;
      value = ["in", "not_in"].includes(draftOperator) ? draftValue.split(",").map((part) => part.trim()).filter(Boolean) : draftValue.trim();
    }
    const rule = { id: editFilterId ?? crypto.randomUUID().replace(/-/g, ""), field: draftField, operator: draftOperator, value };
    setFilters((current) => editFilterId ? current.map((item) => item.id === editFilterId ? rule : item) : [...current, rule]);
    setFilterOpen(false); setDraftField(""); setEditFilterId(null);
    transientTrigger.current?.focus();
  };
  const closeTransient = () => {
    setFilterOpen(false); setColumnOpen(false); setScreenOpen(false); setSaveMode(null);
    transientTrigger.current?.focus();
  };
  const modifyColumn = (key: ColumnKey, visible: boolean) => {
    if (key === "symbol" && !visible) return;
    setColumnVisibility((current) => ({ ...current, [key]: visible }));
    setView("Custom"); urlUpdate({ view: "Custom" });
  };
  const moveColumn = (key: ColumnKey, direction: number) => {
    const order = [...columnOrder]; const index = order.indexOf(key);
    const next = index + direction;
    if (next < 0 || next >= order.length) return;
    [order[index], order[next]] = [order[next], order[index]];
    setColumnOrder(order); setView("Custom"); urlUpdate({ view: "Custom" });
  };
  const currentSnapshot = () => ({ filters, view, sort: { field: sort, descending },
    columns: { visible: availableKeys.filter((key) => columnVisibility[key] !== false), order: columnOrder.filter((key) => availableKeys.includes(key as ColumnKey)),
      widths: Object.fromEntries(Object.entries(columnSizing).filter(([key]) => availableKeys.includes(key as ColumnKey))),
      pinned: (columnPinning.left ?? []).filter((key) => availableKeys.includes(key as ColumnKey)) } });
  const lastSerialized = JSON.stringify(currentSnapshot());
  useEffect(() => {
    if (!restored || !config.data?.persistence_available) return;
    const timer = window.setTimeout(() => {
      const snapshot = JSON.parse(lastSerialized) as ReturnType<typeof currentSnapshot>;
      const screen = { name: "Last Used", universe, ...snapshot };
      // Cache it per universe so switching back within this session restores these columns.
      queryClient.setQueryData(["main-screener-config"], (old: typeof config.data) => old
        ? { ...old, last_by_universe: { ...old.last_by_universe, [universe]: { ...screen, id: "user-last", version: 2 } } } : old);
      void persistLastScreenerConfig(screen).catch(() => undefined);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [lastSerialized, restored, config.data?.persistence_available, universe]);
  const changed = Boolean(selectedScreenId && savedBase && savedBase !== JSON.stringify(currentSnapshot()));
  const selectedSaved = config.data?.saved.find((item) => item.id === selectedScreenId);
  const selectedPreset = config.data?.presets.find((item) => item.id === selectedScreenId);
  const selectedName = selectedSaved?.name ?? selectedPreset?.name ?? "Unsaved Screen";
  const saveCurrent = async () => {
    const name = saveName.trim();
    if (!name) return;
    try {
      const screen = { ...(saveMode === "save" || saveMode === "rename" ? { id: selectedSaved?.id, version: 2 } : {}),
        name, universe, ...currentSnapshot() };
      const response = await saveScreenerScreen(screen);
      queryClient.setQueryData(["main-screener-config"], (old: typeof config.data) => old ? { ...old, saved: response.saved } : old);
      setSelectedScreenId(response.result.id);
      loadedScreen.current = response.result.id;
      setSavedBase(JSON.stringify(currentSnapshot()));
      setSaveMode(null); setConfigError("");
      urlUpdate({ screen: response.result.id });
      transientTrigger.current?.focus();
    } catch { setConfigError("Unable to save this screen."); }
  };
  const removeSaved = async () => {
    if (!selectedSaved) return;
    try {
      const response = await deleteScreenerScreen(selectedSaved.id);
      queryClient.setQueryData(["main-screener-config"], (old: typeof config.data) => old ? { ...old, saved: response.saved } : old);
      setSelectedScreenId(""); setSavedBase(""); setScreenOpen(false);
      loadedScreen.current = null;
      urlUpdate({ screen: null });
    } catch { setConfigError("Unable to delete this screen."); }
  };
  const labelFilter = (rule: ScreenerFilter) => {
    const definition = catalogEntry(rule.field);
    const operator = { eq: "=", ne: "≠", gt: ">", gte: "≥", lt: "<", lte: "≤", between: "", in: "in", not_in: "not in", contains: "contains" }[rule.operator] ?? rule.operator;
    const value = Array.isArray(rule.value) ? rule.value.join(rule.operator === "between" ? "–" : ", ") : String(rule.value);
    return `${definition?.label ?? rule.field} ${operator} ${definition?.unit === "USD" ? "$" : ""}${value}${definition?.unit === "percent" ? "%" : ""}`.replace(/\s+/g, " ").trim();
  };
  const rawSession = universe === "FUTURES" ? windowSession ?? firstPage?.market_session : firstPage?.market_session;
  // Crypto is continuous: "24/7", never an equity session label.
  const session = rawSession === "24_7" ? "24/7" : rawSession?.replace(/_/g, " ").toLowerCase() ?? "—";
  const quoteStates = Object.values(quotes).map((quote) => quote.state);
  const quoteReasons = Object.values(quotes).map((quote) => quote.reason);
  const quoteLabel = quoteError ? "unavailable" :
    quoteStates.includes("LIVE") ? "live for visible rows" :
    quoteStates.includes("DELAYED") ? "delayed" :
    // Crypto visible rows refresh from the venue's public REST ticker, not a stream.
    quoteStates.includes("SNAPSHOT") ? "REST snapshot for visible rows" :
    quoteStates.includes("STALE") ? "stale" : "unavailable";
  return <section className="screener-page" aria-label="Screener">
    <header className="screener-topline"><div className="screener-brand"><Link to="/" aria-label="IMP home">IMP</Link><span className="screener-brand-divider" /><h1>Screener</h1></div>
      <label className="screener-search"><span className="sr-only">Search instruments</span>
        <input ref={searchRef} value={search} onChange={(event) => { setSearch(event.target.value); urlUpdate({ q: event.target.value || null }, true); }}
          onKeyDown={(event) => { if (event.key === "Escape") { setSearch(""); urlUpdate({ q: null }, true); event.currentTarget.blur(); } }}
          placeholder={universe === "FUTURES" ? "Search root, contract or description  /" : universe === "CRYPTO" ? "Search pair, base or quote  /" : referenceOnly ? "Search CUSIP, description, type or maturity  /" : "Search symbol or name  /"} /></label><span className="screener-market-badge">{rawSession === "24_7" ? "24/7" : rawSession ?? "MARKET"}</span></header>
    <div className="screener-toolbar"><label>Universe <select aria-label="Screener universe" value={universe} onChange={(event) => {
      const next = event.target.value as ScreenerUniverse;
      setSelectedScreenId(""); loadedScreen.current = null; setSavedBase("");
      // News mode, window, and sort survive a universe switch; News filters reset. An intelligence
      // view survives only if the next universe offers it; its window, sort, and filters reset.
      const nextViews = config.data?.universes.find((item) => item.id === next)?.intelligence_views ?? [];
      urlUpdate({ universe: next, screen: null, view: null, sort: null, dir: null, ...resetNewsFilterUpdates(),
        ...(intel && nextViews.includes(intel) ? resetIntelUpdates() : exitIntelUpdates()) });
    }}>{(config.data?.universes ?? [
      { id: "US_EQUITIES", label: "US Equities" }, { id: "FUTURES", label: "Futures" }, { id: "US_ETFS", label: "ETFs" },
      { id: "CRYPTO", label: "Crypto" },
    ]).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><span>Session <strong>{session}</strong></span>
      <div className="screener-toolbar-end"><button type="button" className="screener-control" onClick={(event) => { transientTrigger.current = event.currentTarget; setScreenOpen(!screenOpen); setColumnOpen(false); setFilterOpen(false); }} aria-expanded={screenOpen} aria-haspopup="dialog">{selectedName}{changed ? " *" : ""} ▾</button>
        <button type="button" className="screener-control screener-primary" disabled={!config.data?.persistence_available} onClick={(event) => { transientTrigger.current = event.currentTarget; setSaveName(selectedSaved?.name ?? ""); setSaveMode(selectedSaved ? "save" : "save-as"); }}>Save</button>
        <button type="button" className="screener-control" onClick={(event) => { transientTrigger.current = event.currentTarget; setColumnOpen(!columnOpen); setFilterOpen(false); setScreenOpen(false); }} aria-expanded={columnOpen} aria-haspopup="dialog">Columns</button>
        <button type="button" className="screener-control" aria-pressed={previewOpen} onClick={togglePreview}>Preview</button></div></div>
    <div className="screener-tabs" role="tablist" aria-label="Screener views">{(activeSpec?.view_order ?? Object.keys(activeViews)).filter((name) => activeViews[name]).map((name) => <button key={name} type="button" role="tab" aria-selected={!newsMode && !intel && view === name} onClick={() => chooseView(name)}>{name}</button>)}
      <button type="button" role="tab" aria-selected={newsMode} className="screener-news-tab" onClick={() => { if (!newsMode) urlUpdate({ news: "1", ...exitIntelUpdates() }); }}
        aria-label={newsNewCount ? `News, ${newsNewCount} new ${newsNewCount === 1 ? "story" : "stories"} since last view` : undefined}>
        News{newsNewCount > 0 && <span className="screener-news-count" aria-hidden="true">{newsNewCount > 99 ? "99+" : newsNewCount} new</span>}</button>
      {(activeSpec?.intelligence_views ?? []).map((id) => <button key={id} type="button" role="tab" aria-selected={intel === id}
        className="screener-news-tab screener-intel-tab" onClick={() => { if (intel !== id) urlUpdate({ intel: id, ...resetIntelUpdates(), ...exitNewsUpdates() }); }}>{INTEL_LABELS[id as IntelView] ?? id}</button>)}</div>
    {filterNotice && <div className="screener-filter-notice" role="status">{filterNotice}<button type="button" onClick={() => setFilterNotice("")} aria-label="Dismiss filter notice">×</button></div>}
    <div className="screener-filters" aria-label="Active filters">{filters.map((rule) => <span className="screener-chip" key={rule.id}>
      <button type="button" onClick={(event) => { transientTrigger.current = event.currentTarget; beginFilter(rule.field, rule); setFilterOpen(true); }} aria-label={`Edit ${catalogEntry(rule.field)?.label ?? rule.field}`}>{labelFilter(rule)}</button>
      <button type="button" onClick={() => setFilters((current) => current.filter((item) => item.id !== rule.id))} aria-label={`Remove ${catalogEntry(rule.field)?.label ?? rule.field}`}>×</button></span>)}
      <button type="button" className="screener-add" onClick={(event) => { transientTrigger.current = event.currentTarget; setFilterOpen(!filterOpen); setColumnOpen(false); setScreenOpen(false); setDraftField(""); setFilterSearch(""); }} aria-expanded={filterOpen} aria-haspopup="dialog">+ Add Filter</button>
      {filters.length > 0 && <button type="button" className="screener-clear" onClick={() => setFilters([])}>Clear All</button>}
    </div>
    {filterOpen && <div className="screener-popover screener-filter-popover" role="dialog" aria-label={draftField ? "Edit filter" : "Add filter"} onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); closeTransient(); } }}>
      <button type="button" className="screener-popover-close" onClick={closeTransient} aria-label="Close filter picker">×</button>
      {!draftField ? <><input autoFocus aria-label="Search filters" placeholder="Search filters..." value={filterSearch} onChange={(event) => setFilterSearch(event.target.value)} />
        <div className="screener-picker-list">{[...new Set(availableFilters.map((item) => item.category))].map((category) => <div key={category}><h3>{category}</h3>{availableFilters.filter((item) => item.category === category && item.label.toLowerCase().includes(filterSearch.toLowerCase())).map((item) => <button key={item.field} type="button" onClick={() => beginFilter(item.field)}>{item.label}</button>)}</div>)}</div></> : <>
        <h3>{catalogEntry(draftField)?.label}</h3>
        <label>Operator <select aria-label="Filter operator" value={draftOperator} onChange={(event) => setDraftOperator(event.target.value)}>{catalogEntry(draftField)?.operators.map((operator) => <option key={operator} value={operator}>{({ eq: "Equals", ne: "Not equals", gt: "Greater than", gte: "At least", lt: "Less than", lte: "At most", between: "Between", in: "In", not_in: "Not in", contains: "Contains" } as Record<string, string>)[operator]}</option>)}</select></label>
        <label>Value <input autoFocus aria-label="Filter value" type={catalogEntry(draftField)?.type === "number" ? "number" : "text"} value={draftValue} onChange={(event) => setDraftValue(event.target.value)} /></label>
        {draftOperator === "between" && <label>Maximum <input aria-label="Filter maximum" type="number" value={draftSecond} onChange={(event) => setDraftSecond(event.target.value)} /></label>}
        <div className="screener-popover-actions"><button type="button" onClick={() => setDraftField("")}>Back</button><button type="button" className="screener-primary" onClick={applyFilter} disabled={!draftValue.trim() || (draftOperator === "between" && !draftSecond.trim())}>Apply Filter</button></div></>}
    </div>}
    {screenOpen && <div className="screener-popover screener-screen-popover" role="dialog" aria-label="Saved screens" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); closeTransient(); } }}>
      <button type="button" className="screener-popover-close" onClick={closeTransient} aria-label="Close saved screens">×</button>
      <h3>My Screens</h3>{config.data?.saved.length ? config.data.saved.map((item) => <button key={item.id} type="button" onClick={() => { loadedScreen.current = null; setSelectedScreenId(item.id); urlUpdate({ screen: item.id, universe: item.universe, view: null, sort: null, dir: null }); setScreenOpen(false); }}>{item.name} · {config.data?.universes?.find((spec) => spec.id === item.universe)?.label ?? item.universe}</button>) : <span className="screener-popover-note">No personal screens</span>}
      <h3>Built-in</h3>{config.data?.presets.map((item) => <button key={item.id} type="button" disabled={item.status !== "SUPPORTED"} title={item.reason ?? undefined} onClick={() => { loadedScreen.current = null; setSelectedScreenId(item.id); urlUpdate({ screen: item.id, universe: item.universe ?? "US_EQUITIES", view: null, sort: null, dir: null }); setScreenOpen(false); }}>{item.name}{item.status !== "SUPPORTED" ? " · unavailable" : ""}</button>)}
      {selectedSaved && <div className="screener-popover-actions"><button type="button" onClick={() => { setSaveName(selectedSaved.name); setSaveMode("rename"); setScreenOpen(false); }}>Rename</button><button type="button" onClick={() => { void removeSaved(); }}>Delete</button></div>}
      {selectedPreset && changed && <button type="button" onClick={() => { setFilters(selectedPreset.filters); setView("Overview"); setColumnVisibility(viewVisibility("Overview", activeViews)); setScreenOpen(false); }}>Reset preset</button>}
    </div>}
    {columnOpen && <div className="screener-popover screener-column-popover" role="dialog" aria-label="Configure columns" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); closeTransient(); } }}>
      <button type="button" className="screener-popover-close" onClick={closeTransient} aria-label="Close columns">×</button>
      <input autoFocus aria-label="Search columns" placeholder="Search columns..." value={columnSearch} onChange={(event) => setColumnSearch(event.target.value)} />
      <div className="screener-column-list">{columnOrder.filter((key) => availableKeys.includes(key as ColumnKey) && columnByKey[key as ColumnKey]?.label.toLowerCase().includes(columnSearch.toLowerCase())).map((key) => <div className="screener-column-item" key={key}>
        <label><input type="checkbox" checked={columnVisibility[key] !== false} disabled={key === "symbol"} onChange={(event) => modifyColumn(key as ColumnKey, event.target.checked)} />{columnByKey[key as ColumnKey].label}</label>
        <button type="button" onClick={() => moveColumn(key as ColumnKey, -1)} aria-label={`Move ${columnByKey[key as ColumnKey].label} left`}>↑</button><button type="button" onClick={() => moveColumn(key as ColumnKey, 1)} aria-label={`Move ${columnByKey[key as ColumnKey].label} right`}>↓</button>
        <button type="button" onClick={() => { setColumnPinning((current) => ({ left: current.left?.includes(key) ? current.left.filter((item) => item !== key) : [...(current.left ?? []), key], right: [] })); setView("Custom"); }} aria-label={`${columnPinning.left?.includes(key) ? "Unpin" : "Pin"} ${columnByKey[key as ColumnKey].label}`}>{columnPinning.left?.includes(key) ? "●" : "○"}</button>
      </div>)}</div><button type="button" onClick={() => { chooseView(view === "Custom" ? "Overview" : view); setColumnOpen(false); }}>Reset to view default</button>
    </div>}
    {saveMode && <div className="screener-modal-backdrop"><div className="screener-save-dialog" role="dialog" aria-modal="true" aria-label="Save screen" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); closeTransient(); } }}>
      <h2>{saveMode === "rename" ? "Rename Screen" : saveMode === "save-as" ? "Save As" : "Save Screen"}</h2>
      <label>Screen name <input autoFocus aria-label="Screen name" value={saveName} onChange={(event) => setSaveName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void saveCurrent(); }} /></label>
      {configError && <p role="alert">{configError}</p>}
      <div className="screener-popover-actions"><button type="button" onClick={closeTransient}>Cancel</button><button type="button" className="screener-primary" disabled={!saveName.trim()} onClick={() => void saveCurrent()}>Save</button></div>
      {selectedSaved && saveMode === "save" && <button type="button" onClick={() => { setSaveName(""); setSaveMode("save-as"); }}>Save As</button>}
    </div></div>}
    <div className="screener-body" ref={bodyRef}>
    {intel ? <ScreenerErrorBoundary label={`The ${INTEL_LABELS[intel]} view`} resetKey={`${universe}|${intel}`}><Suspense fallback={<div className="screener-message" role="status">Loading {INTEL_LABELS[intel].toLowerCase()} view…</div>}>
      <IntelligenceView universe={universe} universeLabel={activeSpec?.label ?? UNIVERSE_LABELS[universe]} view={intel} search={location.search} onUpdate={(updates) => urlUpdate(updates)} />
    </Suspense></ScreenerErrorBoundary> : newsMode ? <ScreenerErrorBoundary label="The News view" resetKey={universe}><Suspense fallback={<div className="screener-message" role="status">Loading news view…</div>}>
      <NewsView universe={universe} universeLabel={activeSpec?.label ?? UNIVERSE_LABELS[universe]} search={location.search} onUpdate={(updates) => urlUpdate(updates)} />
    </Suspense></ScreenerErrorBoundary> :
    <div className="screener-grid" role="grid" aria-label={universe === "US_EQUITIES" ? "US equity screener" : `${activeSpec?.label ?? universe} screener`} aria-rowcount={(resultCount ?? rows.length) + 1} aria-busy={query.isFetching} tabIndex={0}
      onKeyDown={onGridKeyDown} ref={scrollRef}>
      <div className="screener-header" role="row" style={{ width: table.getTotalSize() }}>
        {table.getHeaderGroups()[0]?.headers.map((header) => {
          const key = header.id as ColumnKey;
          const pinned = header.column.getIsPinned() === "left";
          return <button type="button" role="columnheader" key={header.id}
            className={leftAligned.has(key) ? "screener-heading screener-left" : "screener-heading"}
            style={{ width: header.getSize(), ...(pinned ? { position: "sticky", left: header.column.getStart("left"), zIndex: 4, background: "#1b2530" } : {}) }}
            aria-sort={isSortable(key) ? effectiveSort === key ? descending ? "descending" : "ascending" : "none" : undefined}
            aria-disabled={isSortable(key) ? undefined : true}
            title={isSortable(key) ? undefined : fieldCaps?.[key]?.execution === "LIVE_WINDOW"
              ? "Current quotes for visible rows only; not sortable across the universe" : "Not sortable"}
            onClick={() => { if (availableKeys.includes(key) && isSortable(key)) sortBy(key as SortKey); }}>
            {flexRender(header.column.columnDef.header, header.getContext())}
            <span className="screener-sort">{effectiveSort === key ? descending ? "▼" : "▲" : ""}</span>
            <span className="screener-resize" role="separator" tabIndex={0} aria-orientation="vertical" aria-valuenow={header.getSize()} aria-label={`Resize ${typeof header.column.columnDef.header === "string" ? header.column.columnDef.header : columnByKey[key].label}`}
              onKeyDown={(event) => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); event.stopPropagation(); const width = Math.max(50, header.getSize() + (event.key === "ArrowRight" ? 10 : -10)); setColumnSizing((current) => ({ ...current, [key]: width })); setView("Custom"); } }}
              onMouseDown={(event) => { event.stopPropagation(); header.getResizeHandler()(event); }} onTouchStart={header.getResizeHandler()} /></button>;
        })}
      </div>
      {query.isPending ? <div className="screener-message">{snapshotQuery
        ? `Evaluating the current ${activeSpec?.label ?? "universe"} market snapshot…`
        : `Loading current ${activeSpec?.label ?? "US equity"} universe…`}</div> :
        (query.isError && !query.data) || firstPage?.source_error ? <div className="screener-message screener-message-error" role="alert">
          <strong>{firstPage?.source_error?.startsWith("MARKET_SNAPSHOT") || (snapshotQuery && firstPage?.source_error) ? "Market snapshot unavailable" : "Screener source unavailable"}</strong>
          <span>{firstPage?.source_error === "NOT_CONFIGURED"
            ? "Finviz access is not configured for this workstation."
            : firstPage?.source_error === "TREASURY_NOT_CONFIGURED"
              ? "U.S. Treasury Fiscal Data is not enabled for this workstation (set IMP_TREASURY_LIVE=1)."
            : firstPage?.source_error === "CRYPTO_NOT_CONFIGURED"
              ? "Kraken public market data is not enabled for this workstation (set IMP_CRYPTO_LIVE=1)."
            : firstPage?.source_error === "CLASSIFICATION_UNAVAILABLE"
              ? "ETF membership cannot be verified: the Finviz classification that separates ETFs from REITs and closed-end funds is unavailable."
            : snapshotQuery && firstPage?.source_error
              ? `A complete ${activeSpec?.label ?? "universe"} market snapshot could not be taken, so market filters and sorts cannot be evaluated across the universe. Remove them to browse the catalog.`
              : `The current ${activeSpec?.label ?? "universe"} source could not be refreshed.`}</span>
          <button onClick={() => { forceNextRefresh.current = true; void query.refetch(); }}>Retry source</button>
        </div> :
        rows.length === 0 ? <div className="screener-message">No instruments match {filters.length ? "these filters or this search" : "this search"}.</div> :
        <div className="screener-virtual" style={{ height: virtualizer.getTotalSize(), width: table.getTotalSize() }}>
          {virtualRows.map((virtual) => {
            if (virtual.index === rows.length) {
              return <div role="row" key="screener-more" aria-rowindex={virtual.index + 2} className="screener-row screener-more-row"
                style={{ transform: `translateY(${virtual.start}px)`, width: table.getTotalSize() }}>
                <div role="gridcell" className="screener-cell screener-left screener-more">{query.isFetchNextPageError && !resultSetChanged(query.error)
                  ? <>Could not load more results <button type="button" onClick={() => void query.fetchNextPage()}>Retry</button></>
                  : <span role="status">Loading more results…</span>}</div>
              </div>;
            }
            const row = table.getRowModel().rows[virtual.index];
            if (!row) return null;
            return <div role="row" key={row.id} aria-rowindex={virtual.index + 2} aria-selected={row.id === selected}
              className={`screener-row${row.id === selected ? " selected" : ""}`}
              style={{ transform: `translateY(${virtual.start}px)`, width: table.getTotalSize() }}
              onClick={() => {
                if (row.id === selected) { open(row.original); return; }
                setSelected(row.id);
                if (!previewOpen) { setPreviewOpen(true); persistLayout(true, previewWidth); }
              }}
              onDoubleClick={() => open(row.original)}>
              {row.getVisibleCells().map((cell) => <div role="gridcell" key={cell.id}
                className={leftAligned.has(cell.column.id) ? "screener-cell screener-left" : "screener-cell"}
                style={{ width: cell.column.getSize(), ...(cell.column.getIsPinned() === "left" ? { position: "sticky", left: cell.column.getStart("left"), zIndex: 1, background: row.id === selected ? "#1c3652" : "#111820" } : {}) }}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</div>)}
            </div>;
          })}
        </div>}
    </div>}
    {previewOpen && !narrow && <div className="screener-splitter" role="separator" aria-orientation="vertical" aria-label="Resize quick preview"
      aria-valuemin={PREVIEW_MIN} aria-valuemax={PREVIEW_MAX} aria-valuenow={previewWidth} tabIndex={0}
      onPointerDown={onSplitterPointerDown} onKeyDown={onSplitterKeyDown} />}
    {previewOpen && (!narrow || selectedRow) && <QuickPreview row={selectedRow} quote={selected ? quotes[selected] : undefined} filters={filters} universe={universe}
      screenLabel={selectedScreenId ? `${selectedName}${changed ? " (modified)" : ""}` : null} overlay={narrow} width={previewWidth}
      paneRef={previewRef} onClose={closePreview} onOpen={open}
      optionsSupported={supportedPanels.has("options")} onOpenOptions={openOptionsPanel}
      ratesSupported={supportedPanels.has("rates_curve")} onOpenRates={openRatesPanel}
      squeezeSupported={universe === "US_EQUITIES" && supportedPanels.has("short_squeeze")} onOpenSqueeze={openSqueezePanel}
      newsSupported={supportedPanels.has("news")} onOpenNews={openNewsPanel}
      institutionalSupported={supportedPanels.has("institutional")} governmentSupported={supportedPanels.has("congress_gov")}
      onOpenParticipants={openParticipantPanel} />}
    </div>
    {dockVisible && <>
      <div className="screener-dock-splitter" role="separator" aria-orientation="horizontal" aria-label="Resize specialist panels"
        aria-valuemin={140} aria-valuemax={1200} aria-valuenow={dockHeight} tabIndex={0}
        onPointerDown={onDockSplitterPointerDown} onKeyDown={onDockSplitterKeyDown} />
      <section className="screener-dock" aria-label="Specialist panels" ref={dockRef} style={{ height: dockHeight }}>
        {/* The dock as a whole is contained too: a failure outside any one panel (e.g. a saved arrangement
            the dock cannot restore) never blanks the table, and the layout can be reset from here. */}
        <ScreenerErrorBoundary label="Specialist panels" resetKey={`${universe}|${dockGeneration}`}
          actions={<> <button type="button" onClick={resetDockAfterError}>Reset layout</button></>}>
          <Suspense fallback={<div className="screener-dock-loading" role="status">Loading panels…</div>}>
            <ScreenerDock key={`${universe}|${dockGeneration}`} layout={panelLayout.current} row={selectedRow} quote={selected ? quotes[selected] : undefined} filters={filters} universe={universe} supportedPanels={supportedPanels}
              clientId={clientId.current} pending={pendingPanel} handleRef={dockHandle}
              onOpenChange={(ids) => { onOpenPanels(ids); if (pendingPanel) setPendingPanel(null); }} onLayout={onPanelLayout} />
          </Suspense>
        </ScreenerErrorBoundary>
      </section>
    </>}
    <PanelLauncher open={openPanels} supported={supportedPanels} onLaunch={launchPanel} onReset={resetPanels} resetDisabled={!openPanels.length && dockHeight === DOCK_HEIGHT_DEFAULT} />
    <footer className="screener-footer"><span>{resultCount?.toLocaleString() ?? "—"}{filters.length && resultCount !== null && firstPage?.unfiltered_count !== undefined ? ` of ${firstPage.unfiltered_count.toLocaleString()}` : ""} results{resultCount !== null && rows.length < resultCount ? ` · ${rows.length.toLocaleString()} loaded` : ""}</span>
      {truncated && <span className="screener-truncated" role="status">{truncated}</span>}
      {firstPage?.snapshot && <span title={`${firstPage.snapshot.priced.toLocaleString()} priced · ${firstPage.snapshot.refused.toLocaleString()} without an entitled quote · filters and order use this snapshot; visible rows stream current quotes`}>Market snapshot {clock(firstPage.snapshot.as_of, universe)} (<Age iso={firstPage.snapshot.as_of} staleMs={300_000} /> ago) · {firstPage.snapshot.priced.toLocaleString()} of {firstPage.snapshot.total.toLocaleString()} priced</span>}
      {firstPage?.coverage && <span title="Categories without a permitted source are reported, never counted">{Object.entries(firstPage.coverage).sort(([a], [b]) => coverageRank(a) - coverageRank(b)).map(([category, item]) =>
        `${category.charAt(0) + category.slice(1).toLowerCase()} ${item.count != null ? item.count.toLocaleString() : "unavailable"}`).join(" · ")}</span>}
      <span>Quotes {!streamingQuotes ? "none · publication data" : universe === "FUTURES" && quoteLabel === "unavailable" && quoteReasons.includes("MOOMOO_QUOTE_NOT_ENTITLED") ? "unavailable · entitlement required" : quoteLabel}</span>
      <span>Market {session}</span>
      <span>Universe {firstPage?.universe_as_of ? <>as of {clock(firstPage.universe_as_of, universe)} (<Age iso={firstPage.universe_as_of} /> ago)</> : "unavailable"}</span>
      <span>Source {firstPage?.provider_health[0]?.state.toLowerCase() ?? "checking"} · {activeSpec?.source ?? "Finviz"}</span></footer>
  </section>;
}
