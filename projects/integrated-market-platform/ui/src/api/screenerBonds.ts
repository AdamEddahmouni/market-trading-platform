import { z } from "zod";
import { fetchJson } from "./fetchJson";
import type { ScreenerFilter } from "./screener";

/**
 * S9 Bonds / Fixed Income contracts. Every value carries its class (OBSERVED,
 * DERIVED, REFERENCE, UNAVAILABLE), unit, source, and clock; a curve point is a
 * benchmark reference and never a security's own yield.
 */
const Value = z.union([z.number().finite(), z.string()]).nullable();
// S16: STALE marks a fund-reported valuation at its report date (never a price).
const ItemClass = z.enum(["OBSERVED", "DERIVED", "REFERENCE", "STALE", "UNAVAILABLE"]);
const Item = z.object({
  id: z.string().min(1), label: z.string(), value: Value, unit: z.string(), class: ItemClass,
  source: z.string().nullable(), as_of: z.string().nullable(), note: z.string().nullable(),
}).strict();
export type BondItem = z.infer<typeof Item>;
const Source = z.object({
  id: z.string(), label: z.string(), provider: z.string(), clock: z.string(), state: z.string().nullable(),
  as_of: z.string().nullable(), reason: z.string().nullable(),
  count: z.number().nullable().optional(), licence: z.string().optional(),
}).strict();
export type BondSource = z.infer<typeof Source>;
const Field = z.object({ value: z.number().nullable(), source: z.string(), state: z.string(),
  as_of: z.string().nullable(), basis: z.string().optional() }).strict();

export const BondPreviewSchema = z.object({
  schema_version: z.literal("screener-bond-preview/1.0.0"), universe: z.literal("BONDS"), generated_at: z.string(),
  market_session: z.string(),
  instrument: z.object({
    instrument_id: z.string().min(1), venue_id: z.string(), asset_class: z.enum(["SOVEREIGN_DEBT", "BOND"]),
    instrument_kind: z.enum(["SOVEREIGN_SECURITY", "BOND"]), tradability: z.literal("REFERENCE_ONLY"),
    cusip: z.string().length(9), isin: z.string().nullable(), identity_source: z.string(), issuer: z.string().nullable(),
    description: z.string(), security_type: z.string(), series: z.string().nullable(), category: z.string().optional(),
  }).strict(),
  sections: z.array(z.object({ id: z.string(), title: z.string(), items: z.array(Item) }).strict()),
  why: z.object({ matched: z.object({ state: z.string(), items: z.array(z.object({
    filter_id: z.string(), field: z.string(), label: z.string(), operator: z.string(), value: z.unknown(),
    observed: z.unknown(), passed: z.boolean(), missing: z.boolean(), text: z.string(),
  }).strict()) }).strict() }).strict(),
  sources: z.array(Source),
  capabilities: z.array(z.object({ panel: z.string(), state: z.enum(["SUPPORTED", "UNAVAILABLE", "NOT_APPLICABLE"]),
    reason: z.string().nullable() }).strict()),
}).strict();
export type BondPreview = z.infer<typeof BondPreviewSchema>;

const Point = z.object({ tenor: z.string(), years: z.number().positive(), value: z.number().finite() }).strict();
const Publication = z.object({ publication_date: z.string(), points: z.array(Point) }).strict();
const Curve = z.object({
  state: z.string(), publication_date: z.string().nullable(), points: z.array(Point),
  previous: Publication.nullable(), month_ago: Publication.nullable(),
}).strict();
export type CurvePayload = z.infer<typeof Curve>;
const Reference = z.object({
  state: z.enum(["REFERENCE", "UNAVAILABLE"]), reason: z.string().nullable().optional(), tenor: z.string().optional(),
  tenor_years: z.number().optional(), value: z.number().optional(), distance_years: z.number().optional(),
  curve: z.string().optional(), publication_date: z.string().optional(), method: z.string().optional(),
}).strict();
const FredItem = z.object({
  group: z.string(), id: z.string(), series_id: z.string(), title: z.string(), value: z.number().nullable(),
  units: z.string(), observation_date: z.string().nullable(), knowledge_start_date: z.string().nullable(),
  frequency: z.string(), source_agency: z.string(), usage_rights: z.string(), quality_flags: z.array(z.string()),
  class: z.literal("OBSERVED"),
}).strict();
export type FredItem = z.infer<typeof FredItem>;

const UnavailableSpread = z.object({ state: z.literal("UNAVAILABLE"), reason: z.string(), note: z.string() }).strict();
/** A dated spread: yield at an observed operation price minus the same-day interpolated par curve. */
const ObservedSpread = z.object({
  state: z.literal("DERIVED"), reason: z.null(), value: z.number(), unit: z.literal("bp"), yield: z.number(),
  yield_basis: z.string(), price: z.number(), price_kind: z.string(), source: z.string(), operation_date: z.string(),
  settlement_date: z.string(), curve: z.string(), curve_date: z.string(), par_yield: z.number(),
  tenors: z.array(z.string()), note: z.string(),
}).strict();
export type ObservedSpread = z.infer<typeof ObservedSpread>;
const NyFedRate = z.object({ id: z.string(), label: z.string(), value: z.number(), unit: z.string(), effective_date: z.string(),
  volume_billions: z.number().nullable().optional(), p1: z.number().nullable().optional(), p99: z.number().nullable().optional(),
  target_from: z.number().nullable().optional(), target_to: z.number().nullable().optional(), class: z.string(), source: z.string() }).strict();
export type NyFedRate = z.infer<typeof NyFedRate>;
const BreadthCategory = z.object({ state: z.string(), reason: z.string().nullable().optional(), trade_date: z.string().nullable().optional(),
  rows: z.array(z.record(z.unknown())) }).passthrough();
const Breadth = z.object({ state: z.string(), reason: z.string().nullable(), categories: z.record(BreadthCategory) }).passthrough();

export const RatesCurveSchema = z.object({
  schema_version: z.literal("screener-rates-curve/1.0.0"), universe: z.literal("BONDS"), generated_at: z.string(),
  instrument_id: z.string().nullable(), nominal: Curve, real: Curve,
  spreads: z.array(z.object({ id: z.string(), long_tenor: z.string(), short_tenor: z.string(), formula: z.string(),
    value_bp: z.number().nullable(), publication_date: z.string().nullable(), class: z.literal("DERIVED") }).strict()),
  shape: z.object({ state: z.enum(["UPWARD_SLOPING", "INVERTED", "FLAT_OR_MIXED", "UNAVAILABLE"]), rule: z.string(),
    publication_date: z.string().nullable(), class: z.literal("DERIVED").optional() }).strict(),
  breakevens: z.object({ state: z.string(), reason: z.string().nullable(), publication_date: z.string().optional(),
    method: z.string().optional(), items: z.array(z.object({ tenor: z.string(), nominal: z.number(), real: z.number(),
      value: z.number() }).strict()) }).strict(),
  selected: z.object({
    instrument_id: z.string(), cusip: z.string(), description: z.string(), security_type: z.string(), maturity: z.string(),
    category: z.string().optional(),
    years_to_maturity: z.number(), reference: Reference, indicative: Field.nullable(), auction_yield: Field,
    auction_real_yield: Field, spread: z.union([ObservedSpread, UnavailableSpread]),
  }).strict().nullable(),
  policy: z.object({ state: z.string(), reason: z.string().nullable(), items: z.array(FredItem) }).strict(),
  credit: z.object({ state: z.string(), reason: z.string().nullable(), items: z.array(FredItem), note: z.string() }).strict(),
  finra: z.object({
    trace: z.object({ source: z.string(), state: z.string(), reason: z.string(), corporate_coverage: z.string(),
      agency_coverage: z.string() }).strict(),
    aggregates: z.object({ state: z.string(), reason: z.string().nullable(), trade_date: z.string().nullable().optional(),
      rows: z.array(z.record(z.unknown())).optional() }).passthrough(),
    breadth: Breadth.optional(),
  }).strict(),
  nyfed: z.object({ state: z.string().nullable(), reason: z.string().nullable(), items: z.array(NyFedRate) }).passthrough().optional(),
  soma: z.object({ state: z.string(), as_of: z.string().nullable(), counts: z.record(z.number()) }).passthrough().optional(),
  sources: z.array(Source),
}).strict();
export type RatesCurvePayload = z.infer<typeof RatesCurveSchema>;

export async function fetchBondPreview(instrumentId: string, filters: ScreenerFilter[], signal?: AbortSignal) {
  const query = new URLSearchParams({ instrument: instrumentId, universe: "BONDS" });
  if (filters.length) query.set("filters", JSON.stringify(filters));
  const payload = await fetchJson(`/screener/preview?${query}`, BondPreviewSchema, { signal });
  // Request identity guard: a response for another security is never rendered.
  if (payload.instrument.instrument_id !== instrumentId) throw new Error("BOND_PREVIEW_IDENTITY_MISMATCH");
  return payload;
}

export async function fetchRatesCurve(instrumentId: string | null, signal?: AbortSignal) {
  const query = new URLSearchParams({ universe: "BONDS" });
  if (instrumentId) query.set("instrument", instrumentId);
  const payload = await fetchJson(`/screener/rates-curve?${query}`, RatesCurveSchema, { signal });
  if (payload.instrument_id !== instrumentId) throw new Error("RATES_CURVE_IDENTITY_MISMATCH");
  return payload;
}
