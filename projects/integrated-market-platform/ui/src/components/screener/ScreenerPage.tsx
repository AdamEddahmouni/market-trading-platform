import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { ColumnPinningState, ColumnSizingState, VisibilityState } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useLocation, useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import { deleteScreenerScreen, fetchScreener, fetchScreenerConfig, persistLastScreenerConfig, persistScreenerPreviewLayout, releaseScreenerWindow, releaseScreenerWindowOnUnload, saveScreenerScreen, updateScreenerWindow, type ScreenerFilter, type ScreenerField, type ScreenerQuote, type ScreenerRow, type ScreenerScreen } from "../../api/screener";
import { QuickPreview } from "./QuickPreview";
import "./screener.css";

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

type ColumnKey = "symbol" | "company" | "sector" | "industry" | "country" | "price" | "change_pct" | "volume" | "avg_volume" | "rel_volume" | "float_shares" | "shares_outstanding" | "market_cap" | "short_float_pct" | "short_ratio" | "rsi_14" | "eps_ttm" | "pe" | "fwd_pe" | "perf_week" | "earnings_date" | "recommendation" | "bid" | "ask" | "spread_pct";
type SortKey = Exclude<ColumnKey, "sector" | "industry" | "country" | "earnings_date" | "recommendation" | "bid" | "ask" | "spread_pct"> | "bid" | "ask" | "spread_pct";
type ColumnDefinition = { key: ColumnKey; label: string; width: number; format: "text" | "price" | "percent" | "compact" | "decimal" };
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
  { key: "short_float_pct", label: "Short %", width: 87, format: "percent" },
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
];
const columnByKey = Object.fromEntries(definitions.map((item) => [item.key, item])) as Record<ColumnKey, ColumnDefinition>;
const leftAligned = new Set<string>(["symbol", "company", "sector", "industry", "country"]);
const views: Record<string, ColumnKey[]> = {
  Overview: ["symbol", "price", "change_pct", "volume", "rel_volume", "float_shares", "market_cap", "short_float_pct", "bid", "ask", "spread_pct", "rsi_14"],
  Performance: ["symbol", "price", "change_pct", "perf_week", "volume", "rel_volume", "rsi_14", "market_cap"],
  Technical: ["symbol", "price", "change_pct", "rsi_14", "perf_week", "volume", "rel_volume"],
  Volume: ["symbol", "price", "volume", "avg_volume", "rel_volume", "float_shares", "change_pct"],
  Short: ["symbol", "price", "change_pct", "float_shares", "short_float_pct", "short_ratio", "rel_volume", "volume"],
  Fundamentals: ["symbol", "company", "sector", "industry", "market_cap", "eps_ttm", "pe", "fwd_pe", "earnings_date", "recommendation"],
  Custom: ["symbol", "price", "change_pct", "volume"],
};
const allKeys = definitions.map((item) => item.key);
const sortKeys = new Set(allKeys.filter((key) => !["sector", "industry", "country", "earnings_date", "recommendation"].includes(key)));
const sortFromUrl = (value: string | null): SortKey | null => value && sortKeys.has(value as ColumnKey) ? value as SortKey : null;
const viewVisibility = (view: string): VisibilityState => Object.fromEntries(allKeys.map((key) => [key, (views[view] ?? views.Overview).includes(key)]));
const snapshotOf = (screen: ScreenerScreen) => ({ filters: screen.filters, view: screen.view,
  sort: screen.sort, columns: screen.columns });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const quoteKeys = new Set(["price", "volume", "bid", "ask", "spread_pct"]);
const sourceSort = (key: SortKey) => ["bid", "ask", "spread_pct"].includes(key) ? "volume" : key;
function fieldFor(row: ScreenerRow, key: ColumnKey, quote?: ScreenerQuote) {
  const current = quote?.fields[key];
  if (quoteKeys.has(key) && current?.state === "LIVE" && current.value !== null) return current;
  return row.fields[key];
}
function valueText(field: ScreenerField | undefined, format: (typeof definitions)[number]["format"], signed = false) {
  if (!field || field.value === null) return "—";
  if (format === "price") return field.value.toFixed(2);
  if (format === "percent") return `${signed && field.value > 0 ? "+" : ""}${field.value.toFixed(2)}%`;
  return format === "compact" ? compact.format(field.value) : decimal.format(field.value);
}
const helper = createColumnHelper<ScreenerRow>();

export function ScreenerPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const initialParams = useMemo(() => new URLSearchParams(location.search), []);
  const [search, setSearch] = useState(initialParams.get("q") ?? "");
  const [sort, setSort] = useState<SortKey>(sortFromUrl(initialParams.get("sort")) ?? "volume");
  const [descending, setDescending] = useState(initialParams.get("dir") !== "asc");
  const [view, setView] = useState(initialParams.get("view") && views[initialParams.get("view")!] ? initialParams.get("view")! : "Overview");
  const [filters, setFilters] = useState<ScreenerFilter[]>([]);
  const [selectedScreenId, setSelectedScreenId] = useState(initialParams.get("screen") ?? "");
  const [savedBase, setSavedBase] = useState("");
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(() => viewVisibility("Overview"));
  const [columnOrder, setColumnOrder] = useState<string[]>(allKeys);
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
  const [restored, setRestored] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [quotes, setQuotes] = useState<Record<string, ScreenerQuote>>({});
  const [quoteError, setQuoteError] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const clientId = useRef(crypto.randomUUID().replace(/-/g, ""));
  const quoteQueue = useRef<Promise<void>>(Promise.resolve());
  const forceNextRefresh = useRef(false);
  const transientTrigger = useRef<HTMLElement | null>(null);
  const initialized = useRef(false);
  const loadedScreen = useRef<string | null>(null);
  const config = useQuery({ queryKey: ["main-screener-config"], queryFn: fetchScreenerConfig, staleTime: 60_000 });
  const narrow = useNarrow();
  const [previewOpen, setPreviewOpen] = useState(true);
  const [previewWidth, setPreviewWidth] = useState(400);
  const bodyRef = useRef<HTMLDivElement>(null);
  const previewRef = useRef<HTMLElement>(null);
  const layoutRestored = useRef(false);
  const layoutTimer = useRef<number | undefined>(undefined);
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
    setSearch(params.get("q") ?? "");
    setSelectedScreenId(params.get("screen") ?? "");
    const key = params.get("sort");
    const urlSort = sortFromUrl(key);
    if (urlSort) setSort(urlSort);
    setDescending(params.get("dir") !== "asc");
    const nextView = params.get("view");
    if (nextView && views[nextView] && nextView !== view) {
      setView(nextView);
      setColumnVisibility(viewVisibility(nextView));
    }
  }, [location.search]);
  useEffect(() => {
    if (!config.data) return;
    const params = new URLSearchParams(location.search);
    const id = selectedScreenId;
    const saved = config.data.saved.find((item) => item.id === id);
    const preset = config.data.presets.find((item) => item.id === id && item.status === "SUPPORTED");
    if (id && loadedScreen.current !== id && (saved || preset)) {
      const source = saved ?? { filters: preset!.filters, view: "Overview", sort: { field: "volume", descending: true },
        columns: { visible: views.Overview, order: allKeys, widths: {}, pinned: ["symbol"] } };
      setFilters(source.filters);
      const nextView = params.get("view") && views[params.get("view")!] ? params.get("view")! : source.view;
      setView(nextView);
      setSort(sortFromUrl(params.get("sort")) ?? source.sort.field as SortKey);
      setDescending(params.has("dir") ? params.get("dir") !== "asc" : source.sort.descending);
      setColumnVisibility(Object.fromEntries(allKeys.map((key) => [key, source.columns.visible.includes(key)])));
      setColumnOrder(source.columns.order); setColumnSizing(source.columns.widths);
      setColumnPinning({ left: source.columns.pinned, right: [] });
      setSavedBase(JSON.stringify(snapshotOf(source as ScreenerScreen)));
      loadedScreen.current = id;
    } else if (!id && (!initialized.current || loadedScreen.current !== null) && config.data.last) {
      const last = config.data.last;
      setFilters(last.filters);
      const nextView = params.get("view") && views[params.get("view")!] ? params.get("view")! : last.view;
      setView(nextView); setSort(sortFromUrl(params.get("sort")) ?? last.sort.field as SortKey);
      setDescending(params.has("dir") ? params.get("dir") !== "asc" : last.sort.descending);
      setColumnVisibility(Object.fromEntries(allKeys.map((key) => [key, last.columns.visible.includes(key)])));
      setColumnOrder(last.columns.order); setColumnSizing(last.columns.widths);
      setColumnPinning({ left: last.columns.pinned, right: [] });
      setSavedBase("");
      loadedScreen.current = null;
    } else if (!id && loadedScreen.current !== null) {
      setFilters([]); setView("Overview"); setSort("volume"); setDescending(true);
      setColumnVisibility(viewVisibility("Overview")); setColumnOrder(allKeys);
      setColumnSizing({}); setColumnPinning({ left: ["symbol"], right: [] });
      setSavedBase(""); loadedScreen.current = null;
    }
    initialized.current = true; setRestored(true);
  }, [config.data, selectedScreenId]);
  const query = useQuery({
    queryKey: ["main-screener", search, sourceSort(sort), descending, filters],
    queryFn: () => {
      const force = forceNextRefresh.current;
      forceNextRefresh.current = false;
      return filters.length ? fetchScreener(search, sourceSort(sort), descending, force, filters)
        : force ? fetchScreener(search, sourceSort(sort), descending, true)
          : fetchScreener(search, sourceSort(sort), descending);
    },
    staleTime: 30_000, refetchInterval: 120_000,
  });
  const rows = useMemo(() => {
    const source = query.data?.rows ?? [];
    if (!["bid", "ask", "spread_pct"].includes(sort)) return source;
    return [...source].sort((a, b) => {
      const av = fieldFor(a, sort, quotes[a.instrument.instrument_id])?.value;
      const bv = fieldFor(b, sort, quotes[b.instrument.instrument_id])?.value;
      if (av == null) return bv == null ? a.symbol.localeCompare(b.symbol) : 1;
      if (bv == null) return -1;
      return (descending ? bv - av : av - bv) || a.symbol.localeCompare(b.symbol);
    });
  }, [query.data?.rows, sort, descending, quotes]);
  const columns = useMemo(() => definitions.map((definition) => helper.display({
    id: definition.key, header: definition.label, size: definition.width,
    cell: ({ row }) => {
      const item = row.original;
      if (definition.key === "symbol") return <span className="screener-symbol"><strong>{item.symbol}</strong><small>{item.company}</small></span>;
      if (["company", "sector", "industry", "country", "earnings_date", "recommendation"].includes(definition.key)) {
        const value = item[definition.key as "company" | "sector" | "industry" | "country" | "earnings_date" | "recommendation"];
        return <span title={value ?? "Unavailable"}>{value || "—"}</span>;
      }
      const field = fieldFor(item, definition.key, quotes[item.instrument.instrument_id]);
      const tone = definition.key === "change_pct" && field?.value != null
        ? field.value > 0 ? "screener-positive" : field.value < 0 ? "screener-negative" : "" : "";
      return <span className={tone} title={field ? `${field.source} · ${field.state}` : "Unavailable"}>{valueText(field, definition.format, definition.key === "change_pct")}</span>;
    },
  })), [quotes]);
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel(), getRowId: (row) => row.instrument.instrument_id,
    state: { columnVisibility, columnOrder, columnSizing, columnPinning },
    onColumnVisibilityChange: setColumnVisibility, onColumnOrderChange: setColumnOrder,
    onColumnSizingChange: setColumnSizing, onColumnPinningChange: setColumnPinning,
    columnResizeMode: "onChange" });
  const virtualizer = useVirtualizer({ count: rows.length, getScrollElement: () => scrollRef.current, estimateSize: () => 34, overscan: 5 });
  const virtualRows = virtualizer.getVirtualItems();
  const indices = virtualRows.map((item) => item.index).join(",");
  const visible = useMemo(() => {
    const ids = virtualRows.slice(0, 26).map((item) => rows[item.index]?.instrument.instrument_id).filter((id): id is string => Boolean(id));
    if (selected && rows.some((row) => row.instrument.instrument_id === selected)) ids.unshift(selected);
    return [...new Set(ids)].slice(0, 32);
  }, [indices, rows, selected]);
  const windowKey = visible.join(",");
  useEffect(() => {
    if (!windowKey) return;
    let cancelled = false;
    const refresh = () => {
      quoteQueue.current = quoteQueue.current.then(async () => {
        if (cancelled) return;
        try {
          const payload = await updateScreenerWindow(clientId.current, visible);
          if (!cancelled) { setQuotes(payload.quotes); setQuoteError(false); }
        } catch {
          if (!cancelled) { setQuotes({}); setQuoteError(true); }
        }
      });
    };
    refresh();
    const timer = window.setInterval(refresh, 3_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [windowKey]);
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
  // the preview never shows an instrument the table no longer lists.
  useEffect(() => {
    if (selected && query.isSuccess && !query.isFetching && !rows.some((row) => row.instrument.instrument_id === selected)) setSelected(null);
  }, [rows, selected, query.isSuccess, query.isFetching]);
  const selectedIndex = rows.findIndex((row) => row.instrument.instrument_id === selected);
  const selectedRow = selectedIndex >= 0 ? rows[selectedIndex] : null;
  const activate = (index: number) => {
    const row = rows[index];
    if (!row) return;
    setSelected(row.instrument.instrument_id);
    virtualizer.scrollToIndex(index, { align: "auto" });
  };
  const open = useCallback((row: ScreenerRow) => navigate(workspacePathForInstrument(row.instrument.instrument_id)), [navigate]);
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
      setColumnVisibility(viewVisibility(next));
      setColumnOrder([...views[next], ...allKeys.filter((key) => !views[next].includes(key))]);
      setColumnSizing({}); setColumnPinning({ left: ["symbol"], right: [] });
    }
    urlUpdate({ view: next });
  };
  const beginFilter = (field: string, existing?: ScreenerFilter) => {
    const definition = config.data?.catalog.find((item) => item.field === field);
    if (!definition) return;
    setDraftField(field);
    setDraftOperator(existing?.operator ?? definition.operators[0]);
    setDraftValue(existing ? String(Array.isArray(existing.value) ? existing.value[0] : existing.value) : "");
    setDraftSecond(existing && Array.isArray(existing.value) ? String(existing.value[1]) : "");
    setEditFilterId(existing?.id ?? null);
  };
  const applyFilter = () => {
    const definition = config.data?.catalog.find((item) => item.field === draftField);
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
    columns: { visible: allKeys.filter((key) => columnVisibility[key] !== false), order: columnOrder,
      widths: columnSizing, pinned: columnPinning.left ?? [] } });
  const lastSerialized = JSON.stringify(currentSnapshot());
  useEffect(() => {
    if (!restored || !config.data?.persistence_available) return;
    const timer = window.setTimeout(() => {
      const snapshot = JSON.parse(lastSerialized) as ReturnType<typeof currentSnapshot>;
      void persistLastScreenerConfig({ name: "Last Used", universe: "US_EQUITIES", ...snapshot }).catch(() => undefined);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [lastSerialized, restored, config.data?.persistence_available]);
  const changed = Boolean(selectedScreenId && savedBase && savedBase !== JSON.stringify(currentSnapshot()));
  const selectedSaved = config.data?.saved.find((item) => item.id === selectedScreenId);
  const selectedPreset = config.data?.presets.find((item) => item.id === selectedScreenId);
  const selectedName = selectedSaved?.name ?? selectedPreset?.name ?? "Unsaved Screen";
  const saveCurrent = async () => {
    const name = saveName.trim();
    if (!name) return;
    try {
      const screen = { ...(saveMode === "save" || saveMode === "rename" ? { id: selectedSaved?.id, version: 1 } : {}),
        name, universe: "US_EQUITIES" as const, ...currentSnapshot() };
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
    const definition = config.data?.catalog.find((item) => item.field === rule.field);
    const operator = { eq: "=", ne: "≠", gt: ">", gte: "≥", lt: "<", lte: "≤", between: "", in: "in", not_in: "not in", contains: "contains" }[rule.operator] ?? rule.operator;
    const value = Array.isArray(rule.value) ? rule.value.join(rule.operator === "between" ? "–" : ", ") : String(rule.value);
    return `${definition?.label ?? rule.field} ${operator} ${definition?.unit === "USD" ? "$" : ""}${value}${definition?.unit === "percent" ? "%" : ""}`.replace(/\s+/g, " ").trim();
  };
  const session = query.data?.market_session.replace("_", " ").toLowerCase() ?? "—";
  const quoteStates = Object.values(quotes).map((quote) => quote.state);
  const quoteLabel = quoteError ? "unavailable" :
    quoteStates.includes("LIVE") ? "live for visible rows" :
    quoteStates.includes("DELAYED") ? "delayed" :
    quoteStates.includes("STALE") ? "stale" : "unavailable";
  return <section className="screener-page" aria-label="Screener">
    <header className="screener-topline"><div className="screener-brand"><Link to="/" aria-label="IMP home">IMP</Link><span className="screener-brand-divider" /><h1>Screener</h1></div>
      <label className="screener-search"><span className="sr-only">Search instruments</span>
        <input ref={searchRef} value={search} onChange={(event) => { setSearch(event.target.value); urlUpdate({ q: event.target.value || null }, true); }}
          onKeyDown={(event) => { if (event.key === "Escape") { setSearch(""); urlUpdate({ q: null }, true); event.currentTarget.blur(); } }}
          placeholder="Search symbol or company  /" /></label><span className="screener-market-badge">{query.data?.market_session ?? "MARKET"}</span></header>
    <div className="screener-toolbar"><span>Universe <strong>US Equities</strong></span><span>Session <strong>{session}</strong></span>
      <div className="screener-toolbar-end"><button type="button" className="screener-control" onClick={(event) => { transientTrigger.current = event.currentTarget; setScreenOpen(!screenOpen); setColumnOpen(false); setFilterOpen(false); }} aria-expanded={screenOpen} aria-haspopup="dialog">{selectedName}{changed ? " *" : ""} ▾</button>
        <button type="button" className="screener-control screener-primary" disabled={!config.data?.persistence_available} onClick={(event) => { transientTrigger.current = event.currentTarget; setSaveName(selectedSaved?.name ?? ""); setSaveMode(selectedSaved ? "save" : "save-as"); }}>Save</button>
        <button type="button" className="screener-control" onClick={(event) => { transientTrigger.current = event.currentTarget; setColumnOpen(!columnOpen); setFilterOpen(false); setScreenOpen(false); }} aria-expanded={columnOpen} aria-haspopup="dialog">Columns</button>
        <button type="button" className="screener-control" aria-pressed={previewOpen} onClick={togglePreview}>Preview</button></div></div>
    <div className="screener-tabs" role="tablist" aria-label="Screener views">{Object.keys(views).map((name) => <button key={name} type="button" role="tab" aria-selected={view === name} onClick={() => chooseView(name)}>{name}</button>)}</div>
    <div className="screener-filters" aria-label="Active filters">{filters.map((rule) => <span className="screener-chip" key={rule.id}>
      <button type="button" onClick={(event) => { transientTrigger.current = event.currentTarget; beginFilter(rule.field, rule); setFilterOpen(true); }} aria-label={`Edit ${config.data?.catalog.find((item) => item.field === rule.field)?.label ?? rule.field}`}>{labelFilter(rule)}</button>
      <button type="button" onClick={() => setFilters((current) => current.filter((item) => item.id !== rule.id))} aria-label={`Remove ${config.data?.catalog.find((item) => item.field === rule.field)?.label ?? rule.field}`}>×</button></span>)}
      <button type="button" className="screener-add" onClick={(event) => { transientTrigger.current = event.currentTarget; setFilterOpen(!filterOpen); setColumnOpen(false); setScreenOpen(false); setDraftField(""); setFilterSearch(""); }} aria-expanded={filterOpen} aria-haspopup="dialog">+ Add Filter</button>
      {filters.length > 0 && <button type="button" className="screener-clear" onClick={() => setFilters([])}>Clear All</button>}
    </div>
    {filterOpen && <div className="screener-popover screener-filter-popover" role="dialog" aria-label={draftField ? "Edit filter" : "Add filter"} onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); closeTransient(); } }}>
      <button type="button" className="screener-popover-close" onClick={closeTransient} aria-label="Close filter picker">×</button>
      {!draftField ? <><input autoFocus aria-label="Search filters" placeholder="Search filters..." value={filterSearch} onChange={(event) => setFilterSearch(event.target.value)} />
        <div className="screener-picker-list">{[...new Set(config.data?.catalog.map((item) => item.category) ?? [])].map((category) => <div key={category}><h3>{category}</h3>{config.data?.catalog.filter((item) => item.category === category && item.label.toLowerCase().includes(filterSearch.toLowerCase())).map((item) => <button key={item.field} type="button" onClick={() => beginFilter(item.field)}>{item.label}</button>)}</div>)}</div></> : <>
        <h3>{config.data?.catalog.find((item) => item.field === draftField)?.label}</h3>
        <label>Operator <select aria-label="Filter operator" value={draftOperator} onChange={(event) => setDraftOperator(event.target.value)}>{config.data?.catalog.find((item) => item.field === draftField)?.operators.map((operator) => <option key={operator} value={operator}>{({ eq: "Equals", ne: "Not equals", gt: "Greater than", gte: "At least", lt: "Less than", lte: "At most", between: "Between", in: "In", not_in: "Not in", contains: "Contains" } as Record<string, string>)[operator]}</option>)}</select></label>
        <label>Value <input autoFocus aria-label="Filter value" type={config.data?.catalog.find((item) => item.field === draftField)?.type === "number" ? "number" : "text"} value={draftValue} onChange={(event) => setDraftValue(event.target.value)} /></label>
        {draftOperator === "between" && <label>Maximum <input aria-label="Filter maximum" type="number" value={draftSecond} onChange={(event) => setDraftSecond(event.target.value)} /></label>}
        <div className="screener-popover-actions"><button type="button" onClick={() => setDraftField("")}>Back</button><button type="button" className="screener-primary" onClick={applyFilter} disabled={!draftValue.trim() || (draftOperator === "between" && !draftSecond.trim())}>Apply Filter</button></div></>}
    </div>}
    {screenOpen && <div className="screener-popover screener-screen-popover" role="dialog" aria-label="Saved screens" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); closeTransient(); } }}>
      <button type="button" className="screener-popover-close" onClick={closeTransient} aria-label="Close saved screens">×</button>
      <h3>My Screens</h3>{config.data?.saved.length ? config.data.saved.map((item) => <button key={item.id} type="button" onClick={() => { loadedScreen.current = null; setSelectedScreenId(item.id); urlUpdate({ screen: item.id, view: null, sort: null, dir: null }); setScreenOpen(false); }}>{item.name}</button>) : <span className="screener-popover-note">No personal screens</span>}
      <h3>Built-in</h3>{config.data?.presets.map((item) => <button key={item.id} type="button" disabled={item.status !== "SUPPORTED"} title={item.reason ?? undefined} onClick={() => { loadedScreen.current = null; setSelectedScreenId(item.id); urlUpdate({ screen: item.id, view: null, sort: null, dir: null }); setScreenOpen(false); }}>{item.name}{item.status !== "SUPPORTED" ? " · unavailable" : ""}</button>)}
      {selectedSaved && <div className="screener-popover-actions"><button type="button" onClick={() => { setSaveName(selectedSaved.name); setSaveMode("rename"); setScreenOpen(false); }}>Rename</button><button type="button" onClick={() => { void removeSaved(); }}>Delete</button></div>}
      {selectedPreset && changed && <button type="button" onClick={() => { setFilters(selectedPreset.filters); setView("Overview"); setColumnVisibility(viewVisibility("Overview")); setScreenOpen(false); }}>Reset preset</button>}
    </div>}
    {columnOpen && <div className="screener-popover screener-column-popover" role="dialog" aria-label="Configure columns" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); closeTransient(); } }}>
      <button type="button" className="screener-popover-close" onClick={closeTransient} aria-label="Close columns">×</button>
      <input autoFocus aria-label="Search columns" placeholder="Search columns..." value={columnSearch} onChange={(event) => setColumnSearch(event.target.value)} />
      <div className="screener-column-list">{columnOrder.filter((key) => columnByKey[key as ColumnKey]?.label.toLowerCase().includes(columnSearch.toLowerCase())).map((key) => <div className="screener-column-item" key={key}>
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
    <div className="screener-grid" role="grid" aria-label="US equity screener" aria-rowcount={rows.length + 1} tabIndex={0}
      onKeyDown={onGridKeyDown} ref={scrollRef}>
      <div className="screener-header" role="row" style={{ width: table.getTotalSize() }}>
        {table.getHeaderGroups()[0]?.headers.map((header) => {
          const key = header.id as ColumnKey;
          const pinned = header.column.getIsPinned() === "left";
          return <button type="button" role="columnheader" key={header.id}
            className={leftAligned.has(key) ? "screener-heading screener-left" : "screener-heading"}
            style={{ width: header.getSize(), ...(pinned ? { position: "sticky", left: header.column.getStart("left"), zIndex: 4, background: "#1b2530" } : {}) }}
            aria-sort={sort === key ? descending ? "descending" : "ascending" : "none"}
            onClick={() => { if (!["sector", "industry", "country", "earnings_date", "recommendation"].includes(key)) sortBy(key as SortKey); }}>
            {flexRender(header.column.columnDef.header, header.getContext())}
            <span className="screener-sort">{sort === key ? descending ? "▼" : "▲" : ""}</span>
            <span className="screener-resize" role="separator" tabIndex={0} aria-orientation="vertical" aria-valuenow={header.getSize()} aria-label={`Resize ${columnByKey[key].label}`}
              onKeyDown={(event) => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); event.stopPropagation(); const width = Math.max(50, header.getSize() + (event.key === "ArrowRight" ? 10 : -10)); setColumnSizing((current) => ({ ...current, [key]: width })); setView("Custom"); } }}
              onMouseDown={(event) => { event.stopPropagation(); header.getResizeHandler()(event); }} onTouchStart={header.getResizeHandler()} /></button>;
        })}
      </div>
      {query.isPending ? <div className="screener-message">Loading current US equity universe…</div> :
        query.isError || query.data?.source_error ? <div className="screener-message screener-message-error" role="alert">
          <strong>Screener source unavailable</strong>
          <span>{query.data?.source_error === "NOT_CONFIGURED"
            ? "Finviz access is not configured for this workstation."
            : "The current US equity universe could not be refreshed."}</span>
          <button onClick={() => { forceNextRefresh.current = true; void query.refetch(); }}>Retry source</button>
        </div> :
        rows.length === 0 ? <div className="screener-message">No instruments match {filters.length ? "these filters or this search" : "this search"}.</div> :
        <div className="screener-virtual" style={{ height: virtualizer.getTotalSize(), width: table.getTotalSize() }}>
          {virtualRows.map((virtual) => {
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
    </div>
    {previewOpen && !narrow && <div className="screener-splitter" role="separator" aria-orientation="vertical" aria-label="Resize quick preview"
      aria-valuemin={PREVIEW_MIN} aria-valuemax={PREVIEW_MAX} aria-valuenow={previewWidth} tabIndex={0}
      onPointerDown={onSplitterPointerDown} onKeyDown={onSplitterKeyDown} />}
    {previewOpen && (!narrow || selectedRow) && <QuickPreview row={selectedRow} quote={selected ? quotes[selected] : undefined} filters={filters}
      screenLabel={selectedScreenId ? `${selectedName}${changed ? " (modified)" : ""}` : null} overlay={narrow} width={previewWidth}
      paneRef={previewRef} onClose={closePreview} onOpen={open} />}
    </div>
    <footer className="screener-footer"><span>{query.data?.result_count.toLocaleString() ?? "—"}{filters.length && query.data?.unfiltered_count !== undefined ? ` of ${query.data.unfiltered_count.toLocaleString()}` : ""} results</span>
      <span>Quotes {quoteLabel}</span>
      <span>Market {session}</span>
      <span>Universe {query.data?.universe_as_of ? `as of ${new Date(query.data.universe_as_of).toLocaleTimeString()}` : "unavailable"}</span>
      <span>Source {query.data?.provider_health[0]?.state.toLowerCase() ?? "checking"}</span></footer>
  </section>;
}
