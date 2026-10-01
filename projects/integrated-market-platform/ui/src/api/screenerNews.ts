import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import { RemedySchema } from "./screenerSetup";
import type { ScreenerUniverse } from "./screener";

/**
 * S11 cross-universe News contracts. News is a view inside a universe, never a
 * universe. `null` always means unknown/missing, never zero; every derived value
 * (categories, matches, sentiment, attention) is labelled as such by the server.
 */
const Iso = z.string();
// Local copy: this module must not depend on runtime values of ./screener (tests mock it wholesale).
const ScreenerUniverseSchema = z.enum(["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"]);
// DELAYED: a working source whose free plan delays articles (NewsAPI Developer) — usable, never current.
export const ProviderStateSchema = z.enum(["CURRENT", "STALE", "DELAYED", "PENDING", "NOT_CONFIGURED", "LIVE_DISABLED",
  "RATE_LIMITED", "AUTH_FAILED", "ERROR", "NOT_APPLICABLE"]);
export type ProviderState = z.infer<typeof ProviderStateSchema>;
/** Plan terms the server states for a provider (cost, quota, timing, use restriction). */
const ProviderTerms = z.object({
  plan: z.string().optional(), restriction: z.string().optional(), timing: z.string().optional(),
  quota: z.string().optional(), runtime: z.string().optional(), cost_usd: z.number().optional(),
}).passthrough();
const ProviderStatus = z.object({
  id: z.string(), label: z.string(),
  kind: z.enum(["NEWS", "OFFICIAL_RELEASE", "OFFICIAL_FILING", "SENTIMENT", "AI"]),
  state: ProviderStateSchema, reason: z.string().nullable(), fetched_at: Iso.nullable(),
  item_count: z.number().nullable(), scope: z.enum(["UNIVERSE", "INSTRUMENT"]),
  terms: ProviderTerms.optional(),
  /** Plain-language fix for a degraded state; absent when the provider works or needs no operator step. */
  remedy: RemedySchema.nullable().optional(),
}).passthrough();
export type ProviderStatus = z.infer<typeof ProviderStatus>;
const Category = z.object({ id: z.string(), label: z.string(),
  group: z.enum(["CORPORATE", "REGULATORY", "MACRO", "CRYPTO", "FILING"]) }).passthrough();
export type NewsCategory = z.infer<typeof Category>;
const SourceType = z.enum(["NEWS", "OFFICIAL_RELEASE", "OFFICIAL_FILING"]);
const StorySource = z.object({
  provider_id: z.string(), provider_label: z.string(), publisher: z.string(), url: z.string().nullable(),
  published_at: Iso.nullable(), retrieved_at: Iso, source_type: SourceType,
}).passthrough();
export type StorySource = z.infer<typeof StorySource>;
const MatchBasis = z.enum(["EXACT_TICKER", "PROVIDER_TICKER", "EXACT_CUSIP", "EXACT_ENTITY", "ASSET_MATCH",
  "PAIR_MATCH", "VENUE_MATCH", "UNDERLYING_MATCH", "MACRO_CONTEXT", "ISSUER_MATCH", "AMBIGUOUS"]);
const Match = z.object({ instrument_id: z.string().nullable(), symbol: z.string(), basis: MatchBasis,
  confidence: z.enum(["EXACT", "CONTEXT", "AMBIGUOUS"]), term: z.string().nullable() }).passthrough();
export type NewsMatch = z.infer<typeof Match>;
const SentimentLabel = z.enum(["POSITIVE", "NEUTRAL", "NEGATIVE"]);
const StorySentiment = z.object({
  state: z.enum(["SCORED", "NOT_SCORED", "NOT_CONFIGURED", "UNAVAILABLE", "ERROR"]),
  label: SentimentLabel.nullable(),
  probabilities: z.object({ positive: z.number(), neutral: z.number(), negative: z.number() }).passthrough().nullable(),
  model_id: z.string().nullable(),
  /** IMP_DERIVED_FINBERT: classified locally by IMP, never supplied by a news source. */
  basis: z.string().optional(), reason: z.string().optional(),
}).passthrough();
export type StorySentiment = z.infer<typeof StorySentiment>;
const Story = z.object({
  story_id: z.string(), headline: z.string(), summary: z.string().nullable(), url: z.string().nullable(),
  published_at: Iso.nullable(), published_time_quality: z.enum(["KNOWN", "INFERRED_LOW_CONFIDENCE", "UNKNOWN"]),
  latest_published_at: Iso.nullable(), first_retrieved_at: Iso, source_type: SourceType,
  sources: z.array(StorySource), source_count: z.number(), provider_count: z.number(),
  categories: z.array(Category), matches: z.array(Match), sentiment: StorySentiment, quality_flags: z.array(z.string()),
}).passthrough();
export type NewsStory = z.infer<typeof Story>;
const SentimentModelStatus = z.object({
  state: z.enum(["CURRENT", "NOT_CONFIGURED", "UNAVAILABLE", "ERROR"]), reason: z.string().nullable(),
  model_id: z.string().nullable(), model_revision: z.string().nullable(), loaded: z.boolean(),
  remedy: RemedySchema.nullable().optional(),
}).passthrough();
export type SentimentModelStatus = z.infer<typeof SentimentModelStatus>;
export const NEWS_WINDOWS = ["1h", "4h", "24h", "72h"] as const;
export type NewsWindowId = (typeof NEWS_WINDOWS)[number];
const Window = z.object({ id: z.enum(NEWS_WINDOWS), start: Iso, end: Iso }).passthrough();
const FeedState = z.enum(["CURRENT", "PARTIAL", "PENDING", "NOT_CONFIGURED", "UNAVAILABLE"]);
export type NewsFeedState = z.infer<typeof FeedState>;
export const NEWS_SORTS = ["newest", "oldest", "sources", "relevance"] as const;
const Brief = z.object({
  generated_at: Iso, window: Window, method: z.string(),
  story_count: z.number(), headline_count: z.number(), source_count: z.number(),
  missing_providers: z.array(z.string()),
  groups: z.array(z.object({ category: Category, story_count: z.number(), source_count: z.number(),
    latest_published_at: Iso.nullable(), story_ids: z.array(z.string()) }).passthrough()),
  uncategorized_count: z.number(), coverage_note: z.string(),
}).passthrough();
export type NewsBrief = z.infer<typeof Brief>;

export const NewsFeedSchema = z.object({
  schema_version: z.literal("screener-news/1.0.0"),
  generated_at: Iso, universe: ScreenerUniverseSchema, window: Window, state: FeedState, reason: z.string().nullable(),
  /** The one step behind the feed state (e.g. start OpenD when the ETF/Futures catalog is down). */
  remedy: RemedySchema.nullable().optional(),
  providers: z.array(ProviderStatus), sentiment_model: SentimentModelStatus,
  filters: z.object({
    sources: z.array(z.object({ id: z.string(), label: z.string(), count: z.number() }).passthrough()),
    categories: z.array(z.object({ id: z.string(), label: z.string(), group: z.string(), count: z.number() }).passthrough()),
    sentiment: z.object({ enabled: z.boolean(), reason: z.string().nullable(),
      /** Partial filtering: scored/unscored over the window; unscored stories an applied filter hid. */
      scored: z.number().optional(), unscored: z.number().optional(), hidden_unscored: z.number().optional(),
      /** Stories past this many in a window are never scored. */
      scored_cap: z.number().optional(),
      counts: z.object({ positive: z.number(), neutral: z.number(), negative: z.number() }).passthrough().optional(),
    }).passthrough(),
    applied: z.object({ source: z.string().nullable(), category: z.string().nullable(), sentiment: z.string().nullable(),
      instrument: z.string().nullable() }).passthrough(),
  }).passthrough(),
  sorts: z.array(z.object({ id: z.enum(NEWS_SORTS), label: z.string() }).passthrough()),
  sort: z.string(), result_count: z.number(), headline_count: z.number(),
  /** Stories published after `since`, before filters; null when `since` was not sent. */
  new_count: z.number().nullable().optional(),
  offset: z.number(), limit: z.number(), has_more: z.boolean(),
  stories: z.array(Story), brief: Brief.nullable(),
}).passthrough();
export type NewsFeed = z.infer<typeof NewsFeedSchema>;

/** Paid provider only: today's usage against the hard daily limits (UTC day). */
const Budget = z.object({ day: z.string(), requests: z.number(), max_requests: z.number(), tokens: z.number(),
  max_tokens: z.number() }).passthrough();
export type SynthesisBudget = z.infer<typeof Budget>;
/** One operator-selectable synthesis engine: its models (first = default) and whether it can run now. */
const Engine = z.object({ id: z.string(), label: z.string(), runtime: z.enum(["LOCAL_MODEL", "PAID_API"]),
  models: z.array(z.string()), default_model: z.string().nullable(),
  state: z.enum(["AVAILABLE", "NOT_CONFIGURED"]), reason: z.string().nullable() }).passthrough();
export type SynthesisEngine = z.infer<typeof Engine>;
const AiStatus = z.object({ state: z.enum(["AVAILABLE", "NOT_CONFIGURED", "UNAVAILABLE"]), reason: z.string().nullable(),
  provider_id: z.string().nullable(), model_id: z.string().nullable(),
  runtime: z.enum(["LOCAL_MODEL", "PAID_API"]).nullable().optional(),
  budget: Budget.nullable().optional(),
  /** The operator's choice ("auto" until one is picked) and every engine the picker offers. */
  engine: z.string().optional(), engine_model: z.string().nullable().optional(),
  engine_source: z.enum(["OPERATOR", "ENVIRONMENT", "AUTOMATIC"]).optional(),
  engines: z.array(Engine).optional() }).passthrough();
export type AiStatus = z.infer<typeof AiStatus>;

const TimelineBucket = z.object({ start: Iso, positive: z.number(), neutral: z.number(), negative: z.number(),
  unscored: z.number() }).passthrough();
export type SentimentTimelineBucket = z.infer<typeof TimelineBucket>;
const AnalysisItem = z.object({ text: z.string(), source: z.string(), as_of: Iso.nullable(), story_id: z.string().nullable() }).passthrough();
export type NewsAnalysisItem = z.infer<typeof AnalysisItem>;
export const InstrumentNewsSchema = z.object({
  schema_version: z.literal("screener-news-instrument/1.0.0"),
  generated_at: Iso, universe: ScreenerUniverseSchema,
  instrument: z.object({ instrument_id: z.string(), symbol: z.string(), label: z.string() }).passthrough(),
  capability: z.object({ state: z.enum(["SUPPORTED", "PARTIAL", "NOT_CONFIGURED", "UNAVAILABLE"]), reason: z.string().nullable(),
    match_bases: z.array(MatchBasis), terms: z.array(z.string()) }).passthrough(),
  window: Window, state: FeedState, reason: z.string().nullable(), providers: z.array(ProviderStatus),
  coverage: z.object({ story_count: z.number(), headline_count: z.number(), source_count: z.number(),
    latest_published_at: Iso.nullable() }).passthrough(),
  stories: z.array(Story),
  sentiment: z.object({
    state: z.enum(["CURRENT", "PARTIAL", "NOT_CONFIGURED", "UNAVAILABLE", "INSUFFICIENT_DATA"]), reason: z.string().nullable(),
    model_id: z.string().nullable(),
    counts: z.object({ positive: z.number(), neutral: z.number(), negative: z.number() }).passthrough(),
    scored: z.number(), unscored: z.number(),
    dominant: z.enum(["POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED"]).nullable(),
    latest: z.object({ story_id: z.string(), label: z.string(), published_at: Iso.nullable() }).passthrough().nullable(),
    method: z.string(),
    /** Hourly story counts by headline tone over the instrument window, oldest first. */
    timeline: z.array(TimelineBucket).optional(), timeline_untimed: z.number().optional(),
  }).passthrough(),
  catalysts: z.array(z.object({ category: Category, story_count: z.number(), latest_published_at: Iso.nullable(),
    story_ids: z.array(z.string()) }).passthrough()),
  attention: z.object({
    state: z.enum(["CURRENT", "PARTIAL", "UNAVAILABLE"]), reason: z.string().nullable(), class: z.literal("DERIVED"),
    windows: z.array(z.object({ id: z.enum(["15m", "1h", "4h", "24h"]), headline_count: z.number(), story_count: z.number(),
      prior_headline_count: z.number().nullable() }).passthrough()),
    independent_sources: z.number(), latest_published_at: Iso.nullable(), method: z.string(),
  }).passthrough(),
  reaction: z.object({
    state: z.enum(["CURRENT", "UNAVAILABLE", "NOT_SUPPORTED"]), reason: z.string().nullable(),
    basis: z.string(), timeframe: z.string().nullable(), note: z.string(),
    items: z.array(z.object({
      story_id: z.string(), published_at: Iso,
      reference: z.object({ price: z.number(), bar_start: Iso.nullable() }).passthrough().nullable(),
      horizons: z.array(z.object({ id: z.enum(["+5m", "+15m", "+1h"]), change_pct: z.number().nullable(), price: z.number().nullable(),
        bar_end: Iso.nullable(), state: z.enum(["OBSERVED", "PENDING", "UNAVAILABLE"]) }).passthrough()),
    }).passthrough()),
  }).passthrough(),
  analysis: z.object({ observed: z.array(AnalysisItem), derived: z.array(AnalysisItem), insufficient: z.array(AnalysisItem) }).passthrough(),
  ai: AiStatus,
}).passthrough();
export type InstrumentNews = z.infer<typeof InstrumentNewsSchema>;

const Ref = z.object({ text: z.string(), refs: z.array(z.string()) }).passthrough();
export type SynthesisRefItem = z.infer<typeof Ref>;
export const SynthesisSchema = z.object({
  schema_version: z.literal("screener-news-synthesis/1.0.0"),
  state: z.enum(["CURRENT", "NOT_CONFIGURED", "UNAVAILABLE", "INSUFFICIENT_EVIDENCE", "INVALID_OUTPUT"]),
  reason: z.string().nullable(), epistemic_class: z.literal("AI_SYNTHESIS"), generated_at: Iso,
  provider_id: z.string().nullable(), model_id: z.string().nullable(), prompt_id: z.string(), prompt_version: z.string(),
  input_hash: z.string().nullable(), cache: z.enum(["HIT", "MISS"]).nullable(), story_ids: z.array(z.string()),
  runtime: z.enum(["LOCAL_MODEL", "PAID_API"]).nullable().optional(),
  coverage: z.object({ story_count: z.number(), synthesized_story_count: z.number().optional(), source_count: z.number(), window: Window,
    missing_providers: z.array(z.string()) }).passthrough(),
  synthesis: z.object({
    summary: z.string(), observed_facts: z.array(Ref), derived_context: z.array(Ref), uncertainties: z.array(z.string()),
    conflicting_evidence: z.array(Ref), potential_market_relevance: z.array(Ref),
  }).passthrough().nullable(),
  /** The headlines the model was given, in order; every ref resolves here whatever feed the UI has loaded. */
  stories: z.array(z.object({ story_id: z.string(), headline: z.string(), url: z.string().nullable(),
    published_at: Iso.nullable() }).passthrough()).optional(),
  /** Usage after this call, so the budget line moves with the click. */
  budget: Budget.nullable().optional(),
}).passthrough();
export type NewsSynthesis = z.infer<typeof SynthesisSchema>;

export const SynthesisPreviewSchema = z.object({
  schema_version: z.literal("screener-news-synthesis-preview/1.0.0"),
  ai: AiStatus,
  /** Paid runtime only: the worst-case tokens a click reserves; a cached input costs nothing. */
  estimate: z.object({ story_count: z.number(), tokens: z.number().nullable(), cached: z.boolean(),
    /** Every story the scope matched; more than `story_count` means the synthesis input is capped. */
    available_story_count: z.number().optional() }).passthrough().nullable(),
}).passthrough();
export type SynthesisPreview = z.infer<typeof SynthesisPreviewSchema>;

export type NewsFeedParams = {
  universe: ScreenerUniverse;
  window?: NewsWindowId;
  sort?: string | null;
  source?: string | null;
  category?: string | null;
  sentiment?: string | null;
  instrument?: string | null;
  offset?: number;
  limit?: number;
  view?: "feed" | "brief";
  /** Last-view time: the response counts stories published after it (`new_count`). */
  since?: string | null;
};
export const NEWS_PAGE_LIMIT = 100;

export async function fetchScreenerNews(params: NewsFeedParams, signal?: AbortSignal) {
  const offset = params.offset ?? 0;
  const query = new URLSearchParams({ universe: params.universe, window: params.window ?? "24h",
    offset: String(offset), limit: String(params.limit ?? NEWS_PAGE_LIMIT), view: params.view ?? "feed" });
  if (params.sort) query.set("sort", params.sort);
  if (params.source) query.set("source", params.source);
  if (params.category) query.set("category", params.category);
  if (params.sentiment) query.set("sentiment", params.sentiment);
  if (params.instrument) query.set("instrument", params.instrument);
  if (params.since) query.set("since", params.since);
  const feed = await fetchJson(`/screener/news?${query}`, NewsFeedSchema, signal ? { signal } : undefined);
  // Identity guard: a page for another universe or offset is never appended.
  if (feed.universe !== params.universe || feed.offset !== offset) throw new Error("SCREENER_NEWS_IDENTITY_MISMATCH");
  return feed;
}

export async function fetchInstrumentNews(universe: ScreenerUniverse, instrumentId: string, compact: boolean, signal?: AbortSignal) {
  const query = new URLSearchParams({ universe, instrument: instrumentId });
  if (compact) query.set("compact", "1");
  const payload = await fetchJson(`/screener/news/instrument?${query}`, InstrumentNewsSchema, signal ? { signal } : undefined);
  // Identity guard: a response for another instrument or universe is never rendered.
  if (payload.instrument.instrument_id !== instrumentId || payload.universe !== universe) throw new Error("SCREENER_NEWS_IDENTITY_MISMATCH");
  return payload;
}

export type SynthesisRequest = { universe: ScreenerUniverse; scope: "INSTRUMENT" | "UNIVERSE"; instrument?: string; window?: NewsWindowId };

/** Explicit operator action only; never called on render. Aborted when the selection changes. */
export function postNewsSynthesis(body: SynthesisRequest, signal?: AbortSignal) {
  return postJson("/screener/news/synthesis", body, SynthesisSchema, signal ? { signal } : undefined);
}

/** Operator choice of synthesis engine and model (server catalog only); returns the new AI status. Calls no model. */
export function postSynthesisEngine(engine: string, model: string | null) {
  return postJson("/screener/news/synthesis/engine", { engine, model }, AiStatus);
}

/** AI status and pre-click cost; the server never calls a model for it. */
export function fetchSynthesisPreview(request: SynthesisRequest, signal?: AbortSignal) {
  const query = new URLSearchParams({ universe: request.universe, scope: request.scope, window: request.window ?? "24h" });
  if (request.instrument) query.set("instrument", request.instrument);
  return fetchJson(`/screener/news/synthesis/preview?${query}`, SynthesisPreviewSchema, signal ? { signal } : undefined);
}

const ActivityRow = z.object({
  count: z.number(), unscored: z.number(), latest_at: Iso.nullable(),
  tone: z.object({ positive: z.number(), neutral: z.number(), negative: z.number() }),
});
export type NewsActivityRow = z.infer<typeof ActivityRow>;
export const NewsActivitySchema = z.object({
  schema_version: z.literal("screener-news-activity/1.0.0"), generated_at: Iso, universe: z.string(),
  window: Window, state: FeedState, reason: z.string().nullable(), sentiment_state: z.string(),
  /** Only instruments with at least one story in the window are present. */
  instruments: z.record(ActivityRow),
});
export type NewsActivity = z.infer<typeof NewsActivitySchema>;
/** The server caps one badge request at a grid page. */
export const NEWS_ACTIVITY_MAX_IDS = 200;

export function fetchNewsActivity(universe: ScreenerUniverse, instrumentIds: string[], signal?: AbortSignal) {
  const params = new URLSearchParams({ universe, window: "24h", ids: instrumentIds.slice(0, NEWS_ACTIVITY_MAX_IDS).join(",") });
  return fetchJson(`/screener/news/activity?${params}`, NewsActivitySchema, signal ? { signal } : undefined);
}
