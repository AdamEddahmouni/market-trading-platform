import { z } from "zod";
import { authHeaders } from "../auth/session";
import { fetchJson, postJson } from "./fetchJson";
import type { PanelId, ScreenerUniverse } from "./screener";

// S4 specialist panel contracts. Each panel keeps its own clock and state; a
// response for another instrument is never rendered (identity guard below).
const PanelState = z.enum(["CURRENT", "SESSION_CLOSED", "STALE", "PARTIAL", "INVALID", "DISCONNECTED", "NOT_ENTITLED",
  "UNAVAILABLE", "CONNECTING", "SUBSCRIPTION_BUSY"]);
export type PanelState = z.infer<typeof PanelState>;
const Base = z.object({
  schema_version: z.literal("screener-specialist/1.0.0"),
  instrument_id: z.string(), provider: z.string().nullable(), generated_at: z.string().nullable(),
  market_session: z.string(), state: PanelState, reason: z.string().nullable(),
  entitlement: z.enum(["PROBE_VERIFIED", "UNVERIFIED", "NOT_ENTITLED"]).optional(),
});
const Window = z.object({ basis: z.enum(["SINCE_SUBSCRIPTION", "LAST_N_CAPTURED"]), anchor_at: z.string().nullable(),
  start: z.string().nullable(), end: z.string().nullable(), max_records: z.number(), truncated: z.boolean() }).nullable();
const Aggressor = z.object({ state: z.enum(["NATIVE", "INFERRED", "UNKNOWN"]), side: z.enum(["BUY", "SELL"]).nullable(), method: z.string() });
const OrderFlowSchema = Base.extend({
  panel: z.literal("order_flow"), window: Window,
  latest_event_at: z.string().nullable().optional(), latest_received_at: z.string().nullable().optional(),
  summary: z.object({
    trade_count: z.number(), total_volume: z.number(), buy_volume: z.number(), sell_volume: z.number(), unknown_volume: z.number(),
    net_signed_volume: z.number(), classified_volume_pct: z.number().nullable(), native_count: z.number(), inferred_count: z.number(),
    unknown_count: z.number(), methods: z.record(z.number()), trades_per_minute: z.number().nullable(),
    large_print_threshold: z.number().nullable(),
  }).nullable(),
  tape: z.array(z.object({ trade_id: z.string(), event_time: z.string().nullable(), received_time: z.string().nullable(), price: z.number(),
    size: z.number(), aggressor: Aggressor, condition: z.string().nullable(), large: z.boolean() })),
});
const CvdSchema = Base.extend({
  panel: z.literal("cvd"), derivation: z.literal("DERIVED"), window: Window,
  latest_event_at: z.string().nullable().optional(), latest_received_at: z.string().nullable().optional(),
  summary: z.object({ cvd: z.number(), recent_delta: z.number().nullable(), recent_delta_seconds: z.number(), trade_count: z.number(),
    classified_volume: z.number(), unknown_volume: z.number(), classified_volume_pct: z.number().nullable(),
    aggressor_states: z.record(z.number()), methods: z.array(z.string()) }).nullable(),
  points: z.array(z.object({ time_ms: z.number(), cvd: z.number(), delta: z.number() })),
});
const Level = z.object({ price: z.number(), size: z.number(), cumulative_size: z.number() });
const DepthSchema = Base.extend({
  panel: z.literal("level2"), bids: z.array(Level), asks: z.array(Level), best_bid: z.number().nullable(), best_ask: z.number().nullable(),
  spread: z.number().nullable(), mid: z.number().nullable(), spread_bps: z.number().nullable(),
  imbalance: z.array(z.object({ levels: z.number(), bid_levels: z.number(), ask_levels: z.number(), bid_size: z.number(), ask_size: z.number(),
    bid_share: z.number(), signed: z.number(), complete: z.boolean() })),
  completeness: z.object({ basis: z.string(), bid_levels: z.number(), ask_levels: z.number(), venue_scope: z.string(), update_semantics: z.string() }).nullable(),
  freshness: z.object({ status: z.string(), age_ms: z.number().nullable(), ttl_ms: z.number(), policy: z.string() }).nullable(),
  latest_event_at: z.string().nullable(), latest_received_at: z.string().nullable(), quality_flags: z.array(z.string()),
});
const DemandSchema = z.object({
  schema_version: z.literal("screener-specialist/1.0.0"), instrument_id: z.string().nullable(), panels: z.array(z.string()),
  capabilities: z.array(z.object({ panel: z.string(), capability: z.string(), accepted: z.boolean(), reason: z.string().nullable(),
    ref_count: z.number(), provider_subscription_active: z.boolean() })),
  cap: z.object({ max_instruments: z.number(), occupied_instruments: z.number() }),
});
const ChartBar = z.object({ time: z.number(), start: z.string(), end: z.string(), open: z.number(), high: z.number(), low: z.number(),
  close: z.number(), volume: z.number().nullable(), session: z.string() });
const Zone = z.object({ lower: z.number(), upper: z.number(), center: z.number(), touches: z.number(), strength: z.number(),
  last_touch_end_ns: z.number(), kinds: z.array(z.string()) });
const QuoteField = z.object({ value: z.number().nullable(), source: z.string(), state: z.string(), as_of_ns: z.number().optional() });
const ChartSchema = z.object({
  schema_version: z.literal("screener-chart/1.0.0"), generated_at: z.string(), market_session: z.string(),
  instrument: z.object({ instrument_id: z.string(), symbol: z.string(), company: z.string() }),
  quote: z.object({ state: z.string(), age_ms: z.number().optional(), fields: z.record(QuoteField) }),
  bars: z.object({ timeframe: z.string(), session_scope: z.string(), provider: z.string(), source_id: z.string(), state: z.string(),
    reason: z.string().nullable(), provider_reason: z.string().nullable(), received_at: z.string().nullable(),
    latest_complete_bar_end: z.string().nullable(), bar_count: z.number(), bars: z.array(ChartBar), forming: ChartBar.nullable() }),
  levels: z.object({ method: z.string(), state: z.string(), reason: z.string().nullable(), calculated_at: z.string().nullable(),
    input_bar_count: z.number(), input_latest_bar_end: z.string().nullable(), min_strength: z.number(), zones: z.array(Zone),
    price: z.object({ value: z.number(), source: z.string(), state: z.string(), as_of: z.string() }).nullable() }),
});
const FuturesSchema = z.object({
  schema_version: z.literal("screener-futures-context/1.0.0"), generated_at: z.string(),
  instrument: z.object({ instrument_id: z.string(), symbol: z.string(), company: z.string(), sector: z.string().nullable(), industry: z.string().nullable() }),
  futures: z.object({ mapping_version: z.string(), causal_note: z.string(), items: z.array(z.object({
    root: z.string(), name: z.string(), relationship_type: z.string(), relationship_reason: z.string(),
    contract: z.object({ state: z.string(), reason: z.string().nullable().optional(), contract_id: z.string().optional(),
      last_trade_date: z.string().optional(), provider_code: z.string().optional() }).passthrough(),
    quote: z.object({ price: z.number(), price_basis: z.string(), change_pct: z.number().nullable(), provider: z.string(),
      as_of: z.string().nullable(), age_ms: z.number().nullable(), state: z.string() }).nullable(),
    availability: z.string(), unavailable_reason: z.string().nullable(),
  })) }),
});

export type OrderFlowPayload = z.infer<typeof OrderFlowSchema>;
export type CvdPayload = z.infer<typeof CvdSchema>;
export type DepthPayload = z.infer<typeof DepthSchema>;
export type PanelDemand = z.infer<typeof DemandSchema>;
export type ChartPayload = z.infer<typeof ChartSchema>;
export type FuturesContextPayload = z.infer<typeof FuturesSchema>;

function guard<T>(payload: T, requested: string, actual: string): T {
  if (actual !== requested) throw new Error("PANEL_IDENTITY_MISMATCH");
  return payload;
}

export async function fetchOrderFlow(instrumentId: string, signal?: AbortSignal, universe: ScreenerUniverse = "US_EQUITIES") {
  const payload = await fetchJson(`/screener/order-flow?instrument=${encodeURIComponent(instrumentId)}&universe=${universe}`, OrderFlowSchema, { signal });
  return guard(payload, instrumentId, payload.instrument_id);
}
export async function fetchCvd(instrumentId: string, signal?: AbortSignal, universe: ScreenerUniverse = "US_EQUITIES") {
  const payload = await fetchJson(`/screener/cvd?instrument=${encodeURIComponent(instrumentId)}&universe=${universe}`, CvdSchema, { signal });
  return guard(payload, instrumentId, payload.instrument_id);
}
export async function fetchDepth(instrumentId: string, signal?: AbortSignal, universe: ScreenerUniverse = "US_EQUITIES") {
  const payload = await fetchJson(`/screener/depth?instrument=${encodeURIComponent(instrumentId)}&universe=${universe}`, DepthSchema, { signal });
  return guard(payload, instrumentId, payload.instrument_id);
}
export async function fetchChart(instrumentId: string, timeframe: string, scope: string, signal?: AbortSignal, universe: ScreenerUniverse = "US_EQUITIES") {
  const query = new URLSearchParams({ instrument: instrumentId, timeframe, scope, universe });
  const payload = await fetchJson(`/screener/chart?${query}`, ChartSchema, { signal });
  return guard(payload, instrumentId, payload.instrument.instrument_id);
}
export async function fetchFuturesContext(instrumentId: string, signal?: AbortSignal, universe: ScreenerUniverse = "US_EQUITIES") {
  const payload = await fetchJson(`/screener/futures-context?instrument=${encodeURIComponent(instrumentId)}&universe=${universe}`, FuturesSchema, { signal });
  return guard(payload, instrumentId, payload.instrument.instrument_id);
}

export function demandPanels(clientId: string, instrumentId: string | null, panels: PanelId[], universe: ScreenerUniverse = "US_EQUITIES") {
  return postJson("/screener/panels", { client_id: clientId, instrument_id: instrumentId, panels, universe }, DemandSchema);
}
export function releasePanels(clientId: string) {
  return postJson("/screener/panels/release", { client_id: clientId }, z.object({ released: z.boolean() }));
}
export function releasePanelsOnUnload(clientId: string) {
  void fetch("/screener/panels/release", {
    method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ client_id: clientId }), keepalive: true,
  }).catch(() => undefined);
}
