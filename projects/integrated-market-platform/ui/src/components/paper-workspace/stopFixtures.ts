import type { SmaStopConfig, SmaStopEvaluationResult, SmaStopStatus } from "../../api/paperRiskControl";

/** Test fixtures shaped exactly like the OCT1-08 server projections. */
export const stopPolicy = {
  schema_version: "sma-trailing-stop-policy/1.0.0", policy_id: "STP-reference", method: "SMA_TRAILING", sma_window_bars: 20, bar_interval: "1m",
  session_scope: "RTH", price_basis: "COMPLETED_BAR_CLOSE", config_label: "REFERENCE_TEST_CONFIG", update_timing: "AFTER_BAR_AVAILABLE",
  warmup_requirement: "FULL_WINDOW_OF_COMPLETED_BARS", long_behavior: "ACTIVE=MAX(PREVIOUS_ACTIVE,CANDIDATE)", short_behavior: "ACTIVE=MIN(PREVIOUS_ACTIVE,CANDIDATE)",
} as const;

export const stopConfig: SmaStopConfig = {
  schema_version: "sma-stop-config/1.0.0", configured: true, enabled: true, policy: stopPolicy,
  reference_config: { sma_window_bars: 20, bar_interval: "1m", label: "REFERENCE_TEST_CONFIG", note: "Reference software-evaluation configuration. Not optimized, calibrated or recommended." },
  bounds: { sma_window_bars: [2, 200], bar_interval: ["1m", "5m", "15m"] }, durability: "SQLITE_LOCAL_STATE",
};

const stop = {
  stop_state_id: "STS-1", position_epoch_id: "PE-1", epoch_basis: "LEDGER_OPENING_FILL", side: "LONG" as const, quantity: 7, policy_id: "STP-reference",
  sma_window_bars: 20, bar_interval: "1m", config_label: "REFERENCE_TEST_CONFIG", activated_at: "2026-10-05T14:20:00Z", activation_reason: "POSITION_OPENED",
  sma_value: "184.7300", candidate_stop: "184.73", active_stop: "185.12", previous_stop: "184.9", stop_as_of: "2026-10-05T14:42:00Z", bar_id: "B42",
  bar_available_at: "2026-10-05T14:42:00Z", bars_available: 42, last_updated_at: "2026-10-05T14:40:00Z", last_evaluated_at: "2026-10-05T14:42:05Z",
  update_count: 22, tighten_count: 9, clamp_count: 3, trigger_state: "ARMED", trigger_reason_codes: [] as string[], triggered_at: null, trigger_price: null,
  trigger_evidence: null, trigger_basis: "LAST_TRADE_PRICE", bar_source: { state: "CURRENT", reason: null, source: "MOOMOO_OPEND_CUR_KLINE_1M" },
  carried_from: null, closed_at: null, closed_reason: null, reference_price: "187.4", reference_as_of: "2026-10-05T14:42:04Z", distance_to_stop: "2.28",
  distance_bps: 121.7, exit_decision: null,
};

export function stopStatus(overrides: Partial<SmaStopStatus> = {}, stopOverrides: Record<string, unknown> | null = {}): SmaStopStatus {
  return {
    schema_version: "sma-stop-status/1.0.0", instrument_id: "NVDA", account_id: "paper", method: "SMA_TRAILING", status: "ACTIVE", reason_codes: ["MONOTONIC_CLAMP"],
    policy: stopPolicy, position: { state: "LONG", quantity: 7 }, stop: stopOverrides === null ? null : { ...stop, ...stopOverrides },
    monitoring: { state: "RUNNING", worker_state: "RUNNING", last_evaluated_at: "2026-10-05T14:42:05Z", liveness: "OBSERVED" }, durability: "SQLITE_LOCAL_STATE",
    paper_execution: "MANUAL_ONLY", paper_close: "NOT_SUBMITTED", live_execution: "UNCHANGED", order_type: "NONE_STOP_MONITOR_ONLY",
    evaluated_at: "2026-10-05T14:42:06Z", ...overrides,
  } as SmaStopStatus;
}

export const breachedStatus = (decision: Record<string, unknown> | null = { decision_id: "AD-exit", action_state: "EXIT", execution_readiness: "PREVIEW_ALLOWED", blocker_codes: [], decision_time: "2026-10-05T14:45:01Z" }) =>
  stopStatus({ status: "BREACHED", reason_codes: ["SMA_TRAILING_STOP_BREACHED"] }, {
    active_stop: "186.1", previous_stop: "185.12", trigger_state: "BREACHED", triggered_at: "2026-10-05T14:45:00Z", trigger_price: "185.95",
    trigger_evidence: { kind: "QUOTE", basis: "LAST_TRADE_PRICE", source: "MOOMOO", evidence_ref: "q", bar_id: "B44", as_of: "2026-10-05T14:45:00Z" }, exit_decision: decision,
  });

const aggregate = (overrides: Record<string, number | null>) => ({
  episodes: 31, stop_frequency: 1, mean_gross_return_bps: -1.53, median_gross_return_bps: -6.55, mean_net_return_bps: -11.53, mean_mae_bps: 7.34,
  median_mae_bps: 6.57, mean_max_drawdown_bps: 12.18, worst_drawdown_bps: 30.22, loss_severity_bps: -8.86, premature_exit_frequency: 0.4839,
  mean_holding_bars: 7.42, mean_bars_after_invalidation: 0, gap_through_stop_events: 1, ...overrides,
});

export const evaluationReceipt: SmaStopEvaluationResult = {
  schema_version: "sma-stop-evaluation/1.0.0", result_status: "REPLAY_EVALUATED", experiment_id: "oct1-08-sma-trailing-stop-replay-v1", evidence_class: "HISTORICAL_REPLAY",
  calibration_status: "NOT_CALIBRATED", definition_hash: "def-hash", input_hash: "input-hash", result_hash: "result-hash", corpus_unchanged: true, primary_side: "LONG",
  policy: { policy_id: "STP-reference", sma_window_bars: 20, bar_interval: "1m", config_label: "REFERENCE_TEST_CONFIG" },
  fill_model: { id: "stop-exit-bar-conservative/1.0.0", primary: "STOP_EXIT_AT_TRIGGER_BAR_WORST_PRICE", cost_bps_per_side: 5 },
  provenance: { corpus_path: "evidence/historical-research/corpus_pin", dataset_fingerprint: "B655", corpus_evidence_label: "HISTORICAL_DEVELOPMENT", normalized_sha256: "sha",
    session_dates: ["2026-09-10", "2026-09-11"] },
  corpus: { sessions: ["2026-09-10", "2026-09-11"], bars: 780, instruments: 1 },
  counts: { episodes: 120, evaluable: 59, excluded: 61, exclusions: { INITIAL_STOP_NOT_PROTECTIVE: 61 }, evaluable_by_side: { LONG: 31, SHORT: 28 } },
  aggregates: {
    LONG: { SMA_TRAIL: aggregate({}), RAW_PRICE_TRAIL: aggregate({ mean_mae_bps: 8.26, mean_gross_return_bps: -2.78 }),
      FIXED_INITIAL_STOP: aggregate({ mean_mae_bps: 10.97, stop_frequency: 0.9355 }), NO_TRAIL: aggregate({ mean_mae_bps: 47.16, mean_gross_return_bps: 16.17, stop_frequency: 0, premature_exit_frequency: 0 }) },
    SHORT: { SMA_TRAIL: aggregate({ episodes: 28 }), NO_TRAIL: aggregate({ episodes: 28, stop_frequency: 0 }) },
  },
  comparisons: [{ alternative: "RAW_PRICE_TRAIL", sessions: 5, downside: "BETTER", returns: "BETTER", pattern: "NO_CLEAR_DIFFERENCE" }],
  conclusion: { conclusion: "INSUFFICIENT_EVIDENCE", in_sample_pattern: "NO_CLEAR_DIFFERENCE", in_sample_pattern_status: "DESCRIPTION_ONLY_NOT_A_CLAIM", sessions: 5, instruments: 1,
    superiority_claim: "NONE", statement: "Evidence is insufficient for a directional or superiority claim." },
  sample_size_note: "Small sample: overlapping episodes from few sessions of one instrument. Descriptive only.", episode_count: 120,
};
