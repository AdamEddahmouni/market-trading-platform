import { z } from "zod";
import { fetchJson } from "./fetchJson";

/** OCT1-10 read model. Every value is a server projection; nothing here is recomputed in the browser. */

const Action = z.enum(["NO_ACTION", "CONSIDER_ENTRY", "ENTER", "HOLD", "EXIT", "REVALIDATION_REQUIRED"]);
const Stage = z.enum(["SELECTED_NOT_ASSESSED", "NO_ACTION", "CONSIDERING_ENTRY", "ENTER_NOT_EXECUTED", "ENTRY_SUBMITTED", "REVALIDATION_REQUIRED",
  "POSITION_OPEN", "EXIT_NOT_EXECUTED", "EXIT_SUBMITTED", "POSITION_CLOSED"]);
const Group = z.enum(["SELECTED", "ACTIVE_MANAGED", "RECENT_CLOSED", "UNLINKED_PAPER_ACTIVITY"]);
const Origin = z.enum(["AI_PROPOSAL_SERVER_GATED", "DETERMINISTIC_RISK_CONTROL", "SERVER_FAILSAFE"]);
const Quality = z.enum(["CURRENT", "STALE", "DEGRADED", "UNAVAILABLE"]);
const text = z.string().nullable();
const minor = z.number().int().nullable();

const EvidenceItem = z.object({ evidence_id: text, capability: text.optional(), fact: text.optional(), source: text.optional(), as_of: text.optional(),
  freshness_status: text.optional(), delivery_mode: text.optional(), role: text.optional(), decision_admissibility: text.optional(),
  weak_reasons: z.array(z.string()).optional(), lineage: z.string().optional() }).passthrough();
const EvidenceGroup = z.object({ items: z.array(EvidenceItem), truncated: z.number().int() });
const Counts = z.object({ supporting: z.number().int(), conflicting: z.number().int(), weak: z.number().int(), missing: z.number().int(), blocked: z.number().int() });
const Evidence = z.object({
  counts: Counts, supporting: EvidenceGroup.optional(), conflicting: EvidenceGroup.optional(), weak: EvidenceGroup.optional(),
  conflicting_alignments: z.array(z.object({ alignment_id: text, kind: text, result: text, observed_direction: text, limitations: z.array(z.string()) })).optional(),
  missing: z.array(z.string()).optional(),
  blocked: z.array(z.object({ capability: text, source: text, as_of: text, freshness_status: text, reason_codes: z.array(z.string()) })).optional(),
  blocked_truncated: z.number().int().optional(),
});
export type LifecycleEvidence = z.infer<typeof Evidence>;

const Condition = z.object({ condition_id: text, status: z.enum(["MET", "NOT_MET"]).nullable(), source: text, valid_until: text, reason_codes: z.array(z.string()) });
const Decision = z.object({
  decision_id: z.string(), action_state: Action, decision_time: z.string(), decision_cutoff: z.string(), valid_until: text,
  direction: z.enum(["LONG", "SHORT"]).nullable(), rationale: text, origin: Origin, ai_proposal_state: text.optional(),
  model: z.object({ provider_id: text, model_id: text, prompt_id: text, called: z.boolean() }).nullable(),
  execution_readiness: z.enum(["NOT_PREVIEWED", "PREVIEW_ALLOWED", "BLOCKED"]), blocker_codes: z.array(z.string()), reason_codes: z.array(z.string()),
  previous_state: text, position_at_decision: z.object({ state: z.enum(["FLAT", "LONG", "SHORT"]), quantity: z.number().nullable() }),
  reference_price: text, reference_as_of: text, candidate_run_id: text,
  risk_exit: z.object({ reason: text, stop_state_id: text, policy_id: text, active_stop: text, trigger_price: text, triggered_at: text }).nullable(),
  entry_conditions: z.array(Condition).optional(), hold_conditions: z.array(Condition).optional(), exit_conditions: z.array(Condition).optional(),
  evidence_snapshot_id: text.optional(), decision_trace_id: text.optional(), opportunity_id: text.optional(), evidence: Evidence.optional(),
}).passthrough();
export type LifecycleDecision = z.infer<typeof Decision>;

const Reference = z.object({ decision_id: z.string(), decision_time: z.string(), price: text, as_of: text });
const Fill = z.object({ fill_id: z.string(), order_id: text, kind: z.literal("SIMULATED_PAPER_FILL"), price_minor: z.number().int(), time: text, submitted_at: text,
  quantity: z.number().int(), side: text, position_effect: z.string(), decision_id: text, decision_source: text, is_market_truth: z.literal(false) });
const Entry = z.object({
  status: z.enum(["NOT_PROPOSED", "CONSIDERED", "DECIDED_ENTER", "SUBMITTED_PAPER", "PARTIALLY_FILLED", "FILLED", "BLOCKED", "EXPIRED"]),
  decision_reference: Reference.nullable(), fill: Fill.nullable(), fills: z.array(Fill).optional(), fill_count: z.number().int(),
  quantity: z.number().int().nullable(), average_price_minor: minor, paper: z.enum(["NO_FILL", "SUBMITTED_NOT_FILLED", "SIMULATED_FILL"]),
});
const Exit = z.object({
  status: z.enum(["NO_EXIT", "EXIT_DECIDED", "EXIT_SUBMITTED", "PARTIALLY_CLOSED", "CLOSED", "BLOCKED"]),
  decision_reference: Reference.nullable(), fill: Fill.nullable(), fills: z.array(Fill).optional(), fill_count: z.number().int(),
  closed_quantity: z.number().int().nullable(), average_price_minor: minor,
  paper_close: z.enum(["NOT_APPLICABLE", "NOT_SUBMITTED", "SUBMITTED_NOT_FILLED", "PARTIALLY_FILLED", "FILLED"]),
});
const Mark = z.object({ price_minor: minor, as_of: text, source: text, source_quality: z.string(), age_ms: z.number().nullable(), quality: Quality });
const Position = z.object({ state: z.enum(["FLAT", "LONG", "SHORT", "UNAVAILABLE"]), quantity: z.number().int().nullable(), average_entry_minor: minor.optional(),
  first_entry_time: text.optional(), latest_fill_time: text.optional(), market_value_minor: minor.optional(), mark: Mark.nullable(), closed: z.boolean().optional() });
const stop = z.string().nullable().optional();
const Risk = z.object({
  method: z.literal("SMA_TRAILING_STOP"), origin: z.literal("DETERMINISTIC_RISK_CONTROL"), model: z.literal("none"),
  status: z.enum(["NOT_CONFIGURED", "WARMING_UP", "ACTIVE", "STALE", "BLOCKED", "BREACHED", "CLOSED", "NOT_APPLICABLE", "NO_STOP_RECORD", "UNAVAILABLE"]),
  configured: z.boolean().nullable(), reason_codes: z.array(z.string()),
  policy: z.object({ policy_id: text, sma_window_bars: z.number().nullable(), bar_interval: text }).nullable(),
  stop: z.object({ stop_state_id: stop, sma_value: stop, active_stop: stop, previous_stop: stop, distance_to_stop: stop, distance_bps: z.number().nullable().optional(),
    last_updated_at: stop, stop_as_of: stop, reference_price: stop, trigger_price: stop, triggered_at: stop, closed_reason: stop }).passthrough().nullable(),
  exit_decision_id: text, lineage: z.string(), monitoring: text.optional(),
});
const Pnl = z.object({ realized_minor: minor, unrealized_minor: minor, costs_minor: minor, quality: z.enum(["CURRENT", "STALE", "DEGRADED", "UNAVAILABLE", "REALIZED", "NOT_APPLICABLE"]),
  currency: z.string(), basis: z.literal("PAPER_LEDGER_FILLS"), realized_includes_costs: z.literal(true) });
const Candidate = z.object({
  selected: z.literal(true), selected_in_current_run: z.boolean(), rank: z.number().int().nullable(), run_id: text, run_state: text, selected_at: text,
  decision_cutoff: text, valid_until: text, rationale: text, uncertainties: z.array(z.string()), provider_id: text, model_id: text, prompt_id: text,
  prompt_version: z.union([z.string(), z.number()]).nullable(), simulated: z.boolean(), lineage: z.enum(["CANDIDATE_RUN", "DECISION_SNAPSHOT"]), evidence: Evidence,
});
const Experiment = z.object({ experiment_id: text, name: text.optional(), status: text.optional(), capital_kind: z.literal("SIMULATED"), live_capital: z.literal(false),
  execution: z.string(), market_data: z.string(), equity_minor: minor, cash_minor: minor, valuation_quality: text });
const Reevaluation = z.object({ worker_state: text, worker_label: text, requested_cadence_seconds: z.number().nullable(), effective_cadence_seconds: z.number().nullable(), last_completed: text });
const TimelineRow = z.object({
  kind: z.enum(["CANDIDATE_SELECTED", "DECISION", "STOP", "PAPER_ORDER", "PAPER_FILL"]), at: text, event: z.string(), source: z.string(), reason: text.optional(),
  reason_codes: z.array(z.string()).optional(), ref: z.object({ type: z.string(), id: text }), clocks: z.record(z.unknown()),
}).passthrough();
export type LifecycleTimelineRow = z.infer<typeof TimelineRow>;

export const TradeLifecycleSchema = z.object({
  schema_version: z.literal("trade-lifecycle/1.0.0"), lifecycle_id: z.string(), kind: z.enum(["POSITION_EPISODE", "CANDIDATE"]), group: Group,
  instrument_id: z.string(), symbol: z.string(), stage: Stage, ai_selected: z.boolean(),
  position_origin: z.enum(["AI_DECISION_GOVERNED", "UNLINKED_PAPER_ACTIVITY"]).nullable(),
  candidate: Candidate.nullable(), decision: Decision.nullable(), entry: Entry, position: Position, risk_control: Risk, exit: Exit, pnl: Pnl,
  origin: z.object({ run_id: text, same_as_current_run: z.boolean(), lineage: z.enum(["CANDIDATE_RUN", "NOT_APPLICABLE", "LINEAGE_UNAVAILABLE"]) }),
  freshness: z.object({ projection: z.literal("DERIVED_ON_READ"), decision_valid_until: text, decision_current: z.boolean().nullable(), mark_quality: Quality.nullable().optional() }),
  lineage: z.object({ basis: z.string(), account_id: z.string(), experiment_id: text, episode_id: text, opening_fill_id: text, opening_decision_id: text,
    opening_basis: text, origin_run_id: text, decision_count: z.number().int(), stop_state_ids: z.array(z.string()), candidate: z.string() }),
  limitations: z.array(z.string()), as_of: z.string(), currency: z.string(), price_scale: z.number().int(),
  // Detail only: fetched when a lifecycle is expanded.
  decisions: z.array(Decision).optional(), decisions_truncated: z.number().int().optional(),
  timeline: z.array(TimelineRow).optional(), timeline_truncated: z.number().int().optional(),
  prior_episodes: z.array(z.object({ lifecycle_id: z.string(), open: z.boolean(), opened_at: text, closed_at: text, realized_pnl_minor: minor, ai_selected: z.boolean() })).optional(),
  prior_episodes_truncated: z.number().int().optional(), reevaluation: Reevaluation.optional(), experiment: Experiment.nullable().optional(),
});
export type TradeLifecycle = z.infer<typeof TradeLifecycleSchema>;

export const TradeLifecycleListSchema = z.object({
  schema_version: z.literal("trade-lifecycle-list/1.0.0"), as_of: z.string(), account_id: z.string(), experiment_id: text, currency: z.string(),
  run: z.object({ run_id: z.string(), state: text, valid_until: text, generated_at: text.optional(), selected_count: z.number().int() }).nullable(),
  selected: z.array(TradeLifecycleSchema), active_managed: z.array(TradeLifecycleSchema), recent_closed: z.array(TradeLifecycleSchema), unlinked: z.array(TradeLifecycleSchema),
  counts: z.object({ selected: z.number().int(), active_managed: z.number().int(), recent_closed: z.number().int(), unlinked: z.number().int() }),
  next_closed_before: z.number().int().nullable(), experiment: Experiment.nullable(), reevaluation: Reevaluation,
  market_data: z.string(), execution: z.literal("SIMULATED_PAPER"), limitations: z.array(z.string()),
}).passthrough();
export type TradeLifecycleList = z.infer<typeof TradeLifecycleListSchema>;

const query = (runId: string | null | undefined) => runId ? `?run_id=${encodeURIComponent(runId)}` : "";
export const tradeLifecycles = (runId?: string | null, signal?: AbortSignal) =>
  fetchJson(`/screener/trade-lifecycles${query(runId)}`, TradeLifecycleListSchema, { signal });
export const tradeLifecycle = (lifecycleId: string, runId?: string | null, signal?: AbortSignal) =>
  fetchJson(`/screener/trade-lifecycles/${encodeURIComponent(lifecycleId)}${query(runId)}`, TradeLifecycleSchema, { signal });
