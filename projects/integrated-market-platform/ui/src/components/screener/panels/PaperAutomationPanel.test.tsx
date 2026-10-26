import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PaperAutomationPanel from "./PaperAutomationPanel";
import { PaperAutomationStatusSchema } from "../../../api/paperAutomation";

const api = vi.hoisted(() => ({ status: vi.fn(), history: vi.fn(), report: vi.fn(), configure: vi.fn(), arm: vi.fn(), disarm: vi.fn(), start: vi.fn(),
  pause: vi.fn(), resume: vi.fn(), stop: vi.fn(), emergency: vi.fn() }));
vi.mock("../../../api/paperAutomation", async (original) => ({ ...(await original<typeof import("../../../api/paperAutomation")>()),
  paperAutomationStatus: api.status, paperAutomationHistory: api.history, paperAutomationReport: api.report, configurePaperAutomation: api.configure,
  armPaperAutomation: api.arm, disarmPaperAutomation: api.disarm, startPaperAutomation: api.start, pausePaperAutomation: api.pause,
  resumePaperAutomation: api.resume, stopPaperAutomation: api.stop, emergencyStopPaperAutomation: api.emergency }));

const scope = { universe: "US_EQUITIES", search: "", sort: "symbol", descending: false, filters: [] } as never;
const boundary = { execution: "INTERNAL_PAPER_SIMULATION_ONLY", live_capital: false, real_money_order_routes: "NOT_REACHABLE_FROM_AUTOMATION",
  execution_mode: "INTERNAL_SIMULATION", execution_provider: "INTERNAL", execution_authority: "PAPER_ONLY" };
const session = { label: "REGULAR", trading_day: true, session_date: "2026-10-05", minutes_to_close: 300, early_close_metadata: "UNAVAILABLE" };
const bare = { schema_version: "paper-automation-status/1.0.0", status: "NOT_CONFIGURED", status_label: "Not configured", required_configuration: ["scope"],
  arm_acknowledgement: "ARM_PAPER_ONLY_AUTOMATION", session, boundary, identity_blockers: [], durability: "SQLITE_LOCAL_STATE", evaluated_at: "2026-10-05T14:00:00Z" };
const policy = { policy_id: "PAP-1", account_id: "paper", experiment_id: "PPE-1",
  schedule: { sessions: ["REGULAR"], cadence_seconds: 60, universe_evaluation_interval_seconds: 1800, no_new_entries_minutes_before_close: 15 },
  risk: { max_position_notional_minor: 500000, max_aggregate_exposure_minor: 1000000, max_open_positions: 2, max_daily_loss_minor: 100000, max_per_trade_risk_minor: 10000,
    assumed_adverse_move_bps: 200, allowed_universes: ["US_EQUITIES"], order_types: ["MARKET"], allow_long: true, allow_short: false, allow_entries: true, allow_exits: true },
  exits: { on_stop_breach: true, on_thesis_exit: true },
  ai: { allow_local_inference: true, allow_paid_inference: false, max_paid_requests_per_day: 0, max_paid_tokens_per_day: 0 }, emergency_stop: { max_consecutive_failures: 3 } };
const liveness = { owner: null, worker_alive: false, heartbeat_at: null, lease_until: null, cycle_count: 0, consecutive_failures: 0, last_error: null, last_scheduled: null };
const risk = { open_positions: 0, max_open_positions: 2, exposure_minor: 0, max_aggregate_exposure_minor: 1000000, day_pnl_minor: null, max_daily_loss_minor: 100000,
  valuation_quality: "CURRENT", equity_minor: 10000000, realized_pnl_minor: 0, unrealized_pnl_minor: 0, total_pnl_minor: 0 };
const engine = { state: "AVAILABLE", reason: null, provider_id: "fixture", model_id: "controlled", runtime: "LOCAL_MODEL", budget: null };
const disarmed = { ...bare, status: "DISARMED", status_label: "Configured — not armed", blockers: [], policy, armed: false, arming: null, emergency: null, desired_state: "STOPPED",
  liveness, last_cycle: null, universe: { active_run_id: null, last_result: null, adopted_run_id: null }, candidate_quotes: [], risk, positions: [], working_orders: [],
  recent_intents: [], provider: null, engine, spending: { allowed: true, reason: null } };
const arming = { arming_id: "PAA-1", policy_id: "PAP-1", armed_at: "2026-10-05T14:01:00Z", operator: null, scope: "INTERNAL_PAPER_SIMULATION_ONLY" };
const stopped = { ...disarmed, status: "STOPPED", status_label: "Stopped", armed: true, arming };
const cycle = { cycle_id: "PAC-1", status: "RUNNING", scheduled_for: "2026-10-05T14:05:00Z", error: null, blockers: [], missed_cycles_before: 0,
  reevaluation: { cycle_status: "MATERIAL_CHANGE", position_count: 1, candidate_count: 1, model_call_count: 1 },
  actions: [{ decision_id: "AD-1", instrument_id: "AAPL", action: "ENTER", outcome: "SUBMITTED", reason_codes: ["PAPER_ORDER_SUBMITTED_INTERNAL_SIMULATION"],
    quantity: 6, side: "BUY", order_state: "FILLED", filled_quantity: 6, fill_price_minor: 15000 }] };
const running = { ...stopped, status: "RUNNING", status_label: "Running — evaluating and able to submit Paper orders", desired_state: "RUNNING",
  liveness: { ...liveness, owner: "THIS_PROCESS", worker_alive: true, heartbeat_at: "2026-10-05T14:05:01Z", cycle_count: 4, last_scheduled: "2026-10-05T14:05:00Z" },
  last_cycle: cycle, provider: { state: "CONNECTED", reasons: [] }, candidate_quotes: ["AAPL"],
  universe: { active_run_id: null, adopted_run_id: "CU-1", last_result: { run_id: "AIR-1", status: "GLOBAL_SELECTION_COMPLETE", reason: null, universe_count: 7000,
    ai_evaluated_count: 7000, ai_coverage_pct: 100, coverage_complete: true, adopted: true, selected: ["AAPL"] } },
  risk: { ...risk, open_positions: 1, exposure_minor: 90000, day_pnl_minor: -600 },
  positions: [{ instrument_id: "AAPL", side: "LONG", quantity: 6, average_fill_minor: 15000, mark_minor: 14900, unrealized_pnl_minor: -600 }],
  recent_intents: [{ intent_id: "PAI-1", decision_id: "AD-1", instrument_id: "AAPL", action: "ENTER", state: "SUBMITTED", reason_codes: ["PAPER_ORDER_SUBMITTED_INTERNAL_SIMULATION"],
    decision_origin: "MODEL_PROPOSAL_GATED", quantity: 6, side: "BUY", order_state: "FILLED", filled_quantity: 6, fill_price_minor: 15000, updated_at: "2026-10-05T14:05:00Z" }] };
// One primary status, two simultaneous truths: the regular session is closed AND spending is not authorized.
// The waiting label must not read as "nothing else is wrong".
const waitingWithBlocker = { ...running, status: "WAITING_FOR_MARKET", status_label: "Waiting for the configured market session",
  blockers: [{ category: "BUDGET", code: "AUTONOMOUS_SPENDING_NOT_AUTHORIZED" }], spending: { allowed: false, reason: "AUTONOMOUS_SPENDING_NOT_AUTHORIZED" } };
const report = { schema_version: "paper-automation-report/1.0.0", evidence_class: "SIMULATED_PAPER_FILLS_NOT_MARKET_TRUTH",
  statement: "Paper P&L is accounting of simulated fills against observed prices. It is not evidence of a profitable strategy or a durable edge, and this report changes no policy, limit, model or method.",
  fills: { count: 1, opening: 1, closing: 0, costs_minor: 0, slippage_model: "NOT_SEPARATELY_MODELED" },
  outcomes: { closed_fills: 0, wins: 0, losses: 0, flat: 0, realized_pnl_minor: 0, sample_note: "Counts are fill-level and small samples say nothing about expectancy." },
  portfolio: { equity_minor: 9999400, realized_pnl_minor: 0, unrealized_pnl_minor: -600, total_pnl_minor: -600, exposure_minor: 89400, open_positions: 1,
    max_drawdown_minor_last_snapshots: 600, valuation_quality: "CURRENT" },
  decisions: { intents: 2, submitted: 1, refused_or_deferred: 1, refusal_reasons: { ENTRY_WINDOW_CLOSED: 1 }, by_origin: { MODEL_PROPOSAL_GATED: 2, DETERMINISTIC_RISK_CONTROL: 0 } },
  ai: { universe_runs: 1, complete_runs: 1, incomplete_runs: 0, tokens_input: 1200, tokens_output: 300, models: ["controlled"], reevaluation_model_calls_last_day: 1 },
  generated_at: "2026-10-05T14:06:00Z" };
const events = [{ sequence: 3, at: 3, kind: "PAPER_INTENT_SUBMITTED", at_iso: "2026-10-05T14:05:00Z", instrument_id: "AAPL", reason_codes: ["PAPER_ORDER_SUBMITTED_INTERNAL_SIMULATION"] },
  { sequence: 2, at: 2, kind: "NOT_OBSERVED", at_iso: "2026-10-05T14:02:00Z", reason: "PROCESS_DOWNTIME", observed_from: "2026-10-05T13:30:00Z", observed_to: "2026-10-05T14:02:00Z", missed_scheduled_cycles: 32 },
  { sequence: 1, at: 1, kind: "ARMED", at_iso: "2026-10-05T14:01:00Z" }];
// The adaptive scheduler reports its own decisions: what it decided last, why, and when the next attempt may start.
const scheduling = { policy: { min_separation_seconds: 1800, max_age_seconds: 3600, material_change_trigger: true, max_runs_per_day: 4,
  optional_fields: ["schedule.universe_max_age_seconds", "schedule.universe_material_change_trigger", "schedule.universe_max_runs_per_day"] },
  adaptive: true,
  last_decision: { decision: "SKIP", reason_codes: ["UNIVERSE_SELECTION_FRESH_AND_UNCHANGED"], next_eligible_epoch: 1791212400,
    next_eligible_iso: "2026-10-05T15:00:00Z", at_iso: "2026-10-05T14:05:00Z" },
  next_eligible: "2026-10-05T15:00:00Z", next_eligible_epoch: 1791212400,
  last_complete: { run_id: "AIR-1", finished_at: "2026-10-05T14:00:00Z", universe_count: 7000 },
  last_complete_fingerprint: { scope: "scope-digest", session_date: "2026-10-05", universe_count: 7000 },
  active_run_id: null, withheld: null, failure: null, runs_today: { started: 1, limit: 4 } };
const adaptiveRunning = { ...running, scheduling };
const numbers: [RegExp, string][] = [[/Evaluation cadence/, "60"], [/Full-universe AI evaluation interval/, "1800"], [/No new entries in the last/, "15"],
  [/Maximum position size/, "5000"], [/Maximum aggregate exposure/, "10000"], [/Maximum open positions/, "2"], [/Maximum daily loss/, "1000"],
  [/Maximum risk per trade/, "100"], [/Adverse move assumed/, "200"], [/Paid AI requests per day/, "0"], [/Paid AI tokens per day/, "0"], [/Consecutive failed cycles/, "3"]];
const choices: [RegExp, string][] = [[/^Automatic entries/, "yes"], [/^Long entries/, "yes"], [/^Short entries/, "no"], [/^Automatic exits/, "yes"],
  [/trailing-stop breach/, "yes"], [/gated decision is EXIT/, "yes"], [/Unattended local AI/, "yes"], [/Unattended paid AI/, "no"]];
const open = () => fireEvent.click(screen.getByRole("button", { name: "Open Paper automation controls" }));
const fill = (label: RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
afterEach(() => vi.resetAllMocks());

describe("Paper automation controls", () => {
  it("accepts the payloads the tests render (the fixtures match the server schema)", () => {
    for (const payload of [bare, disarmed, stopped, running, waitingWithBlocker, adaptiveRunning]) expect(PaperAutomationStatusSchema.safeParse(payload).success).toBe(true);
    expect(PaperAutomationStatusSchema.safeParse({ ...running, status: "TRADING" }).success).toBe(false);
    expect(PaperAutomationStatusSchema.safeParse({ ...running, boundary: { ...boundary, live_capital: true } }).success).toBe(false);
  });

  it("does nothing until opened and pre-fills no risk or spending value", async () => {
    api.status.mockResolvedValue(bare);
    render(<PaperAutomationPanel scope={scope} />);
    expect(api.status).not.toHaveBeenCalled();
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Automation: NOT_CONFIGURED — Not configured");
    expect(screen.getByText(/Internal Paper simulation only \(INTERNAL_SIMULATION · INTERNAL\)\. No real-money order route is reachable/)).toBeInTheDocument();
    for (const input of screen.getAllByRole("spinbutton")) expect(input).toHaveValue(null);
    for (const select of screen.getAllByRole("combobox")) expect(select).toHaveValue("");
    expect(screen.getByRole("button", { name: "Save policy" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Arm Paper automation" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
    for (const call of [api.configure, api.arm, api.start, api.history, api.report]) expect(call).not.toHaveBeenCalled();
  });

  it("saves exactly the owner's entries, in minor units, and saving arms nothing", async () => {
    api.status.mockResolvedValueOnce(bare).mockResolvedValue(disarmed); api.configure.mockResolvedValue(disarmed);
    api.history.mockResolvedValue({ events: [] }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    await screen.findByRole("status");
    const numbers: [RegExp, string][] = [[/Evaluation cadence/, "60"], [/Full-universe AI evaluation interval/, "1800"], [/No new entries in the last/, "15"],
      [/Maximum position size/, "5000"], [/Maximum aggregate exposure/, "10000"], [/Maximum open positions/, "2"], [/Maximum daily loss/, "1000"],
      [/Maximum risk per trade/, "100"], [/Adverse move assumed/, "200"], [/Paid AI requests per day/, "0"], [/Paid AI tokens per day/, "0"], [/Consecutive failed cycles/, "3"]];
    for (const [label, value] of numbers) fill(label, value);
    expect(screen.getByRole("button", { name: "Save policy" })).toBeDisabled();  // the yes/no decisions are still unanswered
    const choices: [RegExp, string][] = [[/^Automatic entries/, "yes"], [/^Long entries/, "yes"], [/^Short entries/, "no"], [/^Automatic exits/, "yes"],
      [/trailing-stop breach/, "yes"], [/gated decision is EXIT/, "yes"], [/Unattended local AI/, "yes"], [/Unattended paid AI/, "no"]];
    for (const [label, value] of choices) fill(label, value);
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await screen.findByText(/Position ≤ \$5,000\.00 · exposure ≤ \$10,000\.00 · open positions ≤ 2 · daily loss halt \$1,000\.00 · per-trade risk \$100\.00 at 200 bps/);
    expect(api.configure).toHaveBeenCalledWith(scope, { schedule: policy.schedule, risk: policy.risk, exits: policy.exits, ai: policy.ai, emergency_stop: policy.emergency_stop });
    expect(screen.getByRole("status")).toHaveTextContent("DISARMED — Configured — not armed");
    expect(api.arm).not.toHaveBeenCalled(); expect(api.start).not.toHaveBeenCalled();
    expect(screen.getByText(/A stop is not a guaranteed fill/)).toBeInTheDocument();
  });

  it("arms only after the exact acknowledgement is typed, and Start is a separate explicit step", async () => {
    api.status.mockResolvedValueOnce(disarmed).mockResolvedValueOnce(stopped).mockResolvedValue(running);
    api.history.mockResolvedValue({ events }); api.report.mockResolvedValue(report); api.arm.mockResolvedValue(stopped); api.start.mockResolvedValue(running);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    const arm = await screen.findByRole("button", { name: "Arm Paper automation" });
    expect(arm).toBeDisabled();
    fill(/Type ARM_PAPER_ONLY_AUTOMATION to arm/, "arm");
    expect(arm).toBeDisabled();
    fill(/Type ARM_PAPER_ONLY_AUTOMATION to arm/, "ARM_PAPER_ONLY_AUTOMATION");
    fireEvent.click(arm);
    await screen.findByText(/Armed 2026-10-05T14:01:00Z · authorization PAA-1 · Paper-only/);
    expect(api.arm).toHaveBeenCalledWith("PAP-1", "ARM_PAPER_ONLY_AUTOMATION");
    expect(api.start).not.toHaveBeenCalled();
    expect(screen.queryByRole("group", { name: /Owner policy/ })).not.toBeInTheDocument();  // limits cannot be edited while armed
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Automation: RUNNING — Running — evaluating and able to submit Paper orders"));
    expect(api.start).toHaveBeenCalledTimes(1);
  });

  it("shows session, provider, AI coverage, decisions, orders, positions, risk, results and audit history in text", async () => {
    api.status.mockResolvedValue(running); api.history.mockResolvedValue({ events }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    await screen.findByText(/Market session: REGULAR · 2026-10-05 · 300 min to the regular close/);
    expect(screen.getByText(/Provider: CONNECTED · AI engine: fixture · controlled · LOCAL_MODEL · AVAILABLE · unattended model calls permitted/)).toBeInTheDocument();
    expect(screen.getByText(/Last full-universe run AIR-1:/)).toHaveTextContent("GLOBAL SELECTION COMPLETE · AI evaluated 7000 of 7000 (100%) · selection adopted: AAPL");
    expect(screen.getByText(/reevaluation MATERIAL CHANGE · positions 1 · candidates 1 · model calls 1/)).toBeInTheDocument();
    expect(screen.getByText(/AAPL · ENTER · SUBMITTED · BUY 6 · order FILLED · filled 6 at \$150\.00 \(simulated\)/)).toBeInTheDocument();
    expect(screen.getByText(/Open positions 1\/2 · exposure \$900\.00 of \$10,000\.00 · day P&L −\$6\.00 \(halt at −\$1,000\.00\)/)).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /AAPL LONG 6 \$150\.00 \$149\.00 −\$6\.00/ })).toBeInTheDocument();
    expect(screen.getByText(/gated model proposal · PAPER_ORDER_SUBMITTED_INTERNAL_SIMULATION/)).toBeInTheDocument();
    expect(screen.getByText(/not evidence of a profitable strategy or a durable edge/)).toBeInTheDocument();
    expect(screen.getByText(/1 refused or deferred \(ENTRY_WINDOW_CLOSED ×1\)/)).toBeInTheDocument();
    expect(screen.getByText(/2026-10-05T13:30:00Z → 2026-10-05T14:02:00Z · 32 scheduled cycles missed · PROCESS_DOWNTIME · nothing was evaluated or ordered for this period/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pause" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
  });

  it("names a blocker that is open at the same time as a non-blocked primary status", async () => {
    api.status.mockResolvedValue(waitingWithBlocker); api.history.mockResolvedValue({ events }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Automation: WAITING_FOR_MARKET — Waiting for the configured market session");
    // The closed session must not hide the budget blocker the server also reports.
    expect(screen.getByText("Also open while the primary state is WAITING_FOR_MARKET: BUDGET · AUTONOMOUS_SPENDING_NOT_AUTHORIZED")).toBeInTheDocument();
    expect(screen.queryByText(/^Blocked by: /)).not.toBeInTheDocument();
  });

  it("never shows a blocked or stalled controller as running, and names why", async () => {
    const blocked = { ...running, status: "BLOCKED_BY_BUDGET", status_label: "Blocked — AI budget or spending authorization",
      blockers: [{ category: "BUDGET", code: "AUTONOMOUS_SPENDING_NOT_AUTHORIZED" }], spending: { allowed: false, reason: "AUTONOMOUS_SPENDING_NOT_AUTHORIZED" },
      universe: { active_run_id: null, adopted_run_id: null, withheld: { at: "2026-10-05T14:05:00Z", reason: "AUTONOMOUS_SPENDING_NOT_AUTHORIZED" },
        last_result: { run_id: "AIR-2", status: "PARTIAL_COVERAGE", reason: "AI_COVERAGE_STOPPED", universe_count: 7000, ai_evaluated_count: 50, ai_coverage_pct: 0.71,
          coverage_complete: false, adopted: false, selected: ["AAPL"] } } };
    api.status.mockResolvedValue(blocked); api.history.mockResolvedValue({ events: [] }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Automation: BLOCKED_BY_BUDGET — Blocked — AI budget or spending authorization");
    expect(screen.getByText("Blocked by: BUDGET · AUTONOMOUS_SPENDING_NOT_AUTHORIZED")).toBeInTheDocument();
    expect(screen.getByText(/unattended model calls withheld \(AUTONOMOUS_SPENDING_NOT_AUTHORIZED\)/)).toBeInTheDocument();
    expect(screen.getByText(/Last full-universe run AIR-2:/)).toHaveTextContent("AI evaluated 50 of 7000 (0.71%) · not adopted — coverage incomplete; no candidates were taken from it");
  });

  it("pauses, resumes, stops, disarms and emergency-stops explicitly; a latched emergency stop offers only Disarm", async () => {
    const paused = { ...running, status: "PAUSED", status_label: "Paused", desired_state: "PAUSED" };
    const latched = { ...stopped, status: "EMERGENCY_STOPPED", status_label: "Emergency stop — disarm to clear",
      emergency: { at: "2026-10-05T14:07:00Z", reason: "operator saw something wrong", source: "OPERATOR" } };
    api.status.mockResolvedValueOnce(running).mockResolvedValueOnce(paused).mockResolvedValueOnce(running).mockResolvedValue(latched);
    api.history.mockResolvedValue({ events }); api.report.mockResolvedValue(report);
    api.pause.mockResolvedValue(paused); api.resume.mockResolvedValue(running); api.emergency.mockResolvedValue({ ...latched, cancelled_orders: 0 }); api.disarm.mockResolvedValue(disarmed);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Pause" }));
    fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
    await screen.findByRole("button", { name: "Pause" });
    fill(/Emergency stop reason/, "operator saw something wrong");
    fireEvent.click(screen.getByRole("button", { name: "Emergency stop" }));
    expect(await screen.findByText(/Emergency stop latched 2026-10-05T14:07:00Z · operator saw something wrong \(OPERATOR\)\. Positions were not liquidated\. Disarm to clear it\./)).toBeInTheDocument();
    expect(api.emergency).toHaveBeenCalledWith("operator saw something wrong");
    for (const name of ["Start", "Pause", "Resume", "Arm Paper automation"]) expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Emergency stop" })).toBeDisabled();
    api.status.mockResolvedValue(disarmed);
    fireEvent.click(screen.getByRole("button", { name: "Disarm" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("DISARMED"));
    expect(api.disarm).toHaveBeenCalledTimes(1);
  });

  it("reports a rejected request without changing what is shown", async () => {
    api.status.mockResolvedValue(stopped); api.history.mockResolvedValue({ events: [] }); api.report.mockResolvedValue(report);
    api.start.mockRejectedValue(new Error("PAPER_RISK_POLICY_CHANGED"));
    render(<PaperAutomationPanel scope={scope} />);
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Start" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Paper automation request rejected: PAPER_RISK_POLICY_CHANGED");
    expect(screen.getByRole("status")).toHaveTextContent("Automation: STOPPED — Stopped");
    expect(within(screen.getByRole("region", { name: "Paper automation" })).getByRole("button", { name: "Start" })).toBeEnabled();
  });

  it("shows a failed history read as a read failure, never as an empty history", async () => {
    api.status.mockResolvedValue(stopped); api.history.mockRejectedValue(new Error("history unavailable")); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Audit history is unavailable: the history read failed. This does not mean no events were recorded.");
    expect(screen.queryByText("No events recorded.")).not.toBeInTheDocument();
    // The report read succeeded, so its own section still renders: only the failed read is called out.
    expect(screen.getByText(/not evidence of a profitable strategy or a durable edge/)).toBeInTheDocument();
    expect(screen.queryByText(/Simulated results are unavailable/)).not.toBeInTheDocument();
  });

  it("shows the adaptive scheduler's own decision state and starts nothing while doing so", async () => {
    api.status.mockResolvedValue(adaptiveRunning); api.history.mockResolvedValue({ events: [] }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Automation: RUNNING"));
    expect(screen.getByText(/^Adaptive · minimum separation 1800s · a selection stays useful for 3600s/)).toBeInTheDocument();
    expect(screen.getByText(/runs today 1 of 4/)).toBeInTheDocument();
    expect(screen.getByText(/Last complete selection from session 2026-10-05/)).toBeInTheDocument();
    expect(screen.getByText(/Last decision/)).toHaveTextContent(
      "Last decision SKIP at 2026-10-05T14:05:00Z because UNIVERSE SELECTION FRESH AND UNCHANGED · next eligible 2026-10-05T15:00:00Z.");
    for (const call of [api.configure, api.arm, api.start, api.pause, api.resume, api.stop, api.emergency, api.disarm]) expect(call).not.toHaveBeenCalled();
  });

  it("sends an adaptive scheduling field only when the owner supplied one", async () => {
    api.status.mockResolvedValueOnce(bare).mockResolvedValue(disarmed); api.configure.mockResolvedValue(disarmed);
    api.history.mockResolvedValue({ events: [] }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />);
    open();
    await screen.findByRole("status");
    for (const [label, value] of numbers) fill(label, value);
    for (const [label, value] of choices) fill(label, value);
    fill(/Maximum useful age of a complete selection/, "3600");
    fill(/Re-run when the evaluated universe materially changes/, "yes");
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(api.configure).toHaveBeenCalled());
    // The untouched "maximum runs per day" is absent, not defaulted: an omitted owner decision stays omitted.
    expect(api.configure.mock.calls[0][1].schedule).toEqual({ ...policy.schedule, universe_max_age_seconds: 3600, universe_material_change_trigger: true });
  });

  it("a poll tick only re-reads: it never evaluates, previews or submits", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      api.status.mockResolvedValue(running); api.history.mockResolvedValue({ events }); api.report.mockResolvedValue(report);
      render(<PaperAutomationPanel scope={scope} />);
      open();
      await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Automation: RUNNING"));
      const reads = api.status.mock.calls.length;
      await vi.advanceTimersByTimeAsync(15_000);  // at least three 5 s poll ticks
      expect(api.status.mock.calls.length).toBeGreaterThan(reads);
      for (const call of [api.configure, api.arm, api.start, api.pause, api.resume, api.stop, api.emergency, api.disarm]) expect(call).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
  it("requires all overnight settings and sends the dollar amount in minor units", async () => {
    api.status.mockResolvedValueOnce(bare).mockResolvedValue(disarmed); api.configure.mockResolvedValue(disarmed);
    api.history.mockResolvedValue({ events: [] }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />); open(); await screen.findByRole("status");
    for (const [label, value] of numbers) fill(label, value);
    for (const [label, value] of choices) fill(label, value);
    fill(/Maximum overnight positions/, "5");
    expect(screen.getByRole("button", { name: "Save policy" })).toBeDisabled();
    fill(/Maximum overnight exposure/, "25000"); fill(/Maximum holding period/, "5");
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(api.configure).toHaveBeenCalled());
    expect(api.configure.mock.calls[0][1].risk).toMatchObject({ max_overnight_positions: 5,
      max_overnight_exposure_minor: 2500000, max_hold_sessions: 5 });
  });
  it("shows approved holds and positions waiting for the next open", async () => {
    api.status.mockResolvedValue({ ...running, carry: { approved: { AAPL: {} }, pending: { NVDA: {} } } });
    api.history.mockResolvedValue({ events: [] }); api.report.mockResolvedValue(report);
    render(<PaperAutomationPanel scope={scope} />); open();
    expect(await screen.findByText("Approved to hold: AAPL.")).toBeInTheDocument();
    expect(screen.getByText("Awaiting closure after an unplanned carry: NVDA.")).toBeInTheDocument();
  });

});
