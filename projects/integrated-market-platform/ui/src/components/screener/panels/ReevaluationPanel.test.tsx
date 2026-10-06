import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReevaluationPanel from "./ReevaluationPanel";

const api = vi.hoisted(() => ({ configure: vi.fn(), status: vi.fn(), start: vi.fn(), stop: vi.fn(), once: vi.fn(), history: vi.fn() }));
vi.mock("../../../api/screenerReevaluation", () => ({ configureReevaluation: api.configure, reevaluationStatus: api.status, startReevaluation: api.start,
  stopReevaluation: api.stop, runReevaluationOnce: api.once, reevaluationHistory: api.history }));
const scope = { universe: "US_EQUITIES", search: "", sort: "symbol", descending: false, filters: [] } as never;
const engine = { state: "AVAILABLE", reason: null, provider_id: "fixture", model_id: "controlled", runtime: "LOCAL_MODEL", budget: null };
const bare = { worker_state: "NOT_CONFIGURED", worker_label: "Not configured", engine, durability: "INTENTIONAL_EPHEMERAL", paper_execution: "MANUAL_ONLY" };
const configured = { ...bare, worker_state: "STOPPED", worker_label: "Stopped", loop_id: "RL-1", account_id: "paper", scope: { universe: "US_EQUITIES" },
  requested_cadence_seconds: 60, effective_cadence_seconds: 120, cadence: { limiting_constraint: "MODEL_MINIMUM_INTERVAL", degraded: true },
  liveness: { last_scheduled: null, last_started: null, last_completed: null, last_success: null, last_error: null, last_status: null, missed_ticks: 0, cycle_count: 0 }, next_scheduled: null,
  projection: { worst_case_model_calls: 120, cycles: 195, session_minutes: 390 },
  readiness: { readiness: "REEVALUATION_DEGRADED", reason_codes: ["EFFECTIVE_CADENCE_SLOWER_THAN_REQUESTED"], provider_states: [
    { capability: "QUOTE", provider: "FIXTURE", state: "CURRENT", delivery_mode: "REALTIME", cadence_semantics: "CURRENT", freshness_policy: "q", as_of: "2026-10-05T14:00:00Z", age_seconds: 20, next_useful_refresh: null, within_requested_cadence: true },
    { capability: "NEWS", provider: "RSS", state: "CURRENT", delivery_mode: "SNAPSHOT", cadence_semantics: "REFERENCE", freshness_policy: "n", as_of: "2026-10-05T13:29:00Z", age_seconds: 1860, next_useful_refresh: null, within_requested_cadence: false },
    { capability: "RATES", provider: "TREASURY", state: "CURRENT", delivery_mode: "PUBLICATION_BASED", cadence_semantics: "PUBLICATION_BASED", freshness_policy: "p", as_of: "2026-10-02", age_seconds: null, next_useful_refresh: null, within_requested_cadence: false }] } };
const counters = { proposed_transitions: 1, accepted_transitions: 1, duplicate_suppressions: 0, churn_suppressions: 0, model_calls_avoided: 0 };
const cycle = (overrides = {}) => ({ cycle_id: "RC-1", trigger: "SCHEDULED_CADENCE", scheduled_for: "2026-10-05T14:31:00Z", started_at: "2026-10-05T14:31:00Z", start_drift_ms: 12, duration_ms: 840,
  model_call_count: 1, missed_ticks_before: 0, counters, not_observed: null, cycle_status: "MATERIAL_CHANGE", reason_codes: [],
  transitions: [{ instrument_id: "NVDA", classification: "STATE_CHANGED", reason_codes: ["DIRECTION_CHANGED"], prior_state: "CONSIDER_ENTRY", new_state: "ENTER", model_call: true }], ...overrides });
afterEach(() => vi.resetAllMocks());

describe("Reevaluation controls", () => {
  it("does nothing until opened and never starts on its own", async () => {
    api.status.mockResolvedValue(bare); api.history.mockRejectedValue(new Error("REEVALUATION_NOT_CONFIGURED"));
    render(<ReevaluationPanel scope={scope} />);
    expect(api.status).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Open reevaluation controls" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Worker: NOT_CONFIGURED — Not configured");
    expect(api.start).not.toHaveBeenCalled(); expect(api.configure).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
  });
  it("shows requested and effective cadence, evidence clocks and manual execution before start", async () => {
    api.status.mockResolvedValueOnce(bare).mockResolvedValue(configured); api.history.mockResolvedValue({ cycles: [] }); api.configure.mockResolvedValue(configured);
    render(<ReevaluationPanel scope={scope} />);
    fireEvent.click(screen.getByRole("button", { name: "Open reevaluation controls" }));
    fireEvent.click(await screen.findByRole("button", { name: "Configure" }));
    await screen.findByText(/Requested: 60 sec · Effective: 120 sec — slower than requested \(limited by MODEL_MINIMUM_INTERVAL\)/);
    expect(api.configure).toHaveBeenCalledWith(scope, 60);
    expect(screen.getByText(/Provider readiness:/)).toHaveTextContent("Degraded · EFFECTIVE_CADENCE_SLOWER_THAN_REQUESTED");
    expect(screen.getByRole("row", { name: /NEWS RSS REFERENCE · SNAPSHOT CURRENT .* 1860s old No/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /RATES TREASURY PUBLICATION-BASED .* No/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /QUOTE FIXTURE CURRENT · REALTIME CURRENT .* 20s old Yes/ })).toBeInTheDocument();
    expect(screen.getByText(/Paper execution remains manual/)).toBeInTheDocument();
    expect(screen.getByText(/AI engine: fixture · controlled · LOCAL_MODEL · AVAILABLE/)).toBeInTheDocument();
    expect(screen.getByText(/at most 120 calls per 390-minute session/)).toBeInTheDocument();
    expect(api.start).not.toHaveBeenCalled();
  });
  it("starts, stops and runs once explicitly; history names transitions and unobserved gaps in text", async () => {
    const runningStatus = { ...configured, worker_state: "RUNNING", worker_label: "Running", next_scheduled: "2026-10-05T14:33:00Z",
      liveness: { ...configured.liveness, last_scheduled: "2026-10-05T14:32:00Z", last_completed: "2026-10-05T14:32:01Z", last_status: "NO_MATERIAL_CHANGE", missed_ticks: 5, cycle_count: 2 } };
    const gap = cycle({ cycle_id: "RC-gap", cycle_status: "NOT_OBSERVED", transitions: [], model_call_count: 0,
      not_observed: { observed_from: "2026-10-05T14:34:00Z", observed_to: "2026-10-05T14:39:00Z", missed_scheduled_cycles: 5, reason: "PROCESS_DOWNTIME" } });
    const quiet = cycle({ cycle_id: "RC-2", cycle_status: "NO_MATERIAL_CHANGE", transitions: [], model_call_count: 0, counters: { ...counters, model_calls_avoided: 1 } });
    const churn = cycle({ cycle_id: "RC-3", transitions: [{ instrument_id: "NVDA", classification: "CHURN_SUPPRESSED", reason_codes: ["DIRECTION_CHANGED", "MIN_STATE_DWELL"], prior_state: "ENTER", new_state: null, model_call: false }] });
    api.status.mockResolvedValueOnce(configured).mockResolvedValue(runningStatus); api.history.mockResolvedValue({ cycles: [gap, churn, quiet, cycle()] });
    api.start.mockResolvedValue(runningStatus); api.stop.mockResolvedValue(configured); api.once.mockResolvedValue(cycle());
    render(<ReevaluationPanel scope={scope} />);
    fireEvent.click(screen.getByRole("button", { name: "Open reevaluation controls" }));
    fireEvent.click(await screen.findByRole("button", { name: "Run Reevaluation Now" }));
    await waitFor(() => expect(api.once).toHaveBeenCalledTimes(1)); expect(api.start).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => expect(api.stop).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("status")).toHaveTextContent("Worker: RUNNING — Running");
    expect(screen.getByText(/last result NO MATERIAL CHANGE · next 2026-10-05T14:33:00Z · missed cycles 5 · cycles run 2/)).toBeInTheDocument();
    expect(screen.getByText(/NOT OBSERVED/).closest("li")).toHaveTextContent("5 scheduled cycles missed · PROCESS_DOWNTIME · no decisions were reconstructed");
    expect(screen.getByText(/NVDA · STATE CHANGED · CONSIDER_ENTRY → ENTER · model call: yes/)).toBeInTheDocument();
    expect(screen.getByText(/NVDA · CHURN SUPPRESSED · ENTER → no new decision · model call: no · DIRECTION_CHANGED, MIN_STATE_DWELL/)).toBeInTheDocument();
    expect(screen.getByText(/model calls 0 · avoided 1/).closest("li")).toHaveTextContent("Decision unchanged");
    expect(screen.getByLabelText(/Requested cadence/)).toBeDisabled();
  });
  it("reports a rejected request in text", async () => {
    api.status.mockResolvedValue(configured); api.history.mockResolvedValue({ cycles: [] }); api.start.mockRejectedValue(new Error("REEVALUATION_LOOP_ALREADY_OWNED"));
    render(<ReevaluationPanel scope={scope} />);
    fireEvent.click(screen.getByRole("button", { name: "Open reevaluation controls" }));
    fireEvent.click(await screen.findByRole("button", { name: "Start" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("REEVALUATION_LOOP_ALREADY_OWNED");
  });
});
