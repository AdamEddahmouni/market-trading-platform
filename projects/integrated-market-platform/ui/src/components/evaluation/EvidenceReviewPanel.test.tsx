import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JournalView, KnowledgeView, PlanView, ReplayView, StatusView } from "./EvidenceReviewPanel";
import fixture from "./evidenceReviewFixture.json";
import { EvidenceJournalSchema, EvidenceKnowledgeSchema, EvidencePlanSchema, EvidenceReplaySchema,
  EvidenceStatusSchema } from "../../api/evidenceReview";

// The fixture is the backend's own output; tests/trading_correctness/test_evidence_review_api.py holds it to the service.
describe("Evidence review", () => {
  it("shows the AI window beside collection, which the pause does not switch off", () => {
    render(<StatusView status={EvidenceStatusSchema.parse(fixture.status)} />);
    expect(screen.getByText("CATCH_UP", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText(/Collection has its own switches and is not paused by the AI schedule/)).toBeInTheDocument();
    expect(screen.getByText(/availability not probed/)).toBeInTheDocument();
    const schedule = screen.getByRole("table", { name: "AI analysis schedule" });
    expect(within(schedule).getByText("Paused")).toBeInTheDocument();
    expect(within(schedule).getAllByText("Eligible")).toHaveLength(4);
  });
  it("lists stored news by when it was known and marks a corrected version", () => {
    render(<KnowledgeView knowledge={EvidenceKnowledgeSchema.parse(fixture.knowledge)} />);
    const table = screen.getByRole("table", { name: "Stored news" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(within(table).getByText("Corrected version of an earlier stored record")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "AAPL reports earnings" })).toHaveAttribute("href", "https://example.test/wire-1");
    expect(within(table).getAllByText("SOFTWARE_FIXTURE_ONLY")).toHaveLength(3);
  });
  it("says when stored news is unavailable instead of showing an empty table", () => {
    const store = { state: "UNAVAILABLE" as const, reason: "DURABLE_STATE_DISABLED", records: null, latest_ingested_time: null };
    render(<KnowledgeView knowledge={{ ...EvidenceKnowledgeSchema.parse(fixture.knowledge), store, records: [], count: 0 }} />);
    expect(screen.getByRole("status")).toHaveTextContent("DURABLE_STATE_DISABLED");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
  it("presents the catch-up as a plan with its bound, deferral reason and unverified model access", () => {
    render(<PlanView plan={EvidencePlanSchema.parse(fixture.plan)} />);
    expect(screen.getByText(/Plan only. No model is called and no budget is reserved/)).toHaveTextContent("has not been verified");
    expect(screen.getByText("2 / 1")).toBeInTheDocument();
    expect(screen.getByText(/REQUEST_BOUND ×1/)).toBeInTheDocument();
    expect(within(screen.getByRole("table", { name: "Planned requests" })).getAllByRole("row")).toHaveLength(3);
    expect(within(screen.getByRole("table", { name: "Deferred" })).getByText("REQUEST_BOUND")).toBeInTheDocument();
  });
  it("keeps proposal, operator action, Paper execution and later observations in separate columns", () => {
    const inspect = vi.fn();
    render(<JournalView journal={EvidenceJournalSchema.parse(fixture.journal)} onInspect={inspect} />);
    const row = within(screen.getByRole("table", { name: "Decision journal" })).getAllByRole("row")[1];
    expect(within(row).getByText("ENTER")).toBeInTheDocument();
    expect(within(row).getByText("None recorded")).toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: /Inspect/ }));
    expect(inspect).toHaveBeenCalledWith(fixture.journal.items[0].decision_id);
    expect(screen.getByText(/Realised profit and loss is not computed here/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Submit|Order|Arm|Activate/ })).not.toBeInTheDocument();
  });
  it("lists decisions the journal refused instead of hiding them", () => {
    const journal = EvidenceJournalSchema.parse(fixture.journal);
    render(<JournalView journal={{ ...journal, items: [], unjournaled: [{ decision_id: "AD-1", instrument_id: "AAPL", decision_time: "2026-10-14T14:00:00Z", reason: "JOURNAL_SNAPSHOT_IDENTITY_MISMATCH" }] }} onInspect={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("No decision was recorded");
    expect(screen.getByText(/JOURNAL_SNAPSHOT_IDENTITY_MISMATCH/)).toBeInTheDocument();
  });
  it("shows three policies on one snapshot and refuses to call it a ranking", () => {
    const replay = EvidenceReplaySchema.parse(fixture.replay);
    render(<ReplayView replay={replay} />);
    expect(screen.getByText(/It is not a performance ranking/)).toHaveTextContent("SOFTWARE_FIXTURE_ONLY");
    const table = screen.getByRole("table", { name: "Replay policy comparison" });
    expect(within(table).getAllByRole("columnheader")).toHaveLength(3 + 3);
    expect(within(table).getAllByRole("row")).toHaveLength(replay.decisions.length + 1);
    expect(screen.getByText("Yes, two runs identical")).toBeInTheDocument();
  });
});
