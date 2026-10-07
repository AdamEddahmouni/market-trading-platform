import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import { AiStatusSchema } from "./screenerNews";
import type { ScreenerFilter, ScreenerUniverse } from "./screener";

const ScopeSchema = z.object({
  universe: z.enum(["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"]),
  search: z.string(), sort: z.string().nullable(), descending: z.boolean(), filters: z.array(z.object({
    id: z.string(), field: z.string(), operator: z.string(), value: z.union([z.number(), z.string(), z.array(z.number()), z.array(z.string())]),
  }).passthrough()),
}).passthrough();
export type AiScreenerScope = {
  universe: ScreenerUniverse;
  search: string;
  sort: string;
  descending: boolean;
  filters: ScreenerFilter[];
  result_set?: string | null;
  view?: string;
  screen?: string;
  settled?: boolean;
};

const EstimateSchema = z.object({ intake_count: z.number(), sufficient_count: z.number(), packet_bytes: z.number(),
  input_tokens: z.number(), tokens: z.number().nullable(), cached: z.boolean(), input_hash: z.string() }).passthrough();
const EvidenceSchema = z.object({ evidence_id: z.string(), capability: z.string(), instrument_id: z.string(), role: z.string(),
  source: z.string().nullable(), as_of: z.string().nullable(), delivery_mode: z.string(), freshness_status: z.string(),
  decision_admissibility: z.string(), valid_until: z.string().nullable(), weak_reasons: z.array(z.string()), facts: z.record(z.unknown()),
}).passthrough();
const NewsCoverageSchema = z.object({ state: z.string(), window: z.string(), story_count: z.number(), snapshot_at: z.string(),
  providers: z.array(z.object({ id: z.string(), state: z.string(), reason: z.string().nullable(), fetched_at: z.string().nullable().optional() }).passthrough()),
  sentiment: z.object({ state: z.string(), reason: z.string().nullable(), dominant: z.string().nullable(), model_id: z.string().nullable(),
    model_revision: z.string().nullable(), sentiment_version: z.string(), basis: z.string(), method: z.string(),
    counts: z.record(z.number()), scored: z.number(), unscored: z.number(), window: z.string() }).passthrough(),
  limitations: z.array(z.string()),
}).passthrough();
const AlignmentSchema = z.object({ kind: z.string(), method: z.string(), result: z.enum(["CONFIRMING", "CONFLICTING", "MIXED", "CONTEXT_ONLY", "UNKNOWN"]),
  observed_direction: z.string().nullable(), sentiment_refs: z.array(z.string()), news_refs: z.array(z.string()),
  comparator_ref: z.string().nullable(), cutoff: z.string(), alignment_id: z.string(), limitations: z.array(z.string()),
});
const CandidateEvidenceSchema = z.object({ instrument: z.record(z.string()), current_market_evidence: z.array(EvidenceSchema),
  reference_evidence: z.array(EvidenceSchema), blocked: z.array(z.record(z.unknown())), missing: z.array(z.object({ capability: z.string(), reason: z.string() }).passthrough()),
  weak: z.array(z.record(z.unknown())), sufficient: z.boolean(), news: NewsCoverageSchema.optional(), alignments: z.array(AlignmentSchema).optional(),
}).passthrough();
const SelectionSchema = z.object({ instrument_id: z.string(), rank: z.number(), rationale: z.string(), supporting_refs: z.array(z.string()),
  conflicting_refs: z.array(z.string()), weak_refs: z.array(z.string()), missing_capabilities: z.array(z.string()), uncertainties: z.array(z.string()),
}).passthrough();
const EvidenceSummarySchema = z.object({ sufficient: z.number(), blocked: z.number(), missing: z.number(), weak: z.number() }).passthrough();
export const AiScreenerPreviewSchema = z.object({ schema_version: z.literal("screener-ai-screener-preview/1.0.0"), ai: AiStatusSchema,
  scope: ScopeSchema, matched_count: z.number(), intake_count: z.number(), max_intake: z.number(), estimate: EstimateSchema.nullable(),
  evidence_summary: EvidenceSummarySchema, news_coverage: z.array(NewsCoverageSchema.extend({ instrument_id: z.string() })).optional(), decision_cutoff: z.string(), result_set: z.string().nullable().optional(),
  engine_fit: z.array(z.object({ engine: z.string(), fits: z.boolean().nullable(), packet_size: z.number().nullable(), context_window: z.number().nullable() })).optional(),
}).passthrough();
export type AiScreenerPreview = z.infer<typeof AiScreenerPreviewSchema>;

export const AiScreenerResultSchema = z.object({ schema_version: z.literal("screener-ai-screener/1.0.0"), state: z.string(), reason: z.string().nullable().optional(),
  scope: ScopeSchema, matched_count: z.number(), intake_count: z.number(), max_intake: z.number(), result_set: z.string().nullable().optional(),
  run_id: z.string(), decision_cutoff: z.string(), generated_at: z.string(), valid_until: z.string(), input_hash: z.string(),
  provider_id: z.string().nullable(), model_id: z.string().nullable(), runtime: z.string().nullable(), prompt_id: z.string(), prompt_version: z.string(), prompt_hash: z.string(),
  packet_bytes: z.number(), cache: z.enum(["HIT", "MISS"]), simulated: z.boolean(), tokens_input: z.number().nullable().optional(), tokens_output: z.number().nullable().optional(), latency_ms: z.number().nullable().optional(),
  evidence: z.array(CandidateEvidenceSchema), candidates: z.array(SelectionSchema), limitations: z.array(z.string()), coverage: z.record(z.number()),
}).passthrough();
export type AiScreenerResult = z.infer<typeof AiScreenerResultSchema>;

function queryFor(scope: AiScreenerScope) {
  const query = new URLSearchParams({ universe: scope.universe, search: scope.search, sort: scope.sort,
    descending: scope.descending ? "1" : "0", filters: JSON.stringify(scope.filters) });
  if (scope.result_set) query.set("result_set", scope.result_set);
  if (scope.view) query.set("view", scope.view);
  if (scope.screen) query.set("screen", scope.screen);
  return query;
}

/** Read-only status, scope reconstruction, and cost estimate; never calls a model. */
export function fetchAiScreenerPreview(scope: AiScreenerScope, signal?: AbortSignal) {
  return fetchJson(`/screener/ai-screener/preview?${queryFor(scope)}`, AiScreenerPreviewSchema, signal ? { signal } : undefined);
}

const RunStageSchema = z.object({ stage: z.string(), started_at: z.string(), elapsed_ms: z.number(), detail: z.record(z.unknown()) });
const RunSummarySchema = z.object({ state: z.string(), reason: z.string().nullable().optional(), candidate_run_id: z.string(),
  selected: z.array(z.object({ instrument_id: z.string(), rank: z.number() })), intake_count: z.number().nullable().optional(),
  cache: z.string().nullable().optional(), simulated: z.boolean().nullable().optional(), provider_id: z.string().nullable(), model_id: z.string().nullable(),
  runtime: z.string().nullable(), tokens_input: z.number().nullable().optional(), tokens_output: z.number().nullable().optional(),
  latency_ms: z.number().nullable().optional(), packet_bytes: z.number().nullable().optional(), decision_cutoff: z.string().nullable().optional(),
  valid_until: z.string().nullable().optional(), limitations: z.array(z.string()),
}).passthrough();
/** One tracked run. `run_id` identifies the run being watched; the stored candidate run is `summary.candidate_run_id`. */
export const AiScreenerRunSchema = z.object({ schema_version: z.literal("screener-ai-screener-run/1.0.0"), run_id: z.string(), account_id: z.string(),
  state: z.enum(["RUNNING", "COMPLETED", "FAILED"]), joined: z.boolean(), scope: ScopeSchema, stage: z.string().nullable(), stage_order: z.array(z.string()),
  stages: z.array(RunStageSchema), started_at: z.string(), finished_at: z.string().nullable(), elapsed_ms: z.number(),
  engine: z.object({ provider_id: z.string().nullable(), model_id: z.string().nullable(), runtime: z.string().nullable() }),
  timeout_seconds: z.number(), typical_latency_ms: z.number().nullable(), typical_latency_samples: z.number(),
  intake_count: z.number().nullable(), sufficient_count: z.number().nullable(), packet_bytes: z.number().nullable(),
  summary: RunSummarySchema.nullable(), result: AiScreenerResultSchema.nullable(), error: z.object({ code: z.string(), stage: z.string().nullable() }).nullable(),
}).passthrough();
export type AiScreenerRun = z.infer<typeof AiScreenerRunSchema>;
const RunBudgetSchema = z.object({ day: z.string(), tokens: z.number(), max_tokens: z.number(), requests: z.number(), max_requests: z.number(),
  headroom: z.number(), requests_left: z.number(), run_size: z.number().nullable(), run_size_basis: z.string().nullable(),
  runs_left: z.number().nullable(), resets_at: z.string() }).passthrough();
/** What the Screener shows at all times: engine state, budget in runs-left terms, the run in progress, the latest finished run. */
export const AiScreenerRunsSchema = z.object({ schema_version: z.literal("screener-ai-screener-runs/1.2.0"),
  state: z.enum(["RUNNING", "IDLE", "WAITING_FOR_BUDGET", "BLOCKED", "NOT_CONFIGURED"]),
  ai: z.object({ state: z.string().nullable(), reason: z.string().nullable(), provider_id: z.string().nullable(), model_id: z.string().nullable(), runtime: z.string().nullable() }),
  budget: RunBudgetSchema.nullable(), active: AiScreenerRunSchema.nullable(), latest: AiScreenerRunSchema.nullable() }).passthrough();
export type AiScreenerRuns = z.infer<typeof AiScreenerRunsSchema>;

function sorted(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sorted);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, item]) => [key, sorted(item)]));
  return value;
}

/** Identity of the Screener query a run answers. The list snapshot (`result_set`) is not part of it: the same query
 *  after a list refresh is still the same question, and a result states its own cutoff. */
export function aiScopeKey(scope: { universe: string; search: string; sort?: string | null; descending: boolean; filters: unknown; view?: unknown; screen?: unknown }) {
  return JSON.stringify(sorted({ universe: scope.universe, search: scope.search, sort: scope.sort ?? null, descending: scope.descending,
    filters: scope.filters, view: scope.view ?? "Overview", screen: scope.screen ?? "" }));
}

/** Explicit operator action; GET is intentionally not used for inference. Returns at once: the run continues on the
 *  server, and a run already in progress for this account is joined instead of starting a second one. */
export function postAiScreener(scope: AiScreenerScope, signal?: AbortSignal) {
  return postJson("/screener/ai-screener", scope, AiScreenerRunSchema, signal ? { signal } : undefined);
}

/** Read-only: the run in progress and the latest finished run for this account, without result bodies. */
export function fetchAiScreenerRuns(signal?: AbortSignal) {
  return fetchJson("/screener/ai-screener/runs/active", AiScreenerRunsSchema, signal ? { signal } : undefined);
}

/** Read-only: one tracked run, with its full result once finished. */
export function fetchAiScreenerRun(runId: string, signal?: AbortSignal) {
  return fetchJson(`/screener/ai-screener/runs/${encodeURIComponent(runId)}`, AiScreenerRunSchema, signal ? { signal } : undefined);
}
