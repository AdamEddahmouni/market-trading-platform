import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import { fetchScreener, releaseScreenerWindow, releaseScreenerWindowOnUnload, updateScreenerWindow, type ScreenerField, type ScreenerQuote, type ScreenerRow } from "../../api/screener";
import "./screener.css";

type SortKey = "symbol" | "price" | "change_pct" | "volume" | "rel_volume" | "float_shares" | "market_cap" | "short_float_pct" | "bid" | "ask" | "spread_pct" | "rsi_14";
const definitions: { key: SortKey; label: string; width: number; format: "text" | "price" | "percent" | "compact" | "decimal" }[] = [
  { key: "symbol", label: "Symbol", width: 190, format: "text" },
  { key: "price", label: "Price", width: 92, format: "price" },
  { key: "change_pct", label: "Chg %", width: 86, format: "percent" },
  { key: "volume", label: "Volume", width: 103, format: "compact" },
  { key: "rel_volume", label: "RVOL", width: 76, format: "decimal" },
  { key: "float_shares", label: "Float", width: 93, format: "compact" },
  { key: "market_cap", label: "Mkt Cap", width: 95, format: "compact" },
  { key: "short_float_pct", label: "Short %", width: 87, format: "percent" },
  { key: "bid", label: "Bid", width: 90, format: "price" },
  { key: "ask", label: "Ask", width: 90, format: "price" },
  { key: "spread_pct", label: "Spread %", width: 97, format: "percent" },
  { key: "rsi_14", label: "RSI (14)", width: 84, format: "decimal" },
];
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const quoteKeys = new Set(["price", "volume", "bid", "ask", "spread_pct"]);
const sourceSort = (key: SortKey) => ["bid", "ask", "spread_pct"].includes(key) ? "volume" : key;
function fieldFor(row: ScreenerRow, key: SortKey, quote?: ScreenerQuote) {
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
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("volume");
  const [descending, setDescending] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [quotes, setQuotes] = useState<Record<string, ScreenerQuote>>({});
  const [quoteError, setQuoteError] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const clientId = useRef(crypto.randomUUID().replace(/-/g, ""));
  const quoteQueue = useRef<Promise<void>>(Promise.resolve());
  const forceNextRefresh = useRef(false);
  const query = useQuery({
    queryKey: ["main-screener", search, sourceSort(sort), descending],
    queryFn: () => {
      const force = forceNextRefresh.current;
      forceNextRefresh.current = false;
      return force ? fetchScreener(search, sourceSort(sort), descending, true)
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
      const field = fieldFor(item, definition.key, quotes[item.instrument.instrument_id]);
      const tone = definition.key === "change_pct" && field?.value != null
        ? field.value > 0 ? "screener-positive" : field.value < 0 ? "screener-negative" : "" : "";
      return <span className={tone} title={field ? `${field.source} · ${field.state}` : "Unavailable"}>{valueText(field, definition.format, definition.key === "change_pct")}</span>;
    },
  })), [quotes]);
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel(), getRowId: (row) => row.instrument.instrument_id });
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
  const selectedIndex = rows.findIndex((row) => row.instrument.instrument_id === selected);
  const activate = (index: number) => {
    const row = rows[index];
    if (!row) return;
    setSelected(row.instrument.instrument_id);
    virtualizer.scrollToIndex(index, { align: "auto" });
  };
  const open = (row: ScreenerRow) => navigate(workspacePathForInstrument(row.instrument.instrument_id));
  const onGridKeyDown = (event: KeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      activate(Math.min(rows.length - 1, Math.max(0, selectedIndex < 0 ? 0 : selectedIndex + (event.key === "ArrowDown" ? 1 : -1))));
    } else if (event.key === "Enter" && selectedIndex >= 0) open(rows[selectedIndex]);
    else if (event.key === "Escape") setSelected(null);
  };
  const sortBy = (key: SortKey) => {
    if (sort === key) setDescending((current) => !current);
    else { setSort(key); setDescending(key !== "symbol"); }
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
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
        <input ref={searchRef} value={search} onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Escape") { setSearch(""); event.currentTarget.blur(); } }}
          placeholder="Search symbol or company  /" /></label><span className="screener-market-badge">{query.data?.market_session ?? "MARKET"}</span></header>
    <div className="screener-toolbar"><span>Universe <strong>US Equities</strong></span><span>Session <strong>{session}</strong></span><span className="screener-view">OVERVIEW</span></div>
    <div className="screener-grid" role="grid" aria-label="US equity screener" aria-rowcount={rows.length + 1} tabIndex={0}
      onKeyDown={onGridKeyDown} ref={scrollRef}>
      <div className="screener-header" role="row" style={{ width: table.getTotalSize() }}>
        {table.getFlatHeaders().map((header) => {
          const key = header.id as SortKey;
          return <button type="button" role="columnheader" key={header.id}
            className={key === "symbol" ? "screener-heading screener-left" : "screener-heading"}
            style={{ width: header.getSize() }} aria-sort={sort === key ? descending ? "descending" : "ascending" : "none"}
            onClick={() => sortBy(key)}>{flexRender(header.column.columnDef.header, header.getContext())}
            <span className="screener-sort">{sort === key ? descending ? "▼" : "▲" : ""}</span></button>;
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
        rows.length === 0 ? <div className="screener-message">No instruments match this search.</div> :
        <div className="screener-virtual" style={{ height: virtualizer.getTotalSize(), width: table.getTotalSize() }}>
          {virtualRows.map((virtual) => {
            const row = table.getRowModel().rows[virtual.index];
            if (!row) return null;
            return <div role="row" key={row.id} aria-rowindex={virtual.index + 2} aria-selected={row.id === selected}
              className={`screener-row${row.id === selected ? " selected" : ""}`}
              style={{ transform: `translateY(${virtual.start}px)`, width: table.getTotalSize() }}
              onClick={() => { if (row.id === selected) open(row.original); else setSelected(row.id); }}
              onDoubleClick={() => open(row.original)}>
              {row.getVisibleCells().map((cell) => <div role="gridcell" key={cell.id}
                className={cell.column.id === "symbol" ? "screener-cell screener-left" : "screener-cell"}
                style={{ width: cell.column.getSize() }}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</div>)}
            </div>;
          })}
        </div>}
    </div>
    <footer className="screener-footer"><span>{query.data?.result_count.toLocaleString() ?? "—"} results</span>
      <span>Quotes {quoteLabel}</span>
      <span>Market {session}</span>
      <span>Universe {query.data?.universe_as_of ? `as of ${new Date(query.data.universe_as_of).toLocaleTimeString()}` : "unavailable"}</span>
      <span>Source {query.data?.provider_health[0]?.state.toLowerCase() ?? "checking"}</span></footer>
  </section>;
}
