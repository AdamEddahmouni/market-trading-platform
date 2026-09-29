import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import { authHeaders } from "../auth/session";

const FieldSchema = z.object({
  value: z.number().nullable(),
  source: z.string(),
  state: z.string(),
  as_of: z.string().nullable().optional(),
  as_of_ns: z.number().optional(),
  /** S9: what the number is (e.g. HIGH_YIELD vs HIGH_INVESTMENT_RATE, NOMINAL_PAR_10Y). */
  basis: z.string().optional(),
});
const RowSchema = z.object({
  instrument: z.object({
    instrument_id: z.string(),
    venue_id: z.string(),
    asset_class: z.string(),
    instrument_kind: z.string().optional(),
    tradability: z.string().optional(), intelligence_views: z.array(z.string()).optional(),
  }),
  symbol: z.string(),
  company: z.string(),
  sector: z.string().nullable(),
  industry: z.string().nullable(),
  country: z.string().nullable().optional(),
  earnings_date: z.string().nullable().optional(),
  recommendation: z.string().nullable().optional(),
  root: z.string().optional(),
  exchange: z.string().nullable().optional(),
  contract_month: z.string().optional(),
  expiry: z.string().optional(),
  lead: z.boolean().optional(),
  market_data_id: z.string().optional(),
  provider_symbol: z.string().optional(),
  snapshot_id: z.string().optional(),
  // S9 Bonds: provider-neutral terms. The CUSIP is also `symbol`; it is never a ticker.
  cusip: z.string().optional(),
  isin: z.string().nullable().optional(),
  identity_source: z.string().optional(),
  issuer: z.string().optional(),
  security_type: z.string().optional(),
  term: z.string().nullable().optional(),
  issue_date: z.string().optional(),
  maturity: z.string().optional(),
  maturity_bucket: z.string().nullable().optional(),
  tips: z.string().optional(),
  frn: z.string().optional(),
  callable: z.string().nullable().optional(),
  auction_date: z.string().nullable().optional(),
  series: z.string().nullable().optional(),
  reference_tenor: z.string().nullable().optional(),
  reference_date: z.string().nullable().optional(),
  reference_reason: z.string().nullable().optional(),
  base_asset: z.string().optional(),
  quote_asset: z.string().optional(),
  venue: z.string().optional(),
  product_type: z.string().optional(),
  status: z.string().optional(),
  price_increment: z.string().nullable().optional(),
  min_order_size: z.string().nullable().optional(),
  fields: z.record(FieldSchema),
});
export const ScreenerUniverseSchema = z.enum(["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"]);
export type ScreenerUniverse = z.infer<typeof ScreenerUniverseSchema>;
const ScreenerSchema = z.object({
  schema_version: z.literal("screener/1.0.0"),
  universe: ScreenerUniverseSchema,
  generated_at: z.string(),
  market_session: z.string(),
  universe_as_of: z.string().nullable(),
  screener_as_of: z.string().nullable(),
  result_count: z.number(),
  unfiltered_count: z.number().optional(),
  // S6 bounded page: the server owns filtering, ordering, and the page window.
  offset: z.number().optional(),
  limit: z.number().optional(),
  returned: z.number().optional(),
  has_more: z.boolean().optional(),
  result_set_id: z.string().nullable().optional(),
  selected_id: z.string().nullable().optional(),
  selected_index: z.number().nullable().optional(),
  evaluation: z.enum(["CATALOG", "SNAPSHOT"]).optional(),
  snapshot: z.object({ id: z.string(), as_of: z.string(), source: z.string(), complete: z.boolean(), total: z.number(),
    returned: z.number(), priced: z.number(), refused: z.number(), refused_reason: z.string().nullable() }).passthrough().nullable().optional(),
  provider_health: z.array(z.object({ provider: z.string(), role: z.string().optional(), state: z.string(), reason: z.string().nullable() })),
  /** S9: per-category coverage; an unavailable category has no count and is never folded into a total. */
  coverage: z.record(z.object({ state: z.string(), count: z.number().nullable() })).optional(),
  source_error: z.string().nullable(),
  rows: z.array(RowSchema),
});
const QuoteSchema = z.object({
  state: z.string(),
  session_state: z.string().optional(),
  reason: z.string().nullable().optional(),
  age_ms: z.number().optional(),
  fields: z.record(FieldSchema),
});
const WindowSchema = z.object({
  schema_version: z.literal("screener/1.0.0"),
  generated_at: z.string(),
  market_session: ScreenerSchema.shape.market_session,
  active: z.number(),
  cap: z.number(),
  quotes: z.record(QuoteSchema),
});

export type ScreenerRow = z.infer<typeof RowSchema>;
export type ScreenerField = z.infer<typeof FieldSchema>;
export type ScreenerQuote = z.infer<typeof QuoteSchema>;
export type ScreenerResponse = z.infer<typeof ScreenerSchema>;

export const ScreenerFilterSchema = z.object({
  id: z.string(), field: z.string(), operator: z.string(),
  value: z.union([z.number(), z.string(), z.array(z.number()), z.array(z.string())]),
});
export type ScreenerFilter = z.infer<typeof ScreenerFilterSchema>;
export const ScreenerScreenSchema = z.object({
  id: z.string(), version: z.number(), name: z.string(), universe: ScreenerUniverseSchema,
  filters: z.array(ScreenerFilterSchema), view: z.string(),
  sort: z.object({ field: z.string(), descending: z.boolean() }),
  columns: z.object({ visible: z.array(z.string()), order: z.array(z.string()),
    widths: z.record(z.number()), pinned: z.array(z.string()) }),
});
export type ScreenerScreen = z.infer<typeof ScreenerScreenSchema>;
const ScreenerConfigSchema = z.object({
  schema_version: z.number(), persistence_available: z.boolean(),
  universes: z.array(z.object({ id: ScreenerUniverseSchema, label: z.string(), asset_class: z.string(),
    instrument_kind: z.string(), source: z.string(), session_model: z.string(), default_sort: z.string(),
    default_columns: z.array(z.string()), views: z.record(z.array(z.string())), view_order: z.array(z.string()).optional(),
    view_aliases: z.record(z.string()).optional(),
    quote_capability: z.string(), bars_capability: z.string(), panels: z.array(z.string()),
    admitted_asset_classes: z.array(z.string()).optional(), admitted_instrument_kinds: z.array(z.string()).optional(),
    identity_fields: z.array(z.string()).optional(), data_sources: z.array(z.string()).optional(),
    tradability: z.string().optional(), intelligence_views: z.array(z.string()).optional(),
    fields: z.record(z.object({ execution: z.string(), sortable: z.boolean(), filterable: z.boolean(),
      label: z.string().optional(), unit: z.string().optional() })).optional() })),
  query: z.object({ default_limit: z.number(), max_limit: z.number() }).optional(),
  catalog: z.array(z.object({ field: z.string(), label: z.string(), category: z.string(),
    type: z.enum(["number", "text"]), unit: z.string(), operators: z.array(z.string()),
    universes: z.array(z.string()), availability: z.string() })),
  presets: z.array(z.object({ id: z.string(), name: z.string(), version: z.string(),
    universe: ScreenerUniverseSchema,
    status: z.enum(["SUPPORTED", "UNSUPPORTED"]), reason: z.string().nullable(),
    filters: z.array(ScreenerFilterSchema) })),
  saved: z.array(ScreenerScreenSchema),
  last: ScreenerScreenSchema.nullable(),
  preview_layout: z.object({ version: z.number(), open: z.boolean(), width: z.number() }).optional(),
  panel_layout: z.lazy(() => PanelLayoutSchema).optional(),
});
export type ScreenerConfig = z.infer<typeof ScreenerConfigSchema>;
export const PANEL_IDS = ["order_flow", "cvd", "level2", "charts", "futures", "options", "short_squeeze", "rates_curve", "news",
  "institutional", "congress_gov"] as const;
export type PanelId = (typeof PANEL_IDS)[number];
// Presentation only: which specialist panels are open and how they are arranged.
// Market observations never enter this record.
const PanelLayoutSchema = z.object({
  version: z.literal(1),
  open_panels: z.array(z.enum(PANEL_IDS)),
  active_panel: z.enum(PANEL_IDS).nullable(),
  dock_height: z.number(),
  dockview_layout: z.record(z.unknown()).nullable(),
});
export type PanelLayout = z.infer<typeof PanelLayoutSchema>;

export function persistScreenerPanelLayout(layout: PanelLayout) {
  return postJson("/screener/config", { action: "panel_layout", layout }, z.object({ result: PanelLayoutSchema }).passthrough());
}

/** The canonical Screener query. Pages never change it; any change starts a new result chain. */
export type ScreenerQueryInput = {
  universe: ScreenerUniverse; search: string; sort: string; descending: boolean; filters: ScreenerFilter[];
};
export type ScreenerPageParam = { offset: number; resultSet: string | null };
export const SCREENER_PAGE_LIMIT = 200;

export async function fetchScreener(query: ScreenerQueryInput, page: ScreenerPageParam = { offset: 0, resultSet: null },
  options: { refresh?: boolean; selected?: string | null; signal?: AbortSignal; limit?: number } = {}) {
  const params = new URLSearchParams({
    universe: query.universe, search: query.search, sort: query.sort,
    descending: query.descending ? "1" : "0", offset: String(page.offset), limit: String(options.limit ?? SCREENER_PAGE_LIMIT),
  });
  if (page.resultSet) params.set("result_set", page.resultSet);
  if (options.refresh) params.set("refresh", "1");
  if (options.selected) params.set("selected", options.selected);
  if (query.filters.length) params.set("filters", JSON.stringify(query.filters));
  const result = await fetchJson(`/screener?${params}`, ScreenerSchema, options.signal ? { signal: options.signal } : undefined);
  // Response identity guard: a page for another universe or window is never appended.
  if (result.universe !== query.universe || (result.offset ?? 0) !== page.offset) throw new Error("SCREENER_PAGE_IDENTITY_MISMATCH");
  return result;
}

export function fetchScreenerConfig() {
  return fetchJson("/screener/config", ScreenerConfigSchema);
}

export function saveScreenerScreen(screen: Omit<ScreenerScreen, "id" | "version"> & { id?: string; version?: number }) {
  return postJson("/screener/config", { action: "save", screen },
    z.object({ result: ScreenerScreenSchema, saved: z.array(ScreenerScreenSchema) }));
}

export function deleteScreenerScreen(id: string) {
  return postJson("/screener/config", { action: "delete", id },
    z.object({ result: z.boolean(), saved: z.array(ScreenerScreenSchema) }));
}

export function persistLastScreenerConfig(screen: Omit<ScreenerScreen, "id" | "version">) {
  return postJson("/screener/config", { action: "last", screen },
    z.object({ result: ScreenerScreenSchema, saved: z.array(ScreenerScreenSchema) }));
}

export function persistScreenerPreviewLayout(layout: { open: boolean; width: number }) {
  return postJson("/screener/config", { action: "preview_layout", layout },
    z.object({ result: z.object({ version: z.number(), open: z.boolean(), width: z.number() }) }).passthrough());
}

const BarSchema = z.object({
  time: z.number(), start: z.string(), end: z.string(), open: z.number(), high: z.number(),
  low: z.number(), close: z.number(), volume: z.number().nullable(), session: z.string(),
});
const ZoneSchema = z.object({
  lower: z.number(), upper: z.number(), center: z.number(), touches: z.number(), strength: z.number(),
  last_touch_end_ns: z.number(), kinds: z.array(z.string()),
});
const SideSchema = ZoneSchema.extend({ distance_pct: z.number() }).nullable();
const EvidenceSchema = z.object({
  class: z.enum(["OBSERVED", "DERIVED", "AI_SYNTHESIS", "UNAVAILABLE", "INSUFFICIENT_EVIDENCE"]),
  kind: z.string(), text: z.string(), source: z.string(), as_of: z.string().nullable(),
});
const PreviewSchema = z.object({
  schema_version: z.literal("screener-preview/1.0.0"),
  generated_at: z.string(),
  market_session: ScreenerSchema.shape.market_session,
  instrument: z.object({ instrument_id: z.string(), venue_id: z.string(), asset_class: z.string(), symbol: z.string(),
    company: z.string(), sector: z.string().nullable(), industry: z.string().nullable(),
    root: z.string().nullable().optional(), expiry: z.string().nullable().optional(), exchange: z.string().nullable().optional() }),
  universe: ScreenerUniverseSchema.optional(),
  snapshot_as_of: z.string().nullable().optional(),
  quote: QuoteSchema,
  key_data: z.array(z.object({ field: z.string(), label: z.string(), unit: z.string(), value: z.number().nullable(),
    source: z.string().nullable(), state: z.string(), as_of: z.string().nullable() })),
  bars: z.object({
    timeframe: z.string(), session_scope: z.string(), provider: z.string(), source_id: z.string(), state: z.string(),
    reason: z.string().nullable(), provider_reason: z.string().nullable(), received_at: z.string().nullable(),
    latest_complete_bar_end: z.string().nullable(), bar_count: z.number(), bars: z.array(BarSchema), forming: BarSchema.nullable(),
  }),
  levels: z.object({
    method: z.string(), timeframe: z.string(), session_scope: z.string(), bar_state: z.string(), state: z.string(),
    reason: z.string().nullable(), reasons: z.array(z.string()), calculated_at: z.string().nullable(),
    input_bar_count: z.number(), input_latest_bar_end: z.string().nullable(), min_strength: z.number(),
    strength_semantics: z.string(), zones: z.array(ZoneSchema),
    price: z.object({ value: z.number(), source: z.string(), state: z.string(), as_of: z.string() }).nullable(),
    support: SideSchema, resistance: SideSchema, testing: SideSchema,
  }),
  why: z.object({
    matched: z.object({ state: z.string(), items: z.array(z.object({ filter_id: z.string(), label: z.string(),
      passed: z.boolean(), missing: z.boolean(), text: z.string() })) }),
    moving: z.object({ items: z.array(EvidenceSchema), headline_window_start: z.string() }),
  }),
  futures: z.object({
    mapping_version: z.string(), causal_note: z.string(),
    items: z.array(z.object({
      root: z.string(), name: z.string(), relationship_type: z.string(), relationship_reason: z.string(),
      contract: z.object({ state: z.string(), reason: z.string().nullable().optional(), contract_id: z.string().optional(),
        last_trade_date: z.string().optional() }),
      quote: z.object({ price: z.number(), price_basis: z.string(), change_pct: z.number().nullable(), provider: z.string(),
        as_of: z.string().nullable(), age_ms: z.number().nullable(), state: z.string() }).nullable(),
      availability: z.string(), unavailable_reason: z.string().nullable(),
    })),
  }),
});
export type ScreenerPreview = z.infer<typeof PreviewSchema>;
export type SrZone = z.infer<typeof ZoneSchema>;
export type PreviewBar = z.infer<typeof BarSchema>;

export async function fetchScreenerPreview(instrumentId: string, timeframe: string, scope: string, filters: ScreenerFilter[], signal?: AbortSignal, universe: ScreenerUniverse = "US_EQUITIES", snapshotId?: string | null) {
  const query = new URLSearchParams({ instrument: instrumentId, timeframe, scope, universe });
  if (filters.length) query.set("filters", JSON.stringify(filters));
  // "Why it matched" explains the snapshot the result was filtered on, not a later quote.
  if (snapshotId) query.set("snapshot", snapshotId);
  const preview = await fetchJson(`/screener/preview?${query}`, PreviewSchema, { signal });
  // Request identity guard: a response for another instrument is never rendered.
  if (preview.instrument.instrument_id !== instrumentId) throw new Error("PREVIEW_IDENTITY_MISMATCH");
  return preview;
}

export function updateScreenerWindow(clientId: string, symbols: string[], universe: ScreenerUniverse = "US_EQUITIES") {
  return postJson("/screener/window", { client_id: clientId, symbols, universe }, WindowSchema);
}

export function releaseScreenerWindow(clientId: string) {
  return postJson("/screener/window/release", { client_id: clientId }, z.object({ released: z.boolean() }));
}

export function releaseScreenerWindowOnUnload(clientId: string) {
  void fetch("/screener/window/release", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ client_id: clientId }),
    keepalive: true,
  }).catch(() => undefined);
}
