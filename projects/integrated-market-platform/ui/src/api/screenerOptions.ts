import { z } from "zod";
import { fetchJson } from "./fetchJson";
import type { ScreenerUniverse } from "./screener";

// S7 selected-underlying option chain (`screener-options/1.0.0`). The backend
// normalizes provider text once; values here are typed numbers or null
// (unavailable), never strings to parse. A malformed payload is rejected.
const Num = z.number().finite();
const OptionsState = z.enum(["CURRENT_SNAPSHOT", "STALE", "MARKET_CLOSED", "NOT_CONFIGURED", "NOT_ENTITLED",
  "PROVIDER_UNAVAILABLE", "NO_CHAIN", "UNAVAILABLE"]);
export type OptionsState = z.infer<typeof OptionsState>;
const IsoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const Contract = z.object({
  option_id: z.string(), provider_symbol: z.string(), type: z.enum(["CALL", "PUT"]), expiration: IsoDate, dte: z.number().int(),
  strike: Num, bid: Num.nullable(), ask: Num.nullable(), mid: Num.nullable(), spread: Num.nullable(), spread_pct: Num.nullable(),
  last: Num.nullable(), volume: z.number().int().nonnegative().nullable(), open_interest: z.number().int().nonnegative().nullable(),
  volume_oi_ratio: Num.nullable(), iv: Num.positive().nullable(), delta: Num.min(-1).max(1).nullable(), gamma: Num.nullable(),
  theta: Num.nullable(), vega: Num.nullable(), rho: Num.nullable(), last_trade_at: z.string().nullable(),
  quality_flags: z.array(z.string()),
});
export type OptionContractRow = z.infer<typeof Contract>;
const Brief = z.object({
  option_id: z.string(), provider_symbol: z.string(), type: z.enum(["CALL", "PUT"]), expiration: IsoDate, strike: Num,
  volume: z.number().int().nullable(), open_interest: z.number().int().nullable(), volume_oi_ratio: Num.nullable(),
  iv: Num.nullable(), share_of_side_volume_pct: Num.nullable(),
});
export type OptionBrief = z.infer<typeof Brief>;
const NearestStrike = z.object({
  expiration: IsoDate.nullable(), strike: Num, basis_price: Num, distance: Num, distance_pct: Num, exact: z.boolean(),
  call_iv: Num.nullable(), put_iv: Num.nullable(), call_mid: Num.nullable(), put_mid: Num.nullable(),
});
const Analytics = z.object({
  contracts: z.number().int(), calls: z.number().int(), puts: z.number().int(), expirations: z.number().int(),
  nearest_expiration: IsoDate.nullable(),
  call_volume: z.number().int().nullable(), put_volume: z.number().int().nullable(), total_volume: z.number().int().nullable(),
  put_call_volume_ratio: Num.nullable(), call_put_volume_ratio: Num.nullable(),
  call_open_interest: z.number().int().nullable(), put_open_interest: z.number().int().nullable(),
  total_open_interest: z.number().int().nullable(), put_call_oi_ratio: Num.nullable(),
  volume_reported: z.number().int(), open_interest_reported: z.number().int(), iv_reported: z.number().int(),
  two_sided: z.number().int(), median_spread_pct: Num.nullable(),
  most_active: z.array(Brief), largest_open_interest: z.array(Brief), nearest_strike: NearestStrike.nullable(),
});
export type OptionsAnalytics = z.infer<typeof Analytics>;
const Fields = z.object({ bid: z.boolean(), ask: z.boolean(), last: z.boolean(), volume: z.boolean(), open_interest: z.boolean(),
  iv: z.boolean(), delta: z.boolean(), gamma: z.boolean(), theta: z.boolean(), vega: z.boolean(), rho: z.boolean() });
export type OptionsFields = z.infer<typeof Fields>;
const OptionsSchema = z.object({
  schema_version: z.literal("screener-options/1.0.0"), generated_at: z.string().nullable(),
  instrument_id: z.string(), universe: z.enum(["US_EQUITIES", "US_ETFS"]), symbol: z.string(), view: z.enum(["chain", "summary"]),
  market_session: z.string(), capability: z.record(z.string()),
  provider: z.object({ id: z.string(), label: z.string(), delivery: z.string() }).nullable(),
  state: OptionsState, reason: z.string().nullable(),
  clock: z.object({ fetched_at: z.string().nullable(), age_ms: z.number().nonnegative(), provider_as_of: z.string().nullable(),
    latest_contract_trade_at: z.string().nullable(), refresh_after_s: z.number(), stale_after_s: z.number(),
    provider_latency_ms: Num.nullable(), provider_cache_hit: z.boolean() }).nullable(),
  underlying: z.object({ price: Num.positive(), source: z.string(), state: z.string(), as_of: z.string().nullable() }).nullable(),
  completeness: z.object({ provider_rows: z.number().int(), usable: z.number().int(), dropped: z.number().int(),
    dropped_reasons: z.record(z.number().int()), expired_excluded: z.number().int(), unmapped_columns: z.array(z.string()) }).nullable(),
  quality_flags: z.array(z.string()), fields_supplied: Fields.nullable(),
  expirations: z.array(z.object({ expiration: IsoDate, dte: z.number().int().nonnegative(), contracts: z.number().int(), strikes: z.number().int(),
    call_volume: z.number().int().nullable(), put_volume: z.number().int().nullable() })),
  selected_expiration: IsoDate.nullable(), summary: Analytics.nullable(), expiry_summary: Analytics.nullable(),
  contracts: z.array(Contract),
}).superRefine((payload, context) => {
  // A contract row must belong to the selected, listed, non-expired expiry.
  const listed = new Set(payload.expirations.map((item) => item.expiration));
  if (payload.selected_expiration && !listed.has(payload.selected_expiration)) context.addIssue({ code: "custom", message: "SELECTED_EXPIRATION_UNLISTED" });
  if (payload.contracts.some((row) => row.expiration !== payload.selected_expiration || row.dte < 0)) context.addIssue({ code: "custom", message: "CONTRACT_EXPIRATION_MISMATCH" });
});
export type OptionsPayload = z.infer<typeof OptionsSchema>;
export type OptionsView = "chain" | "summary";

export async function fetchScreenerOptions(instrumentId: string, { universe, view, expiration, snapshotId, signal }:
  { universe: ScreenerUniverse; view: OptionsView; expiration?: string | null; snapshotId?: string | null; signal?: AbortSignal }) {
  const query = new URLSearchParams({ instrument: instrumentId, universe, view });
  if (expiration) query.set("expiration", expiration);
  if (snapshotId) query.set("snapshot", snapshotId);
  const payload = await fetchJson(`/screener/options?${query}`, OptionsSchema, { signal });
  // Identity guard: a chain for another instrument, universe, or view is never rendered.
  if (payload.instrument_id !== instrumentId || payload.universe !== universe || payload.view !== view) throw new Error("OPTIONS_IDENTITY_MISMATCH");
  return payload;
}
