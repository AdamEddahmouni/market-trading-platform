import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import type { AiScreenerScope } from "./screenerAi";

const Outcome = z.object({ quality: z.string() }).passthrough();
const Comparison = z.object({ basis: z.string(), frozen_action_state: z.string(), frozen_direction: z.string().nullable(),
  decision_reference_price: z.number().nullable(), first_observed_price: z.number().nullable(), last_observed_price: z.number().nullable(),
  last_observed_at: z.string().nullable(), change_pct: z.number().nullable(), elapsed_seconds: z.number().nullable(),
  in_window_observations: z.number(), observation_count: z.number(), subsequent_action_state: z.string().nullable(),
  position_state_now: z.string(), signal_outcome: Outcome, execution_outcome: Outcome }).passthrough();
const Snapshot = z.object({ schema_version: z.literal("next-session-decision/1.0.0"), snapshot_id: z.string(), instrument_id: z.string(),
  account_id: z.string(), created_at: z.string(), decision_cutoff: z.string(), target_session_date: z.string(), target_session_kind: z.string(),
  target_timezone: z.string(), target_session_start: z.string(), target_session_end: z.string(), early_close_metadata: z.string(),
  action_decision_id: z.string(), action_state: z.string(), direction: z.string().nullable(), evidence_snapshot_ref: z.string(),
  provider_id: z.string().nullable(), model_id: z.string().nullable(), prompt_id: z.string().nullable(), position_state: z.string(),
  reference_price: z.number().nullable(), reference_price_as_of: z.string().nullable(),
  evaluation_policy: z.object({ policy_id: z.string(), observation_start: z.string(), observation_end: z.string(), reference_price_basis: z.string() }).passthrough(),
  state: z.string(), lock_state: z.enum(["DRAFT", "LOCKED"]), locked_at: z.string().nullable(), validity_state: z.string(), content_hash: z.string() }).passthrough();
export const NextSessionViewSchema = z.object({ schema_version: z.literal("next-session-view/1.0.0"), snapshot: Snapshot,
  observations: z.array(z.object({ observation_id: z.string(), observed_at: z.string(), source_time: z.string(), price: z.number(), in_window: z.boolean() }).passthrough()),
  observation_count: z.number(), durability: z.string(), integrity: z.string(), comparison: Comparison.nullable() });
export type NextSessionView = z.infer<typeof NextSessionViewSchema>;

const Transition = z.object({ instrument_id: z.string().nullable(), classification: z.string(), reason_codes: z.array(z.string()),
  prior_state: z.string().nullable(), new_state: z.string().nullable(), model_call: z.boolean() }).passthrough();
const ProviderState = z.object({ capability: z.string(), provider: z.string().nullable(), state: z.string().nullable(), delivery_mode: z.string().nullable(),
  cadence_semantics: z.string(), freshness_policy: z.string().nullable(), as_of: z.string().nullable(), age_seconds: z.number().nullable(),
  next_useful_refresh: z.string().nullable(), within_requested_cadence: z.boolean() }).passthrough();
const Readiness = z.object({ readiness: z.enum(["REEVALUATION_READY", "REEVALUATION_DEGRADED", "REEVALUATION_BLOCKED"]), reason_codes: z.array(z.string()) }).passthrough();
const Cycle = z.object({ schema_version: z.literal("reevaluation-cycle/1.0.0"), cycle_id: z.string(), trigger: z.string(), scheduled_for: z.string(),
  scheduled_epoch: z.number(), started_at: z.string(), completed_at: z.string().nullable(), start_drift_ms: z.number(), duration_ms: z.number().nullable(),
  requested_cadence_seconds: z.number(), effective_cadence_seconds: z.number(), session_state: z.string(), position_count: z.number(), candidate_count: z.number(),
  material_change_count: z.number(), model_call_count: z.number(), missed_ticks_before: z.number(), transitions: z.array(Transition),
  counters: z.object({ proposed_transitions: z.number(), accepted_transitions: z.number(), duplicate_suppressions: z.number(), churn_suppressions: z.number(), model_calls_avoided: z.number() }),
  not_observed: z.object({ observed_from: z.string(), observed_to: z.string(), missed_scheduled_cycles: z.number(), reason: z.string() }).passthrough().nullable(),
  cycle_status: z.string(), reason_codes: z.array(z.string()) }).passthrough();
export type ReevaluationCycle = z.infer<typeof Cycle>;
const Engine = z.object({ state: z.string(), reason: z.string().nullable(), provider_id: z.string().nullable(), model_id: z.string().nullable(), runtime: z.string().nullable(),
  budget: z.object({ requests: z.number(), max_requests: z.number() }).passthrough().nullable() }).passthrough();
export const ReevaluationStatusSchema = z.object({ schema_version: z.literal("reevaluation-status/1.0.0"), worker_state: z.string(), worker_label: z.string(),
  engine: Engine, durability: z.string(), paper_execution: z.literal("MANUAL_ONLY"), loop_id: z.string().optional(), account_id: z.string().optional(),
  scope: z.object({ universe: z.string() }).passthrough().optional(), requested_cadence_seconds: z.number().optional(), effective_cadence_seconds: z.number().optional(),
  cadence: z.object({ limiting_constraint: z.string(), degraded: z.boolean() }).passthrough().optional(),
  liveness: z.object({ last_scheduled: z.string().nullable(), last_started: z.string().nullable(), last_completed: z.string().nullable(), last_success: z.string().nullable(),
    last_error: z.object({ at: z.string(), code: z.string() }).nullable(), last_status: z.string().nullable(), missed_ticks: z.number(), cycle_count: z.number() }).passthrough().optional(),
  next_scheduled: z.string().nullable().optional(), last_cycle: Cycle.nullable().optional(),
  readiness: Readiness.extend({ provider_states: z.array(ProviderState) }).nullable().optional(),
  projection: z.object({ worst_case_model_calls: z.number(), cycles: z.number(), session_minutes: z.number() }).passthrough().optional() }).passthrough();
export type ReevaluationStatus = z.infer<typeof ReevaluationStatusSchema>;
const History = z.object({ schema_version: z.literal("reevaluation-history/1.0.0"), cycles: z.array(Cycle), next_before: z.number().nullable(), durability: z.string() });

export const draftNextSession = (decision_id: string, signal?: AbortSignal) => postJson("/screener/next-session/draft", { decision_id }, NextSessionViewSchema, { signal });
const act = (operation: "lock" | "observe" | "evaluate") => (snapshot_id: string, signal?: AbortSignal) => postJson(`/screener/next-session/${operation}`, { snapshot_id }, NextSessionViewSchema, { signal });
export const lockNextSession = act("lock");
export const observeNextSession = act("observe");
export const evaluateNextSession = act("evaluate");

/** The loop follows the live scope; a pinned result set or settle flag is never sent. */
export const configureReevaluation = (scope: AiScreenerScope, requested_cadence_seconds: number, signal?: AbortSignal) => postJson("/screener/reevaluation/configure",
  { scope: { universe: scope.universe, search: scope.search, sort: scope.sort, descending: scope.descending, filters: scope.filters, view: scope.view ?? "Overview", screen: scope.screen ?? "" }, requested_cadence_seconds },
  ReevaluationStatusSchema, { signal });
export const reevaluationStatus = (signal?: AbortSignal) => fetchJson("/screener/reevaluation/status", ReevaluationStatusSchema, { signal });
export const startReevaluation = (signal?: AbortSignal) => postJson("/screener/reevaluation/start", {}, ReevaluationStatusSchema, { signal });
export const stopReevaluation = (signal?: AbortSignal) => postJson("/screener/reevaluation/stop", {}, ReevaluationStatusSchema, { signal });
export const runReevaluationOnce = (signal?: AbortSignal) => postJson("/screener/reevaluation/run-once", {}, Cycle, { signal });
export const reevaluationHistory = (limit = 20, signal?: AbortSignal) => fetchJson(`/screener/reevaluation/history?limit=${limit}`, History, { signal });
