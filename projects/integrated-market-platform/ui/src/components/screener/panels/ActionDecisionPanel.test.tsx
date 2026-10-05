import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ActionDecisionPanel from "./ActionDecisionPanel";

const api = vi.hoisted(() => ({ preview: vi.fn(), run: vi.fn(), history: vi.fn(), handoff: vi.fn() }));
vi.mock("../../../api/screenerAction", () => ({ previewAction: api.preview, runAction: api.run, actionHistory: api.history, prepareAction: api.handoff }));
const preview = { paper_authority: false, candidate_current: true, position: { state: "FLAT", quantity: 0 },
  opportunity_id: null, decision_cutoff: "2026-10-05T14:00:00Z", candidate_valid_until: "2099-01-01T00:00:00Z", provider_id: "fixture", model_id: "controlled" };
const decision = { action_state: "ENTER", direction: "LONG", decision_id: "a", decision_time: preview.decision_cutoff,
  valid_until: preview.candidate_valid_until, rationale: "Observed direction supports entry.", position: preview.position,
  execution_readiness: "BLOCKED", blocker_codes: ["NO_GOVERNED_OPPORTUNITY"], model: { provider_id: "fixture", model_id: "controlled", prompt_id: "screener.action_decision.v1" },
  reference_quote: { source_value: 150, as_of: preview.decision_cutoff }, entry_plan: [{ condition_id: "CURRENT_QUOTE", status: "MET", source: "SERVER_ACTION_POLICY" }],
  hold_plan: [], exit_plan: [], supporting_refs: ["q"], conflicting_refs: ["news-conflict"], weak_refs: [], missing_capabilities: [],
  evidence_snapshot: { cutoff: preview.decision_cutoff, evidence: { current_market_evidence: [{ evidence_id: "q", facts: { price: 150 } }], reference_evidence: [] } } };
afterEach(() => vi.resetAllMocks());
describe("Action decisions", () => {
  it.each(["NO_ACTION", "CONSIDER_ENTRY", "ENTER", "HOLD", "EXIT", "REVALIDATION_REQUIRED"])("renders %s only after explicit evaluation", async (state) => {
    api.preview.mockResolvedValue(preview); api.run.mockResolvedValue({ ...decision, action_state: state }); api.history.mockResolvedValue({ decisions: [decision] });
    render(<MemoryRouter><ActionDecisionPanel runId="r" instrumentId="NVDA" /></MemoryRouter>);
    expect(api.run).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Open decision assessment" }));
    await screen.findByText(/Current position: FLAT/); expect(api.run).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Evaluate Decision" }));
    await screen.findByRole("heading", { name: state.replaceAll("_", " ") });
    expect(api.run).toHaveBeenCalledTimes(1); expect(api.handoff).not.toHaveBeenCalled();
    expect(screen.getByText(/news-conflict/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Read decision history" }));
    await waitFor(() => expect(api.history).toHaveBeenCalledTimes(1));
  });
  it("isolates late responses after candidate change", async () => {
    let resolve: (v: unknown) => void = () => {};
    api.preview.mockImplementation(() => new Promise(r => { resolve = r; }));
    const view = render(<MemoryRouter><ActionDecisionPanel runId="r" instrumentId="A" /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Open decision assessment" }));
    view.rerender(<MemoryRouter><ActionDecisionPanel runId="r" instrumentId="B" /></MemoryRouter>);
    resolve(preview); await waitFor(() => expect(screen.queryByText(/Current position:/)).not.toBeInTheDocument());
  });
  it("prepares an explicit handoff under StrictMode without submitting", async () => {
    api.preview.mockResolvedValue({ ...preview, paper_authority: true });
    api.run.mockResolvedValue({ ...decision, execution_readiness: "PREVIEW_ALLOWED", blocker_codes: [] });
    api.handoff.mockResolvedValue({ instrumentId: "NVDA" });
    render(<StrictMode><MemoryRouter><Routes><Route path="/" element={<ActionDecisionPanel runId="r" instrumentId="NVDA" />} /><Route path="/workspace/NVDA" element={<p>Workspace draft</p>} /></Routes></MemoryRouter></StrictMode>);
    fireEvent.click(screen.getByRole("button", { name: "Open decision assessment" }));
    fireEvent.click(await screen.findByRole("button", { name: "Evaluate Decision" }));
    fireEvent.click(await screen.findByRole("button", { name: "Prepare Paper Preview" }));
    await screen.findByText("Workspace draft");
    expect(api.handoff).toHaveBeenCalledTimes(1);
  });
});
