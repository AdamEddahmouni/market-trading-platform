import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PaperTrailingStopPanel } from "./PaperTrailingStopPanel";
import { SmaStopEvaluationTable } from "./SmaStopEvaluationTable";
import { breachedStatus, evaluationReceipt, stopConfig, stopStatus } from "./stopFixtures";

const api = vi.hoisted(() => ({ status: vi.fn(), config: vi.fn(), configure: vi.fn(), evaluate: vi.fn(), history: vi.fn(), evaluation: vi.fn(), handoff: vi.fn() }));
vi.mock("../../api/paperRiskControl", () => ({ smaStopStatus: api.status, smaStopConfig: api.config, configureSmaStop: api.configure, evaluateSmaStop: api.evaluate,
  smaStopHistory: api.history, smaStopEvaluation: api.evaluation }));
vi.mock("../../api/screenerAction", () => ({ prepareAction: api.handoff }));
afterEach(() => vi.resetAllMocks());

function Draft() {
  const location = useLocation();
  return <p>Workspace draft {JSON.stringify(location.state)}</p>;
}

function renderPanel(paperActionsAvailable = true) {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<PaperTrailingStopPanel instrumentId="NVDA" paperActionsAvailable={paperActionsAvailable} />} />
        <Route path="/workspace/NVDA" element={<Draft />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SMA trailing-stop panel", () => {
  it("reads state on open and never evaluates, configures or submits by itself", async () => {
    api.status.mockResolvedValue(stopStatus()); api.config.mockResolvedValue(stopConfig);
    renderPanel();
    expect(await screen.findByTestId("sma-stop-status")).toHaveTextContent("Status: ACTIVE — Active · LONG stop");
    expect(screen.getByRole("heading", { name: "Risk control — SMA trailing stop" })).toBeInTheDocument();
    expect(screen.getByText(/not a resting broker stop order, and a breach never submits a Paper or Live order/)).toBeInTheDocument();
    expect(screen.getByText("Active stop").nextElementSibling).toHaveTextContent("$185.12 · LONG stop");
    expect(screen.getByText("Current SMA").nextElementSibling).toHaveTextContent("$184.7300");
    expect(screen.getByText("Previous stop").nextElementSibling).toHaveTextContent("$184.90");
    expect(screen.getByText("Distance to stop").nextElementSibling).toHaveTextContent("$2.28 (121.7 bps)");
    expect(screen.getByText("Window").nextElementSibling).toHaveTextContent("20 completed 1m bars · reference test configuration — not optimized");
    expect(screen.getByText("Monitoring").nextElementSibling).toHaveTextContent("RUNNING");
    expect(screen.getByText("Stop held at previous level — trailing rule does not loosen protection.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(api.evaluate).not.toHaveBeenCalled(); expect(api.configure).not.toHaveBeenCalled(); expect(api.handoff).not.toHaveBeenCalled();
  });

  it("fails visibly when stop state cannot be read", async () => {
    api.status.mockRejectedValue(new Error("offline")); api.config.mockRejectedValue(new Error("offline"));
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("Stop state unavailable. Nothing is assumed about the stop.");
    expect(screen.queryByRole("button", { name: "Evaluate Stop Now" })).not.toBeInTheDocument();
  });

  it("evaluates only on explicit request and shows the tightened stop", async () => {
    api.status.mockResolvedValue(stopStatus()); api.config.mockResolvedValue(stopConfig);
    api.evaluate.mockResolvedValue(stopStatus({ reason_codes: [] }, { active_stop: "186.1", previous_stop: "185.12", candidate_stop: "186.1", sma_value: "186.1000" }));
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Evaluate Stop Now" }));
    await waitFor(() => expect(screen.getByText("Active stop").nextElementSibling).toHaveTextContent("$186.10"));
    expect(screen.getByText("Previous stop").nextElementSibling).toHaveTextContent("$185.12");
    expect(api.evaluate).toHaveBeenCalledTimes(1); expect(api.evaluate.mock.calls[0][0]).toBe("NVDA");
    expect(screen.queryByText(/Stop held at previous level/)).not.toBeInTheDocument();
  });

  it("offers only bounded policy parameters and reports a rejected change", async () => {
    api.status.mockResolvedValue(stopStatus({ status: "NOT_CONFIGURED", reason_codes: ["STOP_NOT_CONFIGURED"], policy: null, monitoring: undefined }, null));
    api.config.mockResolvedValue({ ...stopConfig, configured: false, enabled: false, policy: null });
    api.configure.mockRejectedValue(new Error("STOP_POLICY_CHANGE_REJECTED_WHILE_ACTIVE"));
    renderPanel();
    expect(await screen.findByTestId("sma-stop-status")).toHaveTextContent("Status: NOT CONFIGURED — Not configured");
    expect(screen.getByRole("button", { name: "Evaluate Stop Now" })).toBeDisabled();
    const window = screen.getByLabelText(/SMA window \(completed bars\)/);
    expect(screen.queryByLabelText(/stop level|stop price|formula/i)).not.toBeInTheDocument();
    fireEvent.change(window, { target: { value: "500" } });
    expect(screen.getByRole("button", { name: "Enable stop policy" })).toBeDisabled();
    fireEvent.change(window, { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("Bar interval"), { target: { value: "5m" } });
    fireEvent.click(screen.getByRole("button", { name: "Enable stop policy" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Stop policy not changed. A working stop cannot be replaced");
    expect(api.configure.mock.calls[0][0]).toEqual({ enabled: true, sma_window_bars: 30, bar_interval: "5m" });
  });

  it("shows a breach as text with an EXIT decision and hands off through the existing draft only", async () => {
    api.status.mockResolvedValue(breachedStatus()); api.config.mockResolvedValue(stopConfig);
    api.handoff.mockResolvedValue({ version: 1, instrumentId: "NVDA", side: "SELL", quantity: 7, orderType: "MARKET" });
    renderPanel();
    const breach = await screen.findByRole("alert", { name: "SMA stop breached" });
    expect(within(breach).getByRole("heading", { name: "SMA trailing stop breached" })).toBeInTheDocument();
    expect(within(breach).getByText("Stop").nextElementSibling).toHaveTextContent("$186.10 · LONG stop");
    expect(within(breach).getByText("Observed").nextElementSibling).toHaveTextContent("$185.95 · last trade");
    expect(within(breach).getByText("Observed at").nextElementSibling).toHaveTextContent("2026-10-05 10:45:00 ET");
    expect(within(breach).getByText("Decision").nextElementSibling).toHaveTextContent("EXIT · AD-exit");
    expect(within(breach).getByText("Paper close").nextElementSibling).toHaveTextContent("NOT SUBMITTED");
    expect(within(breach).getByText(/no model chose or can change this level/)).toBeInTheDocument();
    expect(api.handoff).not.toHaveBeenCalled();
    fireEvent.click(within(breach).getByRole("button", { name: "Prepare Paper Exit" }));
    expect(await screen.findByText(/Workspace draft .*"side":"SELL".*"quantity":7/)).toBeInTheDocument();
    expect(api.handoff).toHaveBeenCalledWith("AD-exit");
  });

  it("does not offer an exit draft without Paper authority, a recorded decision or an allowed preview", async () => {
    api.config.mockResolvedValue(stopConfig);
    api.status.mockResolvedValue(breachedStatus());
    const first = renderPanel(false);
    expect(await screen.findByRole("button", { name: "Prepare Paper Exit" })).toBeDisabled();
    first.unmount();
    api.status.mockResolvedValue(breachedStatus({ decision_id: "AD-exit", action_state: "EXIT", execution_readiness: "BLOCKED", blocker_codes: ["PENDING_ORDER_REVALIDATION"], decision_time: "t" }));
    const second = renderPanel();
    expect(await screen.findByText("Paper preview blocked: PENDING_ORDER_REVALIDATION")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prepare Paper Exit" })).toBeDisabled();
    second.unmount();
    api.status.mockResolvedValue(breachedStatus(null));
    renderPanel();
    expect(await screen.findByText("EXIT decision not yet recorded")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Prepare Paper Exit" })).not.toBeInTheDocument();
  });

  it("reads bounded stop history and the replay comparison only when asked", async () => {
    api.status.mockResolvedValue(stopStatus()); api.config.mockResolvedValue(stopConfig); api.evaluation.mockResolvedValue(evaluationReceipt);
    api.history.mockResolvedValue({ events: [{ sequence: 9, kind: "CLAMPED", at: "2026-10-05T14:42:00Z", status: "ACTIVE", side: "LONG", sma_value: "184.7300", candidate_stop: "184.73",
      active_stop: "185.12", previous_stop: "184.9", reason_codes: ["MONOTONIC_CLAMP"], policy_id: "STP-reference" }], total: 41, next_before: null });
    renderPanel();
    await screen.findByTestId("sma-stop-status");
    expect(api.history).not.toHaveBeenCalled(); expect(api.evaluation).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Read stop history" }));
    const history = await screen.findByRole("table", { name: "Latest 1 of 41 stop events, newest first" });
    expect(within(history).getByRole("rowheader", { name: "CLAMPED · LONG" })).toBeInTheDocument();
    expect(api.history).toHaveBeenCalledWith("NVDA", 20, expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Read replay comparison" }));
    expect(await screen.findByRole("heading", { name: "Method comparison" })).toBeInTheDocument();
  });
});

describe("Replay method comparison", () => {
  it("compares all four methods with downside and return side by side and claims nothing", () => {
    render(<SmaStopEvaluationTable evaluation={evaluationReceipt} />);
    const long = screen.getByRole("table", { name: /LONG episodes \(primary comparison\)\. Historical replay; not live and not Paper\./ });
    for (const method of ["SMA trail", "Raw-price trail", "Fixed initial stop", "Existing / no-trail exit"]) {
      expect(within(long).getByRole("rowheader", { name: method })).toBeInTheDocument();
    }
    for (const column of ["Mean adverse excursion", "Mean max drawdown", "Loss severity", "Mean gross return", "Mean net return", "Exited before a better horizon price"]) {
      expect(within(long).getByRole("columnheader", { name: column })).toBeInTheDocument();
    }
    const sma = within(long).getByRole("rowheader", { name: "SMA trail" }).closest("tr")!;
    expect(sma).toHaveTextContent("7.34 bps"); expect(sma).toHaveTextContent("-1.53 bps"); expect(sma).toHaveTextContent("48.4%");
    expect(within(long).getByRole("rowheader", { name: "Existing / no-trail exit" }).closest("tr")).toHaveTextContent("16.17 bps");
    expect(screen.getByRole("table", { name: /SHORT episodes \(policy math only — Paper short authority is unchanged\)/ })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Conclusion: Insufficient evidence. Evidence is insufficient for a directional or superiority claim. Superiority claim: none.");
    expect(screen.getByText(/In-sample pattern \(description only, not a claim\): No clear difference\./)).toBeInTheDocument();
    expect(screen.getByText(/120 episodes, 59 evaluable, 61 excluded \(INITIAL_STOP_NOT_PROTECTIVE: 61\)/)).toBeInTheDocument();
    expect(screen.getByText(/Evidence class: HISTORICAL REPLAY · Status: REPLAY EVALUATED · Calibration: NOT CALIBRATED/)).toBeInTheDocument();
    expect(screen.getByText(/never at the stop level/)).toBeInTheDocument();
    expect(screen.getByText("def-hash")).toBeInTheDocument(); expect(screen.getByText("result-hash")).toBeInTheDocument();
    expect(screen.getByText("Corpus unchanged by the run").nextElementSibling).toHaveTextContent("Yes");
    expect(document.body.textContent).not.toMatch(/\b(best|superior|outperform|optimal|profitable)\b/i);
  });

  it("says insufficient evidence when no comparison was executed", () => {
    render(<SmaStopEvaluationTable evaluation={{ schema_version: "sma-stop-evaluation/1.0.0", result_status: "NOT_EXECUTED", reason_codes: ["EVALUATION_RECEIPT_NOT_FOUND"] }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Insufficient evidence — the replay comparison has not been executed (EVALUATION_RECEIPT_NOT_FOUND).");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
