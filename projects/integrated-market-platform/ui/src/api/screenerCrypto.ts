import { z } from "zod";
import { fetchJson } from "./fetchJson";
import type { ScreenerFilter } from "./screener";

const Field = z.object({ value: z.number().nullable(), source: z.string(), state: z.string(),
  as_of: z.string().nullable().optional(), basis: z.string().optional() });
const Bar = z.object({ time: z.number(), start: z.string(), end: z.string(), open: z.number(),
  high: z.number(), low: z.number(), close: z.number(), volume: z.number().nullable(), session: z.string() });
const Preview = z.object({
  schema_version: z.literal("screener-crypto-preview/1.0.0"), generated_at: z.string(),
  market_session: z.literal("24_7"),
  instrument: z.object({ instrument_id: z.string(), venue_id: z.string(), symbol: z.string(),
    base_asset: z.string(), quote_asset: z.string(), venue: z.string(), product_type: z.literal("SPOT"),
    status: z.string(), price_increment: z.string().nullable().optional(), min_order_size: z.string().nullable().optional(),
    base_increment: z.string().nullable().optional(), quote_increment: z.string().nullable().optional(),
    min_order_notional: z.string().nullable().optional(), catalog_as_of: z.string().nullable().optional() }).passthrough(),
  snapshot_as_of: z.string().nullable(),
  fields: z.record(Field),
  quote: z.object({ state: z.string(), reason: z.string().nullable().optional(), fields: z.record(Field) }).passthrough(),
  bars: z.object({ timeframe: z.string(), session_scope: z.literal("24_7"), provider: z.string(),
    state: z.string(), reason: z.string().nullable(), received_at: z.string().nullable(),
    latest_complete_bar_end: z.string().nullable(), bar_count: z.number(), bars: z.array(Bar), forming: Bar.nullable() }).passthrough(),
  levels: z.object({ method: z.string(), state: z.string(), reason: z.string().nullable(), calculated_at: z.string().nullable(),
    input_bar_count: z.number(), min_strength: z.number(),
    zones: z.array(z.object({ lower: z.number(), upper: z.number(), center: z.number(), touches: z.number(), strength: z.number(),
      last_touch_end_ns: z.number(), kinds: z.array(z.string()) })),
    price: z.object({ value: z.number(), source: z.string(), state: z.string(), as_of: z.string().nullable() }).nullable() }).passthrough(),
  why: z.object({ matched: z.object({ state: z.string(), items: z.array(z.object({
    filter_id: z.string(), label: z.string(), passed: z.boolean(), missing: z.boolean(), text: z.string() }).passthrough()) }) }),
  source_health: z.object({ catalog: z.string(), snapshot: z.string(), quote: z.string(), bars: z.string() }),
});

export type CryptoPreview = z.infer<typeof Preview>;

export function fetchCryptoPreview(instrumentId: string, timeframe: "1m" | "5m" | "15m", filters: ScreenerFilter[], signal?: AbortSignal) {
  const query = new URLSearchParams({ universe: "CRYPTO", instrument: instrumentId, timeframe, scope: "EXTENDED" });
  if (filters.length) query.set("filters", JSON.stringify(filters));
  return fetchJson(`/screener/preview?${query}`, Preview, { signal });
}
