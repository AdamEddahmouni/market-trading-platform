import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import { authHeaders } from "../auth/session";

const FieldSchema = z.object({
  value: z.number().nullable(),
  source: z.string(),
  state: z.string(),
  as_of: z.string().optional(),
  as_of_ns: z.number().optional(),
});
const RowSchema = z.object({
  instrument: z.object({
    instrument_id: z.string(),
    venue_id: z.string(),
    asset_class: z.string(),
  }),
  symbol: z.string(),
  company: z.string(),
  sector: z.string().nullable(),
  industry: z.string().nullable(),
  country: z.string().nullable().optional(),
  earnings_date: z.string().nullable().optional(),
  recommendation: z.string().nullable().optional(),
  fields: z.record(FieldSchema),
});
const ScreenerSchema = z.object({
  schema_version: z.literal("screener/1.0.0"),
  universe: z.literal("US_EQUITIES"),
  generated_at: z.string(),
  market_session: z.enum(["PREMARKET", "REGULAR", "AFTER_HOURS", "CLOSED"]),
  universe_as_of: z.string().nullable(),
  screener_as_of: z.string().nullable(),
  result_count: z.number(),
  unfiltered_count: z.number().optional(),
  provider_health: z.array(z.object({ provider: z.string(), state: z.string(), reason: z.string().nullable() })),
  source_error: z.string().nullable(),
  rows: z.array(RowSchema),
});
const QuoteSchema = z.object({
  state: z.string(),
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
  id: z.string(), version: z.number(), name: z.string(), universe: z.literal("US_EQUITIES"),
  filters: z.array(ScreenerFilterSchema), view: z.string(),
  sort: z.object({ field: z.string(), descending: z.boolean() }),
  columns: z.object({ visible: z.array(z.string()), order: z.array(z.string()),
    widths: z.record(z.number()), pinned: z.array(z.string()) }),
});
export type ScreenerScreen = z.infer<typeof ScreenerScreenSchema>;
const ScreenerConfigSchema = z.object({
  schema_version: z.number(), persistence_available: z.boolean(),
  catalog: z.array(z.object({ field: z.string(), label: z.string(), category: z.string(),
    type: z.enum(["number", "text"]), unit: z.string(), operators: z.array(z.string()),
    universes: z.array(z.string()), availability: z.string() })),
  presets: z.array(z.object({ id: z.string(), name: z.string(), version: z.string(),
    status: z.enum(["SUPPORTED", "UNSUPPORTED"]), reason: z.string().nullable(),
    filters: z.array(ScreenerFilterSchema) })),
  saved: z.array(ScreenerScreenSchema),
  last: ScreenerScreenSchema.nullable(),
});
export type ScreenerConfig = z.infer<typeof ScreenerConfigSchema>;

export function fetchScreener(search: string, sort: string, descending: boolean, refresh = false, filters: ScreenerFilter[] = []) {
  const query = new URLSearchParams({
    universe: "US_EQUITIES", search, sort,
    descending: descending ? "1" : "0", limit: "10000",
  });
  if (refresh) query.set("refresh", "1");
  if (filters.length) query.set("filters", JSON.stringify(filters));
  return fetchJson(`/screener?${query}`, ScreenerSchema);
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

export function updateScreenerWindow(clientId: string, symbols: string[]) {
  return postJson("/screener/window", { client_id: clientId, symbols }, WindowSchema);
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
