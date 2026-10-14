import { z } from "zod";
import { fetchJson } from "./fetchJson";

/** Read-only evidence review: stored news, the inference dry-run plan, the decision journal and the as-of replay. */
const Authority = z.object({ provider_calls: z.literal(0), inference_calls: z.literal(0), budget_reserved: z.literal(false),
  state_written: z.literal(false), trading_mutation: z.literal(false), execution_authority: z.literal(false) });
const Session = z.object({ timezone: z.string(), allowed: z.boolean(), window: z.string(), reason: z.string().nullable(),
  local_time: z.string().optional(), session_date: z.string().optional(), trading_day_basis: z.string() }).passthrough();
const Store = z.object({ state: z.enum(["AVAILABLE", "EMPTY", "UNAVAILABLE"]), reason: z.string().nullable(),
  records: z.number().nullable(), latest_ingested_time: z.string().nullable() });
const Model = z.object({ engine: z.string(), model: z.string().nullable(), selection_source: z.string(), runtime: z.string(),
  configured: z.boolean(), configuration_reason: z.string().nullable(), availability: z.literal("NOT_PROBED") });
const Gate = z.object({ state: z.string().optional(), enabled: z.boolean().optional() }).passthrough();

export const EvidenceStatusSchema = z.object({ schema_version: z.literal("evidence-review-status/1"), server_time: z.string(),
  session: Session, schedule: z.array(z.object({ window: z.string(), start: z.string(), end: z.string(), inference_allowed: z.boolean() })),
  schedule_timezone: z.string(), collection_independent_of_inference_pause: z.literal(true), collection: z.record(Gate),
  knowledge: Store, model: Model, authority: Authority });

const KnowledgeRecord = z.object({ record_id: z.string(), article_id: z.string(), supersedes_record_id: z.string().nullable(),
  headline: z.string().nullable(), summary: z.string().nullable().optional(), url: z.string().nullable(),
  provider_id: z.string().nullable(), source_id: z.string().nullable(), instruments: z.array(z.string()),
  published_time: z.string().nullable(), retrieved_time: z.string().nullable(), first_observed_time: z.string(),
  available_time: z.string(), evidence_class: z.string().nullable().optional(), source_reference: z.string().nullable().optional() }).passthrough();
export const EvidenceKnowledgeSchema = z.object({ schema_version: z.literal("evidence-review-knowledge/1"), as_of: z.string(),
  store: Store, records: z.array(KnowledgeRecord), count: z.number(), limit: z.number(), include_revisions: z.boolean(),
  availability_basis: z.string(), authority: Authority });

const PlanRow = z.object({ record_id: z.string().nullable(), headline: z.string().nullable().optional(),
  source_id: z.string().nullable().optional(), available_time: z.string().nullable(), worst_case_tokens: z.number(),
  reason: z.string().optional() });
export const EvidencePlanSchema = z.object({ schema_version: z.literal("evidence-review-plan/1"), dry_run: z.literal(true),
  planned_for: z.string(), clock_source: z.string(), evidence_as_of: z.string(), session: Session, store: Store,
  candidates: z.number(), planned_requests: z.number(), planned_tokens: z.number(), planned: z.array(PlanRow),
  deferred: z.array(PlanRow), deferred_reasons: z.record(z.number()), unscanned_count: z.number(),
  unscanned_reason: z.string().nullable(), bounds: z.object({ max_requests: z.number(), max_tokens: z.number(), max_backlog: z.number() }),
  budget: z.object({ source: z.string().optional(), requests: z.number().optional(), tokens: z.number().optional(),
    max_requests: z.number().optional(), max_tokens: z.number().optional() }).passthrough(),
  model: Model, model_route: z.object({ state: z.string(), reason: z.string().nullable() }).passthrough(),
  availability_basis: z.string(), estimate_basis: z.string(), request_allowance: z.number().nullable(),
  processed_state: z.string(), collection_independent: z.literal(true), inference_calls: z.literal(0),
  budget_reserved: z.literal(false), authority: Authority });

const LaterEvidence = z.object({ status: z.enum(["AVAILABLE", "UNAVAILABLE"]), reason: z.string().optional(),
  evaluation_id: z.string().optional(), trade_episode_id: z.string().nullable().optional(),
  execution_outcome: z.object({ state: z.string() }).passthrough().nullable().optional(),
  signal_outcomes: z.array(z.record(z.unknown())).optional() }).passthrough();
const JournalItem = z.object({ decision_id: z.string(), decision_time: z.string(), instrument_id: z.string(), mode: z.string(),
  opportunity_id: z.string().nullable(), action: z.object({ action_state: z.string().nullable(),
    operator_action: z.string().nullable(), execution_readiness: z.string().nullable().optional(),
    model_proposal: z.record(z.unknown()).nullable(), rationale: z.string().nullable().optional() }).passthrough(),
  decision_snapshot_hash: z.string(), evidence_snapshot_id: z.string().nullable().optional(),
  candidate_run_id: z.string().nullable().optional(), evidence_count: z.number(), evidence_ids: z.array(z.string()),
  missing_information: z.array(z.string()), outcome_status: z.string(), realized_pnl: z.null(),
  realized_pnl_status: z.string(), later_evidence: LaterEvidence }).passthrough();
export const EvidenceJournalSchema = z.object({ schema_version: z.literal("evidence-review-journal/1"), day: z.string(),
  day_basis: z.string(), observation_as_of: z.string(), mode: z.string(), items: z.array(JournalItem),
  unjournaled: z.array(z.object({ decision_id: z.string().nullable().optional(), instrument_id: z.string().nullable().optional(),
    decision_time: z.string().nullable().optional(), reason: z.string() })),
  source: z.string(), later_evidence_source: z.string(), authority: Authority }).passthrough();
export const EvidenceJournalEntrySchema = z.object({ schema_version: z.literal("evidence-review-journal-entry/1"),
  observation_as_of: z.string(), entry: z.record(z.unknown()), later_evidence: LaterEvidence, authority: Authority }).passthrough();

const ReplayPolicy = z.object({ policy_id: z.string(), policy_version: z.string(), classification: z.string(),
  decision: z.string(), directional_units: z.number(), decision_id: z.string() }).passthrough();
export const EvidenceReplaySchema = z.object({ schema_version: z.literal("evidence-review-replay/1"),
  evidence_class: z.literal("SOFTWARE_FIXTURE_ONLY"), replay_date: z.string(), as_of: z.string(), timezone: z.string(),
  market_data_ref: z.string(), coverage: z.object({ eligible_samples: z.number(), decision_samples: z.number(),
    withheld_news: z.number(), withheld_inference: z.number() }),
  decisions: z.array(z.object({ sample_id: z.string(), as_of: z.string(), instrument_id: z.string(),
    news_event_ids: z.array(z.string()), market_snapshot_ref: z.string(), policies: z.array(ReplayPolicy),
    policies_differ: z.boolean() }).passthrough()),
  gaps: z.array(z.object({ sample_id: z.string(), reason: z.string() })), limitations: z.array(z.string()),
  snapshot_hash: z.string(), deterministic: z.boolean(),
  available: z.array(z.object({ replay_date: z.string(), clocks: z.array(z.string()) })),
  comparison: z.object({ basis: z.string(), any_policy_difference: z.boolean(), performance_ranking: z.null(),
    ranking_status: z.literal("NOT_A_PERFORMANCE_RANKING") }),
  simulation_only: z.literal(true), authority: Authority });

export type EvidenceStatus = z.infer<typeof EvidenceStatusSchema>;
export type EvidenceKnowledge = z.infer<typeof EvidenceKnowledgeSchema>;
export type EvidencePlan = z.infer<typeof EvidencePlanSchema>;
export type EvidenceJournal = z.infer<typeof EvidenceJournalSchema>;
export type EvidenceReplay = z.infer<typeof EvidenceReplaySchema>;

const BASE = "/evaluation/evidence";
/** Empty fields are omitted so the server applies its own defaults (the present, the recorded budget). */
const query = (fields: Record<string, string | boolean | undefined>) => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(fields)) {
    if (value === true) params.set(key, "1");
    else if (typeof value === "string" && value.trim()) params.set(key, value.trim());
  }
  const text = params.toString();
  return text ? `?${text}` : "";
};
export const evidenceApi = {
  status: () => fetchJson(`${BASE}/status`, EvidenceStatusSchema),
  knowledge: (fields: { as_of?: string; symbol?: string; revisions?: boolean }) =>
    fetchJson(`${BASE}/knowledge${query(fields)}`, EvidenceKnowledgeSchema),
  plan: (fields: { at?: string; max_requests?: string; request_allowance?: string; assume_available?: boolean }) =>
    fetchJson(`${BASE}/plan${query(fields)}`, EvidencePlanSchema),
  journal: (fields: { day?: string; as_of?: string }) => fetchJson(`${BASE}/journal${query(fields)}`, EvidenceJournalSchema),
  journalEntry: (fields: { day?: string; as_of?: string; decision_id: string }) =>
    fetchJson(`${BASE}/journal${query(fields)}`, EvidenceJournalEntrySchema),
  replay: (fields: { date?: string; as_of?: string }) => fetchJson(`${BASE}/replay${query(fields)}`, EvidenceReplaySchema),
};
