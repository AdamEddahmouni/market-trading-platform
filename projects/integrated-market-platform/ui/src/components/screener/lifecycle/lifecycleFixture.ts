import type { LifecycleDecision, TradeLifecycle, TradeLifecycleList } from "../../../api/screenerLifecycle";

/** Shaped exactly like the OCT1-10 server projection (`trade-lifecycle/1.0.0`). Controlled fixture values only. */

const item = (id: string, capability: string, fact: string, extra: Record<string, unknown> = {}) => ({
  evidence_id: id, capability, fact, source: "CONTROLLED_FIXTURE", as_of: "2026-10-06T14:28:00Z", freshness_status: "CURRENT", delivery_mode: "REALTIME",
  role: "CURRENT_MARKET", decision_admissibility: "ADMISSIBLE", valid_until: "2026-10-06T14:38:00Z", weak_reasons: [], ...extra,
});
export const evidenceDetail = {
  counts: { supporting: 2, conflicting: 2, weak: 0, missing: 1, blocked: 1 },
  supporting: { items: [item("q", "QUOTE", "price: 150.0"), item("t", "TECHNICALS", "change_pct: 2")], truncated: 0 },
  conflicting: { items: [item("news-conflict", "SENTIMENT", "label: NEGATIVE", { freshness_status: "PUBLICATION_CURRENT", delivery_mode: "PUBLICATION_BASED", role: "REFERENCE_CONTEXT" })], truncated: 0 },
  weak: { items: [], truncated: 0 },
  conflicting_alignments: [{ alignment_id: "AL-1", kind: "NEWS_SENTIMENT_VS_PRICE", result: "CONFLICTING", observed_direction: "POSITIVE", limitations: ["Fixture conflict"] }],
  missing: ["OPTIONS"],
  blocked: [{ capability: "LEVEL2", source: "CONTROLLED_FIXTURE", as_of: "2026-10-06T14:13:00Z", freshness_status: "STALE", reason_codes: ["AGE_EXCEEDS_POLICY"] }],
  blocked_truncated: 0,
};

export function decision(overrides: Partial<LifecycleDecision> = {}): LifecycleDecision {
  return {
    decision_id: "AD-1", action_state: "ENTER", decision_time: "2026-10-06T14:30:00Z", decision_cutoff: "2026-10-06T14:30:00Z", valid_until: "2099-01-01T00:00:00Z",
    direction: "LONG", rationale: "Observed positive price change supports this assessment.", origin: "AI_PROPOSAL_SERVER_GATED", ai_proposal_state: "ENTER",
    model: { provider_id: "fixture", model_id: "controlled", prompt_id: "screener.action_decision.v1", called: true },
    execution_readiness: "PREVIEW_ALLOWED", blocker_codes: [], reason_codes: ["BOUNDED_PROPOSAL_ACCEPTED"], previous_state: null,
    position_at_decision: { state: "FLAT", quantity: 0 }, reference_price: "150.0", reference_as_of: "2026-10-06T14:30:00Z", candidate_run_id: "run-1", risk_exit: null,
    ...overrides,
  };
}

const fill = (overrides: Record<string, unknown> = {}) => ({
  fill_id: "F-open", order_id: "O-1", kind: "SIMULATED_PAPER_FILL" as const, price_minor: 15020, time: "2026-10-06T14:31:14Z", submitted_at: "2026-10-06T14:31:10Z",
  quantity: 6, side: "BUY", position_effect: "OPEN", decision_id: "AD-1", decision_source: "AI_DECISION_GOVERNED", is_market_truth: false as const, ...overrides,
});

/** A flat AI-selected candidate with an ENTER decision and no Paper fill. */
export function lifecycle(overrides: Partial<TradeLifecycle> = {}): TradeLifecycle {
  return {
    schema_version: "trade-lifecycle/1.0.0", lifecycle_id: "LC-aapl", kind: "CANDIDATE", group: "SELECTED", instrument_id: "AAPL", symbol: "AAPL",
    stage: "ENTER_NOT_EXECUTED", ai_selected: true, position_origin: null,
    candidate: { selected: true, selected_in_current_run: true, rank: 1, run_id: "run-1", run_state: "CURRENT", selected_at: "2026-10-06T14:28:00Z",
      decision_cutoff: "2026-10-06T14:28:00Z", valid_until: "2099-01-01T00:00:00Z", rationale: "AAPL shows observed strength.", uncertainties: [],
      provider_id: "fixture", model_id: "controlled", prompt_id: "screener.ai_candidate_reduction.v2", prompt_version: "2", simulated: true, lineage: "CANDIDATE_RUN",
      evidence: { counts: evidenceDetail.counts } },
    decision: decision(),
    entry: { status: "DECIDED_ENTER", decision_reference: { decision_id: "AD-1", decision_time: "2026-10-06T14:30:00Z", price: "150.0", as_of: "2026-10-06T14:30:00Z" },
      fill: null, fill_count: 0, quantity: null, average_price_minor: null, paper: "NO_FILL" },
    position: { state: "FLAT", quantity: 0, mark: null },
    risk_control: { method: "SMA_TRAILING_STOP", origin: "DETERMINISTIC_RISK_CONTROL", model: "none", status: "NOT_APPLICABLE", configured: false, reason_codes: [],
      policy: null, stop: null, exit_decision_id: null, lineage: "NOT_APPLICABLE" },
    exit: { status: "NO_EXIT", decision_reference: null, fill: null, fill_count: 0, closed_quantity: null, average_price_minor: null, paper_close: "NOT_APPLICABLE" },
    pnl: { realized_minor: null, unrealized_minor: null, costs_minor: null, quality: "NOT_APPLICABLE", currency: "USD", basis: "PAPER_LEDGER_FILLS", realized_includes_costs: true },
    origin: { run_id: "run-1", same_as_current_run: true, lineage: "CANDIDATE_RUN" },
    freshness: { projection: "DERIVED_ON_READ", decision_valid_until: "2099-01-01T00:00:00Z", decision_current: true, mark_quality: null },
    lineage: { basis: "CANDIDATE_RUN_ID", account_id: "acct", experiment_id: "PPE-1", episode_id: null, opening_fill_id: null, opening_decision_id: null,
      opening_basis: null, origin_run_id: "run-1", decision_count: 1, stop_state_ids: [], candidate: "CANDIDATE_RUN" },
    limitations: [], as_of: "2026-10-06T14:32:00Z", currency: "USD", price_scale: 100,
    ...overrides,
  };
}

const activeStop = { stop_state_id: "STS-1", sma_value: "140", active_stop: "140", previous_stop: "139.5", distance_to_stop: "11", distance_bps: 728.5,
  last_updated_at: "2026-10-06T14:45:00Z", stop_as_of: "2026-10-06T14:45:00Z", reference_price: "151", trigger_price: null, triggered_at: null, closed_reason: null };

/** LONG 6 opened by a simulated Paper fill, currently HOLD, with an active SMA stop. */
export function openPosition(overrides: Partial<TradeLifecycle> = {}): TradeLifecycle {
  return lifecycle({
    lifecycle_id: "TE-aapl-1", kind: "POSITION_EPISODE", stage: "POSITION_OPEN", position_origin: "AI_DECISION_GOVERNED",
    decision: decision({ decision_id: "AD-2", action_state: "HOLD", ai_proposal_state: "HOLD", decision_time: "2026-10-06T14:47:00Z", execution_readiness: "NOT_PREVIEWED",
      previous_state: "ENTER", position_at_decision: { state: "LONG", quantity: 6 }, reference_price: "151.0" }),
    entry: { status: "FILLED", decision_reference: { decision_id: "AD-1", decision_time: "2026-10-06T14:30:00Z", price: "150.0", as_of: "2026-10-06T14:30:00Z" },
      fill: fill(), fill_count: 1, quantity: 6, average_price_minor: 15020, paper: "SIMULATED_FILL" },
    position: { state: "LONG", quantity: 6, average_entry_minor: 15020, first_entry_time: "2026-10-06T14:31:14Z", latest_fill_time: "2026-10-06T14:31:14Z", market_value_minor: 90600,
      mark: { price_minor: 15100, as_of: "2026-10-06T14:47:58Z", source: "MOOMOO", source_quality: "PASS", age_ms: 2000, quality: "CURRENT" } },
    risk_control: { method: "SMA_TRAILING_STOP", origin: "DETERMINISTIC_RISK_CONTROL", model: "none", status: "ACTIVE", configured: true, reason_codes: [],
      policy: { policy_id: "STP-1", sma_window_bars: 20, bar_interval: "1m" }, stop: activeStop, exit_decision_id: null, lineage: "STOP_STATE", monitoring: "RUNNING" },
    exit: { status: "NO_EXIT", decision_reference: null, fill: null, fill_count: 0, closed_quantity: null, average_price_minor: null, paper_close: "NOT_SUBMITTED" },
    pnl: { realized_minor: 0, unrealized_minor: 480, costs_minor: 0, quality: "CURRENT", currency: "USD", basis: "PAPER_LEDGER_FILLS", realized_includes_costs: true },
    freshness: { projection: "DERIVED_ON_READ", decision_valid_until: "2099-01-01T00:00:00Z", decision_current: true, mark_quality: "CURRENT" },
    lineage: { basis: "PAPER_FILL_AND_DECISION_IDS", account_id: "acct", experiment_id: "PPE-1", episode_id: "TE-aapl-1", opening_fill_id: "F-open", opening_decision_id: "AD-1",
      opening_basis: "LEDGER_OPEN_FILL", origin_run_id: "run-1", decision_count: 2, stop_state_ids: ["STS-1"], candidate: "CANDIDATE_RUN" },
    ...overrides,
  });
}

/** The same episode after a deterministic stop breach: EXIT decided, no close fill yet. */
export function breachedPosition(overrides: Partial<TradeLifecycle> = {}): TradeLifecycle {
  const open = openPosition();
  const exitDecision = decision({ decision_id: "AD-3", action_state: "EXIT", decision_time: "2026-10-06T15:21:00Z", direction: null, origin: "DETERMINISTIC_RISK_CONTROL",
    ai_proposal_state: null, model: null, rationale: "Deterministic SMA trailing-stop risk condition. Server-authored; no model call.", previous_state: "HOLD",
    reason_codes: ["SMA_TRAILING_STOP_BREACHED", "SERVER_RISK_EXIT"], position_at_decision: { state: "LONG", quantity: 6 }, reference_price: "139.0",
    risk_exit: { reason: "DETERMINISTIC_SMA_TRAILING_STOP_RISK_CONDITION", stop_state_id: "STS-1", policy_id: "STP-1", active_stop: "140", trigger_price: "139", triggered_at: "2026-10-06T15:21:00Z" } });
  return openPosition({
    stage: "EXIT_NOT_EXECUTED", decision: exitDecision,
    risk_control: { ...open.risk_control, status: "BREACHED", reason_codes: ["SMA_TRAILING_STOP_BREACHED"], exit_decision_id: "AD-3",
      stop: { ...activeStop, trigger_price: "139", triggered_at: "2026-10-06T15:21:00Z" } },
    exit: { status: "EXIT_DECIDED", decision_reference: { decision_id: "AD-3", decision_time: "2026-10-06T15:21:00Z", price: "139.0", as_of: "2026-10-06T15:21:00Z" },
      fill: null, fill_count: 0, closed_quantity: null, average_price_minor: null, paper_close: "NOT_SUBMITTED" },
    ...overrides,
  });
}

/** The episode after the simulated close fill. */
export function closedEpisode(overrides: Partial<TradeLifecycle> = {}): TradeLifecycle {
  const breached = breachedPosition();
  return breachedPosition({
    stage: "POSITION_CLOSED", group: "RECENT_CLOSED", position: { state: "FLAT", quantity: 0, mark: null, closed: true },
    candidate: { ...breached.candidate!, selected_in_current_run: false },
    exit: { ...breached.exit, status: "CLOSED", paper_close: "FILLED", fill_count: 1, closed_quantity: 6, average_price_minor: 13870,
      fill: fill({ fill_id: "F-close", order_id: "O-2", price_minor: 13870, time: "2026-10-06T15:22:04Z", side: "SELL", position_effect: "CLOSE", decision_id: "AD-3" }) },
    risk_control: { ...breached.risk_control, status: "CLOSED" },
    pnl: { realized_minor: -6900, unrealized_minor: null, costs_minor: 0, quality: "REALIZED", currency: "USD", basis: "PAPER_LEDGER_FILLS", realized_includes_costs: true },
    freshness: { projection: "DERIVED_ON_READ", decision_valid_until: "2026-10-06T15:31:00Z", decision_current: false, mark_quality: null },
    ...overrides,
  });
}

/** The expanded projection for a lifecycle: frozen evidence, every decision and the ordered history. */
export function detailOf(summary: TradeLifecycle, overrides: Partial<TradeLifecycle> = {}): TradeLifecycle {
  const enter = decision({ entry_conditions: [
    { condition_id: "CURRENT_QUOTE", status: "MET", source: "SERVER_ACTION_POLICY", valid_until: "2026-10-06T14:40:00Z", reason_codes: [] },
    { condition_id: "DIRECTION_SUPPORTED", status: "MET", source: "SERVER_ACTION_POLICY", valid_until: "2026-10-06T14:40:00Z", reason_codes: [] }],
    hold_conditions: [], exit_conditions: [], evidence_snapshot_id: "AS-1", decision_trace_id: "DT-1", opportunity_id: "opp-1", evidence: evidenceDetail });
  const decisions = summary.decision && summary.decision.decision_id !== "AD-1" ? [enter, { ...summary.decision, entry_conditions: [], hold_conditions: [], exit_conditions: [],
    evidence: { ...evidenceDetail, supporting: { items: [item("q2", "QUOTE", "price: 151.0")], truncated: 0 } } }] : [enter];
  return {
    ...summary,
    candidate: summary.candidate ? { ...summary.candidate, evidence: evidenceDetail } : null,
    entry: { ...summary.entry, fills: summary.entry.fill ? [summary.entry.fill] : [] },
    exit: { ...summary.exit, fills: summary.exit.fill ? [summary.exit.fill] : [] },
    decisions, decisions_truncated: 0,
    timeline: [
      { kind: "CANDIDATE_SELECTED", at: "2026-10-06T14:28:00Z", event: "Candidate selected", source: "AI Screener", reason: "Rank #1", ref: { type: "CANDIDATE_RUN", id: "run-1" }, clocks: {} },
      { kind: "DECISION", at: "2026-10-06T14:30:00Z", event: "Action decision: ENTER", source: "AI proposal, server-gated", reason: enter.rationale, reason_codes: [], ref: { type: "ACTION_DECISION", id: "AD-1" }, clocks: {} },
      ...(summary.entry.fill ? [{ kind: "PAPER_FILL" as const, at: summary.entry.fill.time, event: "Paper simulated fill — position opened", source: "Paper ledger", reason: "BUY 6 @ 150.20", ref: { type: "PAPER_FILL", id: "F-open" }, clocks: {} }] : []),
      ...(decisions.length > 1 ? [{ kind: "DECISION" as const, at: decisions[1].decision_time, event: `${decisions[1].origin === "DETERMINISTIC_RISK_CONTROL" ? "Risk control" : "Reevaluation"}: ${decisions[1].action_state}`,
        source: decisions[1].origin === "DETERMINISTIC_RISK_CONTROL" ? "Deterministic risk control" : "AI proposal, server-gated", reason: decisions[1].rationale, reason_codes: decisions[1].reason_codes.filter((code) => code !== "BOUNDED_PROPOSAL_ACCEPTED"),
        ref: { type: "ACTION_DECISION", id: decisions[1].decision_id }, clocks: {} }] : []),
      ...(summary.exit.fill ? [{ kind: "PAPER_FILL" as const, at: summary.exit.fill.time, event: "Paper simulated close fill — position closed", source: "Paper ledger", reason: "SELL 6 @ 138.70", ref: { type: "PAPER_FILL", id: "F-close" }, clocks: {} }] : []),
    ],
    timeline_truncated: 0, prior_episodes: [], prior_episodes_truncated: 0,
    reevaluation: { worker_state: "RUNNING", worker_label: "Running", requested_cadence_seconds: 60, effective_cadence_seconds: 120, last_completed: "2026-10-06T14:42:00Z" },
    experiment: { experiment_id: "PPE-1", name: "OCT1-10", status: "ACTIVE", capital_kind: "SIMULATED", live_capital: false, execution: "INTERNAL_SIMULATION",
      market_data: "LIVE_OBSERVATIONAL", equity_minor: 10000480, cash_minor: 9909880, valuation_quality: "CURRENT" },
    ...overrides,
  };
}

export function lifecycleList(overrides: Partial<TradeLifecycleList> = {}): TradeLifecycleList {
  return {
    schema_version: "trade-lifecycle-list/1.0.0", as_of: "2026-10-06T14:48:00Z", account_id: "acct", experiment_id: "PPE-1", currency: "USD", price_scale: 100,
    run: null, selected: [], active_managed: [], recent_closed: [], unlinked: [], counts: { selected: 0, active_managed: 0, recent_closed: 0, unlinked: 0 },
    next_closed_before: null,
    experiment: { experiment_id: "PPE-1", name: "OCT1-10", status: "ACTIVE", capital_kind: "SIMULATED", live_capital: false, execution: "INTERNAL_SIMULATION",
      market_data: "LIVE_OBSERVATIONAL", equity_minor: 10000480, cash_minor: 9909880, valuation_quality: "CURRENT" },
    reevaluation: { worker_state: "RUNNING", worker_label: "Running", requested_cadence_seconds: 60, effective_cadence_seconds: 120, last_completed: "2026-10-06T14:42:00Z" },
    market_data: "LIVE_OBSERVATIONAL", execution: "SIMULATED_PAPER", limitations: [],
    ...overrides,
  } as TradeLifecycleList;
}
