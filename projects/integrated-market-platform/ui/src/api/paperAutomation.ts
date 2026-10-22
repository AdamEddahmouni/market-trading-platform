import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import type { AiScreenerScope } from "./screenerAi";

/** AUTO-01: owner policy, arming and controls for unattended internal Paper simulation. The server decides everything shown here. */
const Blocker = z.object({ category: z.string(), code: z.string() });
const Session = z.object({ label: z.string(), trading_day: z.boolean(), session_date: z.string(), minutes_to_close: z.number().nullable() }).passthrough();
/** Adaptive full-universe scheduling is optional: an absent field means the owner did not enable it. */
const Scheduling = z.object({
  policy: z.object({ min_separation_seconds: z.number(), max_age_seconds: z.number().nullable().optional(),
    material_change_trigger: z.boolean().nullable().optional(), max_runs_per_day: z.number().nullable().optional(),
    optional_fields: z.array(z.string()) }).passthrough(),
  adaptive: z.boolean(),
  last_decision: z.object({ decision: z.string(), reason_codes: z.array(z.string()), next_eligible_epoch: z.number().nullable().optional(),
    next_eligible_iso: z.string().nullable().optional(), at_iso: z.string().nullable().optional() }).passthrough().nullable().optional(),
  next_eligible: z.string().nullable().optional(), next_eligible_epoch: z.number().nullable().optional(),
  last_complete: z.object({ run_id: z.string(), finished_at: z.string().nullable().optional(),
    universe_count: z.number().nullable().optional() }).passthrough().nullable().optional(),
  last_complete_fingerprint: z.object({ scope: z.string(), session_date: z.string(),
    universe_count: z.number().nullable().optional() }).passthrough().nullable().optional(),
  active_run_id: z.string().nullable().optional(),
  withheld: z.object({ at: z.string(), reason: z.string() }).nullable().optional(),
  failure: z.object({ count: z.number(), code: z.string(), backoff_until: z.number() }).passthrough().nullable().optional(),
  runs_today: z.object({ started: z.number(), limit: z.number().nullable().optional() }).passthrough() }).passthrough();
const Policy = z.object({ policy_id: z.string(), account_id: z.string(), experiment_id: z.string(),
  schedule: z.object({ sessions: z.array(z.string()), cadence_seconds: z.number(), universe_evaluation_interval_seconds: z.number(), no_new_entries_minutes_before_close: z.number(),
    universe_max_age_seconds: z.number().optional(), universe_material_change_trigger: z.boolean().optional(), universe_max_runs_per_day: z.number().optional() }),
  risk: z.object({ max_position_notional_minor: z.number(), max_aggregate_exposure_minor: z.number(), max_open_positions: z.number(), max_daily_loss_minor: z.number(),
    max_per_trade_risk_minor: z.number(), assumed_adverse_move_bps: z.number(), allowed_universes: z.array(z.string()), order_types: z.array(z.string()),
    allow_long: z.boolean(), allow_short: z.boolean(), allow_entries: z.boolean(), allow_exits: z.boolean() }),
  exits: z.object({ on_stop_breach: z.boolean(), on_thesis_exit: z.boolean() }),
  ai: z.object({ allow_local_inference: z.boolean(), allow_paid_inference: z.boolean(), max_paid_requests_per_day: z.number(), max_paid_tokens_per_day: z.number() }),
  emergency_stop: z.object({ max_consecutive_failures: z.number() }) }).passthrough();
const Action = z.object({ decision_id: z.string(), instrument_id: z.string(), action: z.string(), outcome: z.string(), reason_codes: z.array(z.string()),
  quantity: z.number().optional(), side: z.string().optional(), order_state: z.string().nullable().optional(), filled_quantity: z.number().optional(),
  fill_price_minor: z.number().nullable().optional() }).passthrough();
const UniverseResult = z.object({ run_id: z.string(), status: z.string(), reason: z.string().nullable(), universe_count: z.number().nullable(),
  ai_evaluated_count: z.number().nullable(), ai_coverage_pct: z.number().nullable(), coverage_complete: z.boolean(), adopted: z.boolean(),
  selected: z.array(z.string()).optional() }).passthrough();
const Cycle = z.object({ cycle_id: z.string(), status: z.string().optional(), scheduled_for: z.string(), error: z.string().nullable(), blockers: z.array(Blocker),
  actions: z.array(Action), missed_cycles_before: z.number(),
  reevaluation: z.object({ cycle_status: z.string(), position_count: z.number(), candidate_count: z.number(), model_call_count: z.number() }).passthrough().nullable() }).passthrough();
const Risk = z.object({ open_positions: z.number(), max_open_positions: z.number(), exposure_minor: z.number().nullable(), max_aggregate_exposure_minor: z.number(),
  day_pnl_minor: z.number().nullable(), max_daily_loss_minor: z.number(), valuation_quality: z.string().nullable().optional(), equity_minor: z.number().nullable().optional(),
  realized_pnl_minor: z.number().nullable().optional(), unrealized_pnl_minor: z.number().nullable().optional(), total_pnl_minor: z.number().nullable().optional() }).passthrough();
const Intent = z.object({ intent_id: z.string(), decision_id: z.string(), instrument_id: z.string(), action: z.string(), state: z.string(), reason_codes: z.array(z.string()),
  decision_origin: z.string().optional(), quantity: z.number().optional(), side: z.string().optional(), order_state: z.string().nullable().optional(),
  filled_quantity: z.number().optional(), fill_price_minor: z.number().nullable().optional(), updated_at: z.string() }).passthrough();
export const AUTOMATION_STATES = ["NOT_CONFIGURED", "DISARMED", "STOPPED", "PAUSED", "EMERGENCY_STOPPED", "WAITING_FOR_MARKET", "BLOCKED_BY_AUTHORITY",
  "BLOCKED_BY_DATA", "BLOCKED_BY_RISK", "BLOCKED_BY_BUDGET", "RUNNING", "ERROR"] as const;
export const PaperAutomationStatusSchema = z.object({ schema_version: z.literal("paper-automation-status/1.0.0"), status: z.enum(AUTOMATION_STATES), status_label: z.string(),
  required_configuration: z.array(z.string()), arm_acknowledgement: z.string(), session: Session, durability: z.string(),
  boundary: z.object({ execution: z.literal("INTERNAL_PAPER_SIMULATION_ONLY"), live_capital: z.literal(false), real_money_order_routes: z.string(),
    execution_mode: z.string(), execution_provider: z.string() }).passthrough(),
  identity_blockers: z.array(z.string()).optional(), blockers: z.array(Blocker).optional(), policy: Policy.optional(), armed: z.boolean().optional(),
  arming: z.object({ arming_id: z.string(), policy_id: z.string(), armed_at: z.string(), operator: z.string().nullable() }).passthrough().nullable().optional(),
  emergency: z.object({ at: z.string(), reason: z.string(), source: z.string() }).passthrough().nullable().optional(), desired_state: z.string().optional(),
  liveness: z.object({ owner: z.string().nullable(), worker_alive: z.boolean(), heartbeat_at: z.string().nullable(), cycle_count: z.number().nullable(),
    consecutive_failures: z.number().nullable(), last_error: z.object({ at: z.string(), code: z.string() }).nullable(), last_scheduled: z.string().nullable() }).passthrough().optional(),
  last_cycle: Cycle.nullable().optional(),
  universe: z.object({ active_run_id: z.string().nullable(), last_result: UniverseResult.nullable(), adopted_run_id: z.string().nullable().optional(),
    withheld: z.object({ at: z.string(), reason: z.string() }).nullable().optional() }).passthrough().nullable().optional(),
  scheduling: Scheduling.optional(),
  candidate_quotes: z.array(z.string()).optional(), risk: Risk.optional(),
  positions: z.array(z.object({ instrument_id: z.string(), quantity: z.number(), side: z.string().nullable().optional(), average_fill_minor: z.number().nullable().optional(),
    mark_minor: z.number().nullable().optional(), unrealized_pnl_minor: z.number().nullable().optional() }).passthrough()).optional(),
  working_orders: z.array(z.object({ order_id: z.string(), instrument_id: z.string(), side: z.string(), state: z.string() }).passthrough()).optional(),
  recent_intents: z.array(Intent).optional(),
  provider: z.object({ state: z.string(), reasons: z.array(z.string()) }).passthrough().nullable().optional(),
  engine: z.object({ state: z.string(), reason: z.string().nullable(), provider_id: z.string().nullable(), model_id: z.string().nullable(), runtime: z.string().nullable() }).passthrough().optional(),
  spending: z.object({ allowed: z.boolean(), reason: z.string().nullable() }).optional(), evaluated_at: z.string() }).passthrough();
export type PaperAutomationStatus = z.infer<typeof PaperAutomationStatusSchema>;
export type PaperAutomationPolicy = z.infer<typeof Policy>;
const EmergencyResult = PaperAutomationStatusSchema.extend({ cancelled_orders: z.number() });
const Event = z.object({ sequence: z.number(), at: z.number(), kind: z.string(), at_iso: z.string().nullable().optional() }).passthrough();
export type PaperAutomationEvent = z.infer<typeof Event>;
const History = z.object({ schema_version: z.literal("paper-automation-history/1.0.0"), events: z.array(Event), next_before: z.number().nullable(), durability: z.string() });
const Report = z.object({ schema_version: z.literal("paper-automation-report/1.0.0"), evidence_class: z.literal("SIMULATED_PAPER_FILLS_NOT_MARKET_TRUTH"), statement: z.string(),
  fills: z.object({ count: z.number(), opening: z.number(), closing: z.number(), costs_minor: z.number(), slippage_model: z.string() }),
  outcomes: z.object({ closed_fills: z.number(), wins: z.number(), losses: z.number(), flat: z.number(), realized_pnl_minor: z.number(), sample_note: z.string() }).passthrough(),
  portfolio: z.object({ equity_minor: z.number().nullable(), realized_pnl_minor: z.number().nullable(), unrealized_pnl_minor: z.number().nullable(), total_pnl_minor: z.number().nullable(),
    exposure_minor: z.number().nullable(), open_positions: z.number(), max_drawdown_minor_last_snapshots: z.number(), valuation_quality: z.string().nullable() }).passthrough(),
  decisions: z.object({ intents: z.number(), submitted: z.number(), refused_or_deferred: z.number(), refusal_reasons: z.record(z.string(), z.number()),
    by_origin: z.record(z.string(), z.number()) }),
  ai: z.object({ universe_runs: z.number(), complete_runs: z.number(), incomplete_runs: z.number(), tokens_input: z.number(), tokens_output: z.number(),
    models: z.array(z.string()), reevaluation_model_calls_last_day: z.number() }), generated_at: z.string() }).passthrough();
export type PaperAutomationReport = z.infer<typeof Report>;

/** Every field is an owner decision: the form sends exactly what was entered and the server refuses an incomplete policy. */
export type PaperAutomationPolicyInput = Pick<PaperAutomationPolicy, "schedule" | "risk" | "exits" | "ai" | "emergency_stop">;
const scopeBody = (scope: AiScreenerScope) => ({ universe: scope.universe, search: scope.search, sort: scope.sort, descending: scope.descending,
  filters: scope.filters, view: scope.view ?? "Overview", screen: scope.screen ?? "" });

export const paperAutomationStatus = (signal?: AbortSignal) => fetchJson("/paper/automation/status", PaperAutomationStatusSchema, { signal });
export const paperAutomationHistory = (limit = 30, signal?: AbortSignal) => fetchJson(`/paper/automation/history?limit=${limit}`, History, { signal });
export const paperAutomationReport = (signal?: AbortSignal) => fetchJson("/paper/automation/report", Report, { signal });
export const configurePaperAutomation = (scope: AiScreenerScope, policy: PaperAutomationPolicyInput, signal?: AbortSignal) =>
  postJson("/paper/automation/configure", { scope: scopeBody(scope), ...policy }, PaperAutomationStatusSchema, { signal });
export const armPaperAutomation = (policy_id: string, acknowledgement: string, signal?: AbortSignal) =>
  postJson("/paper/automation/arm", { policy_id, acknowledgement }, PaperAutomationStatusSchema, { signal });
const control = (operation: "disarm" | "start" | "pause" | "resume" | "stop") => (signal?: AbortSignal) =>
  postJson(`/paper/automation/${operation}`, {}, PaperAutomationStatusSchema, { signal });
export const disarmPaperAutomation = control("disarm");
export const startPaperAutomation = control("start");
export const pausePaperAutomation = control("pause");
export const resumePaperAutomation = control("resume");
export const stopPaperAutomation = control("stop");
export const emergencyStopPaperAutomation = (reason: string, signal?: AbortSignal) =>
  postJson("/paper/automation/emergency-stop", reason ? { reason } : {}, EmergencyResult, { signal });
