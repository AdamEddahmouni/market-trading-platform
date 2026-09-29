import { z } from "zod";
import { fetchJson } from "./fetchJson";
import type { ScreenerUniverse } from "./screener";

/**
 * S12 Institutional, Whale, Congressional & Government intelligence contracts.
 * An intelligence layer over the active universe, never a universe. Evidence
 * families stay separate and are never blended into a score; `null` means
 * unknown, never zero. Every disclosure keeps its own clocks.
 */
const Iso = z.string();
// Local copy: this module must not depend on runtime values of ./screener (tests mock it wholesale).
const Universe = z.enum(["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"]);
const SCHEMA = z.literal("screener-participants/1.0.0");

export const PARTICIPANT_STATES = ["PUBLICATION_CURRENT", "CURRENT_AS_FILED", "CURRENT", "STALE", "PARTIAL", "PENDING",
  "NOT_CONFIGURED", "LIVE_DISABLED", "UNAVAILABLE", "SOURCE_ERROR", "NO_MATCH", "NO_DISCLOSURES", "NOT_APPLICABLE",
  "NOT_LOADED", "SEE_ORDER_FLOW"] as const;
const State = z.string();
const Provider = z.object({
  id: z.string(), label: z.string(), family: z.enum(["INSTITUTIONAL", "WHALE", "CONGRESSIONAL", "GOVERNMENT"]),
  scope: z.enum(["UNIVERSE", "INSTRUMENT"]), state: State, reason: z.string().nullable(), fetched_at: Iso.nullable(),
  published: z.string().nullable(), item_count: z.number().nullable(), cadence: z.string(),
  source_url: z.string().optional(),
}).passthrough();
export type ParticipantProvider = z.infer<typeof Provider>;
const Amount = z.object({ min_amount: z.number().nullable(), max_amount: z.number().nullable(), display: z.string(),
  exact_value_disclosed: z.literal(false) }).passthrough();
export type DisclosedAmount = z.infer<typeof Amount>;

const CongressRow = z.object({
  id: z.string(), chamber: z.string(),
  member: z.object({ name: z.string(), state_district: z.string(), member_id: z.string() }).passthrough(),
  owner: z.string(), asset_description: z.string(), asset_type_code: z.string().nullable(),
  disclosed_ticker: z.string().nullable(), transaction_type: z.string(),
  transaction_date: z.string().nullable(), notification_date: z.string().nullable(), filing_date: z.string(),
  available_at: Iso.nullable(), available_basis: z.string(), retrieved_at: Iso.nullable(),
  amount: Amount.nullable(), disclosure_lag_days: z.number().nullable(), source_url: z.string(),
  quality_flags: z.array(z.string()),
  instrument: z.object({ instrument_id: z.string(), symbol: z.string(), basis: z.string(), confidence: z.string(),
    is_option: z.boolean() }).passthrough().optional(),
}).passthrough();
export type CongressTransaction = z.infer<typeof CongressRow>;

export const CONGRESS_WINDOWS = ["30d", "60d", "90d"] as const;
export const CONGRESS_SORTS = ["filed", "traded", "amount"] as const;
export const CongressViewSchema = z.object({
  schema_version: SCHEMA, generated_at: Iso, universe: Universe, view: z.literal("congress"),
  window: z.object({ id: z.enum(CONGRESS_WINDOWS), days: z.number(), since: z.string(), basis: z.string() }).passthrough(),
  state: State, reason: z.string().nullable(), providers: z.array(Provider),
  sorts: z.array(z.object({ id: z.string(), label: z.string() }).passthrough()), sort: z.string(),
  filters: z.object({
    transaction_types: z.array(z.object({ id: z.string(), count: z.number() }).passthrough()),
    amount_floors: z.array(z.number()),
    members: z.array(z.object({ id: z.string(), name: z.string(), state_district: z.string() }).passthrough()),
    applied: z.object({ transaction_type: z.string().nullable(), min_amount: z.number().nullable(),
      member: z.string().nullable() }).passthrough(),
  }).passthrough(),
  rows: z.array(CongressRow), result_count: z.number(), offset: z.number(), limit: z.number(), has_more: z.boolean(),
  coverage: z.record(z.unknown()), boundaries: z.array(z.string()), time_note: z.string(), neutrality_note: z.string(),
}).passthrough();
export type CongressView = z.infer<typeof CongressViewSchema>;

export const OWNERSHIP_WINDOWS = ["1d", "3d", "5d", "10d"] as const;
export const OwnershipViewSchema = z.object({
  schema_version: SCHEMA, generated_at: Iso, universe: Universe, view: z.literal("ownership"),
  window: z.object({ id: z.enum(OWNERSHIP_WINDOWS), business_days: z.number() }).passthrough(),
  state: State, reason: z.string().nullable(), providers: z.array(Provider),
  families: z.array(z.object({ id: z.string(), label: z.string() }).passthrough()),
  family_counts: z.record(z.number()).optional(),
  applied: z.object({ family: z.string().nullable() }).passthrough(),
  sorts: z.array(z.object({ id: z.string(), label: z.string() }).passthrough()), sort: z.string(),
  rows: z.array(z.object({
    accession: z.string(), form_type: z.string(), family: z.string(), is_amendment: z.boolean(), filed_date: z.string(),
    instrument: z.object({ instrument_id: z.string(), symbol: z.string() }).passthrough(),
    issuer_name: z.string(), filers: z.array(z.string()), filer_count: z.number(),
    match: z.object({ basis: z.string(), confidence: z.string(), role_basis: z.string().optional() }).passthrough(),
    source_url: z.string(),
  }).passthrough()),
  result_count: z.number(), offset: z.number(), limit: z.number(), has_more: z.boolean(),
  coverage: z.record(z.unknown()).nullable(), boundaries: z.array(z.string()), time_note: z.string(),
}).passthrough();
export type OwnershipView = z.infer<typeof OwnershipViewSchema>;

const Category = z.object({
  id: z.string(), label: z.string(), long: z.number().nullable(), short: z.number().nullable(),
  spreading: z.number().nullable(), change_long: z.number().nullable(), change_short: z.number().nullable(),
  net: z.number().nullable(), net_change: z.number().nullable(),
  traders_long: z.number().nullable(), traders_short: z.number().nullable(),
}).passthrough();
const PositioningReport = z.object({
  root: z.string(), report: z.string(), report_label: z.string(), cftc_contract_market_code: z.string(),
  market_name: z.string(), report_date: z.string(), publication_time: Iso, publication_basis: z.string(),
  open_interest: z.number().nullable(), change_open_interest: z.number().nullable(), categories: z.array(Category),
  net_method: z.string(), source_url: z.string(),
}).passthrough();
export type PositioningReport = z.infer<typeof PositioningReport>;
export const PositioningViewSchema = z.object({
  schema_version: SCHEMA, generated_at: Iso, universe: Universe, view: z.literal("positioning"),
  state: State, reason: z.string().nullable(), providers: z.array(Provider),
  groups: z.array(z.object({ report: z.string(), label: z.string(), rows: z.array(PositioningReport) }).passthrough()),
  coverage: z.object({ universe_roots: z.number(), mapped_roots: z.number(), unmapped_roots: z.array(z.string()) }).passthrough(),
  boundaries: z.array(z.string()), time_note: z.string(),
}).passthrough();
export type PositioningView = z.infer<typeof PositioningViewSchema>;

const Section = z.object({ state: State, reason: z.string().nullable() }).passthrough();
export type ParticipantSection = z.infer<typeof Section> & Record<string, unknown>;
export const PARTICIPANT_LENSES = ["institutional", "congress_gov"] as const;
export type ParticipantLens = (typeof PARTICIPANT_LENSES)[number];
export const ParticipantInstrumentSchema = z.object({
  schema_version: SCHEMA, generated_at: Iso, universe: Universe, lens: z.enum(PARTICIPANT_LENSES), compact: z.boolean(),
  instrument: z.object({ instrument_id: z.string(), symbol: z.string(), label: z.string() }).passthrough(),
  state: State, providers: z.array(Provider), sections: z.record(Section),
  identity: z.object({ ticker: z.string().nullable(), cik: z.string().nullable(), cusips: z.array(z.string()) }).passthrough().optional(),
  boundaries: z.array(z.string()), neutrality_note: z.string().optional(),
}).passthrough();
export type ParticipantInstrument = z.infer<typeof ParticipantInstrumentSchema>;

export type CongressParams = { universe: ScreenerUniverse; window?: string | null; type?: string | null;
  minAmount?: number | null; member?: string | null; sort?: string | null; offset?: number };
export type OwnershipParams = { universe: ScreenerUniverse; window?: string | null; family?: string | null;
  sort?: string | null; offset?: number };
export const PARTICIPANT_PAGE_LIMIT = 100;

const init = (signal?: AbortSignal) => (signal ? { signal } : undefined);
function guard<T extends { universe: string }>(payload: T, universe: ScreenerUniverse, offset?: number) {
  // Identity guard: a page for another universe or offset is never rendered or appended.
  if (payload.universe !== universe || (offset != null && (payload as { offset?: number }).offset !== offset)) {
    throw new Error("SCREENER_PARTICIPANTS_IDENTITY_MISMATCH");
  }
  return payload;
}

export async function fetchCongressView(params: CongressParams, signal?: AbortSignal) {
  const offset = params.offset ?? 0;
  const query = new URLSearchParams({ universe: params.universe, window: params.window ?? "60d",
    offset: String(offset), limit: String(PARTICIPANT_PAGE_LIMIT) });
  if (params.type) query.set("type", params.type);
  if (params.minAmount) query.set("min_amount", String(params.minAmount));
  if (params.member) query.set("member", params.member);
  if (params.sort) query.set("sort", params.sort);
  return guard(await fetchJson(`/screener/participants/congress?${query}`, CongressViewSchema, init(signal)), params.universe, offset);
}

export async function fetchOwnershipView(params: OwnershipParams, signal?: AbortSignal) {
  const offset = params.offset ?? 0;
  const query = new URLSearchParams({ universe: params.universe, window: params.window ?? "5d",
    offset: String(offset), limit: String(PARTICIPANT_PAGE_LIMIT) });
  if (params.family) query.set("family", params.family);
  if (params.sort) query.set("sort", params.sort);
  return guard(await fetchJson(`/screener/participants/ownership?${query}`, OwnershipViewSchema, init(signal)), params.universe, offset);
}

export async function fetchPositioningView(universe: ScreenerUniverse, signal?: AbortSignal) {
  const query = new URLSearchParams({ universe });
  return guard(await fetchJson(`/screener/participants/positioning?${query}`, PositioningViewSchema, init(signal)), universe);
}

export async function fetchParticipantInstrument(universe: ScreenerUniverse, instrumentId: string, lens: ParticipantLens,
  compact: boolean, signal?: AbortSignal) {
  const query = new URLSearchParams({ universe, instrument: instrumentId, lens });
  if (compact) query.set("compact", "1");
  const payload = await fetchJson(`/screener/participants/instrument?${query}`, ParticipantInstrumentSchema, init(signal));
  // Identity guard: a response for another instrument, universe, or lens is never rendered.
  if (payload.instrument.instrument_id !== instrumentId || payload.universe !== universe || payload.lens !== lens) {
    throw new Error("SCREENER_PARTICIPANTS_IDENTITY_MISMATCH");
  }
  return payload;
}
