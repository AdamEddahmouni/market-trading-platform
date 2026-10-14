import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import EvidenceReviewPanel, { IntelligenceView, JournalView, KnowledgeView, PlanView, ReplayView, StatusView } from "./EvidenceReviewPanel";
import fixture from "./evidenceReviewFixture.json";
import { evidenceApi, EvidenceIntelligenceSchema, EvidenceJournalSchema, EvidenceKnowledgeSchema, EvidencePlanSchema, EvidenceReplaySchema,
  EvidenceStatusSchema } from "../../api/evidenceReview";

// The fixture is the backend's own output; tests/trading_correctness/test_evidence_review_api.py holds it to the service.
const status = EvidenceStatusSchema.parse(fixture.status);
const knowledge = EvidenceKnowledgeSchema.parse(fixture.knowledge);
const plan = EvidencePlanSchema.parse(fixture.plan);
const journal = EvidenceJournalSchema.parse(fixture.journal);
const replay = EvidenceReplaySchema.parse(fixture.replay);

describe("Evidence review", () => {
  it("shows local analysis as derived language evidence with its model, window and availability clock", () => {
    const authority = status.authority;
    const view = EvidenceIntelligenceSchema.parse({ schema_version: "evidence-review-intelligence/1", as_of: "2026-10-14T14:01:00Z",
      state: "PROCESSED", status: { at: "2026-10-14T14:00:00Z", backlog: 0, processed: 2, scored: 1, session: { window: "REGULAR" } },
      heartbeat_age_seconds: 60, evidence_class: "DERIVED_LOCAL_EVIDENCE_NOT_A_SIGNAL", label_counts: { NEGATIVE: 1, NOT_APPLICABLE: 1 },
      outputs: [
        { revision_id: "b", provider_id: "finnhub", source_id: "finnhub-src", headline: "Apple shares fall after downgrade",
          instrument_ids: ["AAPL"], published_time: "2026-10-14T13:00:00Z", input_available_time: "2026-10-14T13:01:00Z",
          processed_at: "2026-10-14T14:00:00Z", window: "REGULAR", event_categories: ["company.analyst"], status: "PROCESSED",
          sentiment: { state: "SCORED", label: "NEGATIVE", probabilities: { positive: 0.05, neutral: 0.1, negative: 0.85 } },
          sentiment_model: { model_id: "ProsusAI/finbert", model_revision: "abc" } },
        { revision_id: "c", provider_id: "sec_filings", source_id: "sec", headline: "Apple Inc. filed 8-K", instrument_ids: ["AAPL"],
          published_time: null, input_available_time: "2026-10-14T13:02:00Z", processed_at: "2026-10-14T14:00:00Z", window: "REGULAR",
          event_categories: [], status: "PROCESSED", sentiment: { state: "NOT_APPLICABLE" }, sentiment_model: null }],
      authority });
    render(<IntelligenceView view={view} />);
    expect(screen.getByText(/not a forecast or a trading signal/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Local analysis outputs" });
    expect(within(table).getByText("NEGATIVE (85%)")).toBeInTheDocument();
    expect(within(table).getByText("Not applicable (official filing)")).toBeInTheDocument();
    expect(screen.getByText("REGULAR", { selector: "dd" })).toBeInTheDocument();
  });
  it("shows the AI window beside collection, which the pause does not switch off", () => {
    render(<StatusView status={status} />);
    expect(screen.getByText("CATCH_UP", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText(/Collection has its own switches and is not paused by the AI schedule/)).toBeInTheDocument();
    expect(screen.getByText(/availability not probed/)).toBeInTheDocument();
    const schedule = screen.getByRole("table", { name: "AI analysis schedule" });
    expect(within(schedule).getByText("Paused")).toBeInTheDocument();
    expect(within(schedule).getAllByText("Eligible")).toHaveLength(4);
  });
  it("lists stored news by when it was known and marks a corrected version", () => {
    render(<KnowledgeView knowledge={knowledge} />);
    const table = screen.getByRole("table", { name: "Stored news" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(within(table).getByText("Corrected version of an earlier stored record")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "AAPL reports earnings" })).toHaveAttribute("href", "https://example.test/wire-1");
    expect(within(table).getAllByText("SOFTWARE_FIXTURE_ONLY")).toHaveLength(3);
  });
  it("links only plain web addresses and says when a record carries no saved provenance", () => {
    const row = { ...knowledge.records[0], url: "javascript:alert(1)", evidence_class: null, source_reference: null };
    render(<KnowledgeView knowledge={{ ...knowledge, records: [row], count: 1 }} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("None saved with this record")).toBeInTheDocument();
  });
  it("says when stored news is unavailable instead of showing an empty table", () => {
    const store = { state: "UNAVAILABLE" as const, reason: "DURABLE_STATE_DISABLED", records: null, latest_ingested_time: null };
    render(<KnowledgeView knowledge={{ ...knowledge, store, records: [], count: 0 }} />);
    expect(screen.getByRole("status")).toHaveTextContent("DURABLE_STATE_DISABLED");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
  it("presents the catch-up as a plan and labels assumed model access as an assumption", () => {
    render(<PlanView plan={plan} />);
    const warning = screen.getByText(/Plan only. No model is called and no budget is reserved/);
    expect(warning).toHaveTextContent("This preview assumes model access; that is your assumption and nothing has checked it.");
    expect(warning).toHaveTextContent("no spending approval is implied");
    expect(screen.getByText(/assumed for this preview, not verified/)).toBeInTheDocument();
    expect(screen.queryByText(/SUPPORTED/)).not.toBeInTheDocument();
    expect(screen.getByText("2 / 1 / 0")).toBeInTheDocument();
    expect(screen.getByText(/REQUEST_BOUND ×1/)).toBeInTheDocument();
    expect(within(screen.getByRole("table", { name: "Planned requests" })).getAllByRole("row")).toHaveLength(3);
    expect(within(screen.getByRole("table", { name: "Deferred" })).getByText("REQUEST_BOUND")).toBeInTheDocument();
  });
  it("without the assumption says nothing can be planned, and reports an unavailable store and unexamined backlog", () => {
    const store = { state: "UNAVAILABLE" as const, reason: "NEWS_KNOWLEDGE_SCAN_BOUND", records: null, latest_ingested_time: null };
    render(<PlanView plan={{ ...plan, availability_basis: "NOT_VERIFIED", store, planned: [], planned_requests: 0, unscanned_count: 7,
      unscanned_reason: "BACKLOG_BOUND", model_route: { ...plan.model_route, state: "NOT_VERIFIED" } }} />);
    expect(screen.getByText(/Model access is unconfirmed, so no request can be planned/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("NEWS_KNOWLEDGE_SCAN_BOUND");
    expect(screen.getByText("0 / 1 / 7 (BACKLOG_BOUND)")).toBeInTheDocument();
  });
  it("keeps the model proposal, the checked decision, the Paper position and later observations in separate columns", () => {
    const inspect = vi.fn();
    render(<JournalView journal={journal} onInspect={inspect} />);
    const table = screen.getByRole("table", { name: "Decision journal" });
    expect(within(table).getAllByRole("columnheader").map(cell => cell.textContent)).toEqual([
      "Time / instrument", "Model proposal", "Decision after IMP's checks", "Paper position opened by this decision",
      "Later market observations", "Evidence"]);
    const cells = within(within(table).getAllByRole("row")[1]).getAllByRole("cell");
    expect(cells[1]).toHaveTextContent("ENTER");
    expect(cells[2]).toHaveTextContent("ENTER");
    expect(cells[3]).toHaveTextContent("OPEN");
    fireEvent.click(within(cells[5]).getByRole("button", { name: /Inspect/ }));
    expect(inspect).toHaveBeenCalledWith(fixture.journal.items[0].decision_id);
    expect(screen.getByText(/Profit and loss is not computed here/)).toHaveTextContent("simulated");
    expect(screen.queryByRole("button", { name: /Submit|Order|Arm|Activate/ })).not.toBeInTheDocument();
  });
  it("lists decisions the journal refused instead of hiding them", () => {
    render(<JournalView journal={{ ...journal, items: [], unjournaled: [{ decision_id: "AD-1", instrument_id: "AAPL", decision_time: "2026-10-14T14:00:00Z", reason: "JOURNAL_SNAPSHOT_IDENTITY_MISMATCH" }] }} onInspect={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("No decision was recorded");
    expect(screen.getByText(/JOURNAL_SNAPSHOT_IDENTITY_MISMATCH/)).toBeInTheDocument();
  });
  it("shows three policies on one snapshot, refuses to call it a ranking and says AI output was not admitted", () => {
    render(<ReplayView replay={replay} />);
    const warning = screen.getByText(/It is not a performance ranking/);
    expect(warning).toHaveTextContent("SOFTWARE_FIXTURE_ONLY");
    expect(warning).toHaveTextContent("No stored AI output is admitted in this view");
    const table = screen.getByRole("table", { name: "Replay policy comparison" });
    expect(within(table).getAllByRole("columnheader")).toHaveLength(3 + 3);
    expect(within(table).getAllByRole("row")).toHaveLength(replay.decisions.length + 1);
    expect(screen.getByText("Identical")).toBeInTheDocument();
  });
});

describe("Evidence review panel", () => {
  afterEach(() => vi.restoreAllMocks());
  const mount = () => render(<QueryClientProvider client={new QueryClient()}><EvidenceReviewPanel account="paper-1" /></QueryClientProvider>);

  it("reads only the open view, applies filters on Show and sends the assumption only when ticked", async () => {
    vi.spyOn(evidenceApi, "status").mockResolvedValue(status);
    const news = vi.spyOn(evidenceApi, "knowledge").mockResolvedValue(knowledge);
    const planned = vi.spyOn(evidenceApi, "plan").mockResolvedValue(plan);
    const entries = vi.spyOn(evidenceApi, "journal").mockResolvedValue(journal);
    mount();
    expect(await screen.findByRole("table", { name: "Stored news" })).toBeInTheDocument();
    expect(news).toHaveBeenCalledWith({ as_of: "", symbol: "" });
    expect(planned).not.toHaveBeenCalled();
    expect(entries).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Morning catch-up plan" }));
    expect(await screen.findByRole("table", { name: "Planned requests" })).toBeInTheDocument();
    expect(planned).toHaveBeenLastCalledWith({ at: "", max_requests: "", request_allowance: "", assume_available: false });
    fireEvent.change(screen.getByLabelText(/Preview clock/), { target: { value: "2026-10-14T07:30:00Z" } });
    fireEvent.click(screen.getByLabelText(/Preview as if model access were confirmed/));
    expect(planned).toHaveBeenCalledTimes(1);  // typing sends nothing
    fireEvent.click(screen.getByRole("button", { name: "Show" }));
    await vi.waitFor(() => expect(planned).toHaveBeenLastCalledWith(
      { at: "2026-10-14T07:30:00Z", max_requests: "", request_allowance: "", assume_available: true }));
    fireEvent.click(screen.getByRole("button", { name: "Show" }));  // the same inputs again is a fresh read
    await vi.waitFor(() => expect(planned).toHaveBeenCalledTimes(3));
  });
  it("shows a refusal once, without retrying, and reads an inspected entry at the listed day and cutoff", async () => {
    vi.spyOn(evidenceApi, "status").mockResolvedValue(status);
    const news = vi.spyOn(evidenceApi, "knowledge").mockRejectedValue(new Error("INVALID_EVIDENCE_CUTOFF"));
    vi.spyOn(evidenceApi, "journal").mockResolvedValue(journal);
    const entry = vi.spyOn(evidenceApi, "journalEntry").mockResolvedValue({ schema_version: "evidence-review-journal-entry/1",
      day: journal.day, observation_as_of: journal.observation_as_of, entry: { decision_id: "x" }, later_evidence: journal.items[0].later_evidence,
      authority: journal.authority });
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("INVALID_EVIDENCE_CUTOFF");
    expect(news).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Decision journal" }));
    fireEvent.click(await screen.findByRole("button", { name: /Inspect/ }));
    expect(await screen.findByText(/What happened afterwards/)).toHaveTextContent("simulated");
    expect(entry).toHaveBeenCalledWith({ day: journal.day, as_of: journal.observation_as_of, decision_id: journal.items[0].decision_id });
  });
});
