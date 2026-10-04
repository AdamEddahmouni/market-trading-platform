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

/** Explicit operator action; GET is intentionally not used for inference. */
export function postAiScreener(scope: AiScreenerScope, signal?: AbortSignal) {
  return postJson("/screener/ai-screener", scope, AiScreenerResultSchema, signal ? { signal } : undefined);
}
