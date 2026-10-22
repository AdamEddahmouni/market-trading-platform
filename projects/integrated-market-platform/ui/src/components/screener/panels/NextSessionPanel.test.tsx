import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import NextSessionPanel from "./NextSessionPanel";

const api = vi.hoisted(() => ({ draft: vi.fn(), lock: vi.fn(), observe: vi.fn(), evaluate: vi.fn() }));
vi.mock("../../../api/screenerReevaluation", () => ({ draftNextSession: api.draft, lockNextSession: api.lock, observeNextSession: api.observe, evaluateNextSession: api.evaluate }));
const snapshot = { snapshot_id: "NS-1", lock_state: "DRAFT", state: "DRAFT", target_session_date: "2026-10-06", target_session_kind: "US_EQUITY_RTH", target_timezone: "America/New_York",
  target_session_start: "2026-10-06T13:30:00Z", target_session_end: "2026-10-06T20:00:00Z", early_close_metadata: "UNAVAILABLE", decision_cutoff: "2026-10-05T19:55:12Z",
  action_state: "CONSIDER_ENTRY", direction: null, position_state: "FLAT", reference_price: 150, reference_price_as_of: "2026-10-05T19:55:10Z",
  evaluation_policy: { policy_id: "next-session-open-30m/1.0.0", observation_start: "2026-10-06T13:30:00Z", observation_end: "2026-10-06T14:00:00Z", reference_price_basis: "DECISION_REFERENCE_QUOTE" },
  provider_id: "fixture", model_id: "controlled", prompt_id: "screener.action_decision.v1", evidence_snapshot_ref: "AS-1", action_decision_id: "AD-1", validity_state: "SOURCE_DECISION_CURRENT", locked_at: null };
const view = (overrides = {}, comparison: unknown = null) => ({ snapshot: { ...snapshot, ...overrides }, observations: [], observation_count: comparison ? 1 : 0, durability: "INTENTIONAL_EPHEMERAL", integrity: "VERIFIED", comparison });
afterEach(() => vi.resetAllMocks());

describe("Next-session snapshot", () => {
  it("freezes only on explicit request, then locks immutably", async () => {
    api.draft.mockResolvedValue(view()); api.lock.mockResolvedValue(view({ lock_state: "LOCKED", state: "LOCKED", locked_at: "2026-10-05T19:56:00Z" }));
    render(<NextSessionPanel decisionId="AD-1" actionState="CONSIDER_ENTRY" />);
    expect(api.draft).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Freeze for Next Session" }));
    await screen.findByText(/DRAFT — not yet frozen/);
    expect(screen.getByText(/Target: 2026-10-06 · US_EQUITY_RTH/)).toBeInTheDocument();
    expect(screen.getByText(/Decision cutoff: 2026-10-05T19:55:12Z · Action: CONSIDER_ENTRY · Direction: Unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/Evaluation: next-session-open-30m\/1.0.0/)).toBeInTheDocument();
    expect(screen.getByText(/Model: fixture · controlled/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Lock" }));
    await screen.findByText(/LOCKED — immutable\. This snapshot cannot be changed\./);
    expect(screen.queryByRole("button", { name: "Lock" })).not.toBeInTheDocument();
    expect(screen.getByText("No later observation recorded yet.")).toBeInTheDocument();
  });
  it("shows a later observation as an observation, with execution not applicable", async () => {
    const comparison = { frozen_action_state: "CONSIDER_ENTRY", frozen_direction: null, decision_reference_price: 150, first_observed_price: 151.5, last_observed_price: 153,
      last_observed_at: "2026-10-06T13:55:00Z", change_pct: 2, subsequent_action_state: "ENTER", position_state_now: "FLAT", signal_outcome: { quality: "COMPLETE" }, execution_outcome: { quality: "NOT_APPLICABLE" } };
    api.draft.mockResolvedValue(view({ lock_state: "LOCKED", state: "OBSERVING", locked_at: "2026-10-05T19:56:00Z" }));
    api.observe.mockResolvedValue(view({ lock_state: "LOCKED", state: "OBSERVING", locked_at: "2026-10-05T19:56:00Z" }, comparison));
    render(<NextSessionPanel decisionId="AD-1" actionState="CONSIDER_ENTRY" />);
    fireEvent.click(screen.getByRole("button", { name: "Freeze for Next Session" }));
    fireEvent.click(await screen.findByRole("button", { name: "Record observation" }));
    await screen.findByText(/change since decision 2%/);
    expect(screen.getByText(/Current decision: ENTER · Current position: FLAT/)).toBeInTheDocument();
    expect(screen.getByText(/Signal comparison: COMPLETE · Paper execution outcome: NOT_APPLICABLE/)).toBeInTheDocument();
    expect(screen.getByText(/Evaluation status: OBSERVING · 1 observation recorded/)).toBeInTheDocument();
    expect(screen.getByText(/not profit and loss/)).toBeInTheDocument();
  });
  it("surfaces a server rejection and refuses unavailable evaluations", async () => {
    api.draft.mockRejectedValue(new Error("NEXT_SESSION_CALENDAR_UNAVAILABLE"));
    const { rerender } = render(<NextSessionPanel decisionId="AD-1" actionState="ENTER" />);
    fireEvent.click(screen.getByRole("button", { name: "Freeze for Next Session" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("NEXT_SESSION_CALENDAR_UNAVAILABLE");
    rerender(<NextSessionPanel decisionId="AD-2" actionState="REVALIDATION_REQUIRED" />);
    expect(screen.queryByRole("button", { name: "Freeze for Next Session" })).not.toBeInTheDocument();
    expect(screen.getByText(/requires revalidation/)).toBeInTheDocument();
  });
});
