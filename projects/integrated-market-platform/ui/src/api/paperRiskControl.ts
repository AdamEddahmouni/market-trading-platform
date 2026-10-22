import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";

/** OCT1-08 SMA trailing-stop monitor. Server-owned risk facts; none of these routes creates or submits an order. */
const text = z.string().nullable();
const Policy = z.object({ schema_version: z.literal("sma-trailing-stop-policy/1.0.0"), policy_id: z.string(), method: z.literal("SMA_TRAILING"),
  sma_window_bars: z.number().int(), bar_interval: z.string(), session_scope: z.string(), price_basis: z.string(), config_label: z.string(),
  update_timing: z.string(), warmup_requirement: z.string(), long_behavior: z.string(), short_behavior: z.string() }).passthrough();
const Monitoring = z.object({ state: z.enum(["RUNNING", "NOT_RUNNING"]), worker_state: z.string(), last_evaluated_at: text, liveness: z.string() });
const ExitDecision = z.object({ decision_id: z.string(), action_state: z.string(), execution_readiness: z.string(), blocker_codes: z.array(z.string()), decision_time: z.string() });
const Stop = z.object({ stop_state_id: z.string(), position_epoch_id: z.string(), epoch_basis: z.string(), side: z.enum(["LONG", "SHORT"]), quantity: z.number(),
  policy_id: z.string(), sma_window_bars: z.number().int(), bar_interval: z.string(), config_label: z.string(), activated_at: text, activation_reason: z.string(),
  sma_value: text, candidate_stop: text, active_stop: text, previous_stop: text, stop_as_of: text, bar_id: text, bar_available_at: text, bars_available: z.number(),
  last_updated_at: text, last_evaluated_at: text, update_count: z.number(), tighten_count: z.number(), clamp_count: z.number(),
  trigger_state: z.string(), trigger_reason_codes: z.array(z.string()), triggered_at: text, trigger_price: text,
  trigger_evidence: z.object({ kind: text, basis: text, source: text, evidence_ref: text, bar_id: text, as_of: text }).nullable(), trigger_basis: z.string(),
  bar_source: z.object({ state: z.string(), reason: text, source: text }).passthrough().nullable().optional(), carried_from: text.optional(),
  closed_at: text, closed_reason: text, reference_price: text, reference_as_of: text, distance_to_stop: text, distance_bps: z.number().nullable(),
  exit_decision: ExitDecision.nullable().optional() }).passthrough();
export const SmaStopStatusSchema = z.object({ schema_version: z.literal("sma-stop-status/1.0.0"), instrument_id: z.string(), account_id: z.string(),
  method: z.literal("SMA_TRAILING"), status: z.enum(["NOT_CONFIGURED", "WARMING_UP", "ACTIVE", "STALE", "BLOCKED", "BREACHED", "CLOSED"]),
  reason_codes: z.array(z.string()), policy: Policy.nullable(), position: z.object({ state: z.enum(["FLAT", "LONG", "SHORT"]), quantity: z.number() }).nullable(),
  stop: Stop.nullable(), monitoring: Monitoring.optional(), durability: z.string(), paper_execution: z.literal("MANUAL_ONLY"),
  paper_close: z.literal("NOT_SUBMITTED"), live_execution: z.literal("UNCHANGED"), order_type: z.literal("NONE_STOP_MONITOR_ONLY"),
  evaluated_at: z.string(), exit_decision_error: z.string().optional() }).passthrough();
export type SmaStopStatus = z.infer<typeof SmaStopStatusSchema>;

export const SmaStopConfigSchema = z.object({ schema_version: z.literal("sma-stop-config/1.0.0"), configured: z.boolean(), enabled: z.boolean(), policy: Policy.nullable(),
  reference_config: z.object({ sma_window_bars: z.number().int(), bar_interval: z.string(), label: z.string(), note: z.string() }),
  bounds: z.object({ sma_window_bars: z.tuple([z.number(), z.number()]), bar_interval: z.array(z.string()) }), durability: z.string() });
export type SmaStopConfig = z.infer<typeof SmaStopConfigSchema>;

const StopEvent = z.object({ sequence: z.number(), kind: z.string(), at: text, status: z.string(), side: z.string(), sma_value: text, candidate_stop: text,
  active_stop: text, previous_stop: text, reason_codes: z.array(z.string()), policy_id: z.string() }).passthrough();
export type SmaStopEvent = z.infer<typeof StopEvent>;
const History = z.object({ schema_version: z.literal("sma-stop-history/1.0.0"), instrument_id: z.string(), events: z.array(StopEvent), next_before: z.number().nullable(),
  total: z.number(), durability: z.string() });

const Aggregate = z.object({ episodes: z.number(), stop_frequency: z.number(), mean_gross_return_bps: z.number().nullable(), median_gross_return_bps: z.number().nullable(),
  mean_net_return_bps: z.number().nullable(), mean_mae_bps: z.number().nullable(), median_mae_bps: z.number().nullable(), mean_max_drawdown_bps: z.number().nullable(),
  worst_drawdown_bps: z.number().nullable(), loss_severity_bps: z.number().nullable(), premature_exit_frequency: z.number(), mean_holding_bars: z.number().nullable(),
  mean_bars_after_invalidation: z.number().nullable(), gap_through_stop_events: z.number() }).passthrough();
export type SmaStopAggregate = z.infer<typeof Aggregate>;
const Executed = z.object({ schema_version: z.literal("sma-stop-evaluation/1.0.0"), result_status: z.literal("REPLAY_EVALUATED"), experiment_id: z.string(),
  evidence_class: z.literal("HISTORICAL_REPLAY"), calibration_status: z.literal("NOT_CALIBRATED"), definition_hash: z.string(), input_hash: z.string(), result_hash: z.string(),
  corpus_unchanged: z.boolean(), primary_side: z.enum(["LONG", "SHORT"]),
  policy: z.object({ policy_id: z.string(), sma_window_bars: z.number(), bar_interval: z.string(), config_label: z.string() }).passthrough(),
  fill_model: z.object({ id: z.string(), primary: z.string(), cost_bps_per_side: z.number() }).passthrough(),
  provenance: z.object({ corpus_path: z.string(), dataset_fingerprint: z.string(), corpus_evidence_label: z.string(), normalized_sha256: z.string(), session_dates: z.array(z.string()) }).passthrough(),
  corpus: z.object({ sessions: z.array(z.string()), bars: z.number(), instruments: z.number() }).passthrough(),
  counts: z.object({ episodes: z.number(), evaluable: z.number(), excluded: z.number(), exclusions: z.record(z.number()), evaluable_by_side: z.record(z.number()) }),
  aggregates: z.record(z.record(Aggregate)),
  comparisons: z.array(z.object({ alternative: z.string(), sessions: z.number(), downside: z.string(), returns: z.string(), pattern: z.string() }).passthrough()),
  conclusion: z.object({ conclusion: z.enum(["INSUFFICIENT_EVIDENCE", "NO_CLEAR_DIFFERENCE", "SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF", "SMA_UNDERPERFORMED_REFERENCE"]),
    in_sample_pattern: z.string(), in_sample_pattern_status: z.string(), sessions: z.number(), instruments: z.number(), superiority_claim: z.literal("NONE"), statement: z.string() }),
  sample_size_note: z.string(), episode_count: z.number() }).passthrough();
const NotExecuted = z.object({ schema_version: z.literal("sma-stop-evaluation/1.0.0"), result_status: z.literal("NOT_EXECUTED"), reason_codes: z.array(z.string()) });
export const SmaStopEvaluationSchema = z.union([Executed, NotExecuted]);
export type SmaStopEvaluation = z.infer<typeof SmaStopEvaluationSchema>;
export type SmaStopEvaluationResult = z.infer<typeof Executed>;

const BASE = "/paper/risk-control/sma-stop";
export const smaStopStatus = (instrument: string, signal?: AbortSignal) => fetchJson(`${BASE}?instrument=${encodeURIComponent(instrument)}`, SmaStopStatusSchema, { signal });
export const smaStopConfig = (signal?: AbortSignal) => fetchJson(`${BASE}/config`, SmaStopConfigSchema, { signal });
/** Bounded parameters only: the server rejects anything but enabled, window and interval. */
export const configureSmaStop = (body: { enabled: true; sma_window_bars: number; bar_interval: string } | { enabled: false }, signal?: AbortSignal) =>
  postJson(`${BASE}/configure`, body, SmaStopConfigSchema, { signal });
export const evaluateSmaStop = (instrument_id: string, signal?: AbortSignal) => postJson(`${BASE}/evaluate`, { instrument_id }, SmaStopStatusSchema, { signal });
export const smaStopHistory = (instrument: string, limit = 20, signal?: AbortSignal) =>
  fetchJson(`${BASE}/history?instrument=${encodeURIComponent(instrument)}&limit=${limit}`, History, { signal });
export const smaStopEvaluation = (signal?: AbortSignal) => fetchJson(`${BASE}/evaluation`, SmaStopEvaluationSchema, { signal });
