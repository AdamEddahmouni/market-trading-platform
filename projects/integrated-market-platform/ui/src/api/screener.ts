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

export function fetchScreener(search: string, sort: string, descending: boolean, refresh = false) {
  const query = new URLSearchParams({
    universe: "US_EQUITIES", search, sort,
    descending: descending ? "1" : "0", limit: "10000",
  });
  if (refresh) query.set("refresh", "1");
  return fetchJson(`/screener?${query}`, ScreenerSchema);
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
