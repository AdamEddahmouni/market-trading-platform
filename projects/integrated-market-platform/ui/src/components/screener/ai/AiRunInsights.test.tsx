import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, renderHook, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AiScreenerHistoryRun, AiScreenerReason, AiScreenerRun } from "../../../api/screenerAi";
import { AiReasonChips, AiRunHistory, reasonText } from "./AiRunInsights";
import { AiRowBadge, useAiRowMarks } from "./aiRowMarks";

const api = vi.hoisted(() => ({ history: vi.fn() }));
vi.mock("../../../api/screenerAi", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerAi")>(), fetchAiScreenerHistory: api.history }));

const scope = { universe: "US_EQUITIES" as const, search: "", sort: "volume", descending: true, filters: [] };
const reason = (overrides: Partial<AiScreenerReason>): AiScreenerReason => ({ kind: "BLOCKED", capability: "TECHNICALS", reason: "NO_OBSERVATION_TIME", count: 20, of: 20, symbols: ["AAA", "BBB", "CCC"], ...overrides });
const stored = (overrides: Partial<AiScreenerHistoryRun>): AiScreenerHistoryRun => ({ candidate_run_id: "run-1", generated_at: "2026-10-07T13:58:12Z", state: "NO_GROUNDED_CANDIDATES", reason: null,
  provider_id: "anthropic.messages", model_id: "claude-haiku-4-5", runtime: "PAID_API", cache: "MISS", tokens_input: 43_000, tokens_output: 638, latency_ms: 10_800,
  selected: [], selected_count: 0, intake_count: 20, scope, previous_run_id: null, added: null, removed: null, ...overrides });
const wrap = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

afterEach(() => { vi.resetAllMocks(); vi.useRealTimers(); });

describe("reason chips", () => {
  it("say what was blocked or missing, for how many, and name the exceptions", () => {
    expect(reasonText(reason({}))).toBe("Technicals blocked: no observation time · all 20");
    expect(reasonText(reason({ capability: "QUOTE", reason: "AGE_EXCEEDS_POLICY", count: 1, symbols: ["LABT"] }))).toBe("Quote blocked: too old · LABT");
    expect(reasonText(reason({ kind: "NO_NEWS", capability: "NEWS", reason: null, count: 18 }))).toBe("No news story · 18 of 20");
    expect(reasonText(reason({ kind: "INSUFFICIENT", capability: null, reason: null, count: 2, symbols: ["AAA", "LABT"] }))).toBe("Not enough current evidence · AAA, LABT");
    // A code with no plain wording is shown as words, never dropped.
    expect(reasonText(reason({ capability: "ORDER_FLOW", reason: "SOME_NEW_CODE", count: 5 }))).toBe("Order flow blocked: some new code · 5 of 20");
  });

  it("keep the code in the title and the model's prose behind a disclosure", () => {
    render(<AiReasonChips reasons={[reason({}), reason({ kind: "NO_NEWS", capability: "NEWS", reason: null })]} limitations={["Only price and volume were available."]} />);
    const chips = within(screen.getByRole("list", { name: "What limited this pass" })).getAllByRole("listitem");
    expect(chips.map((chip) => chip.textContent)).toEqual(["Technicals blocked: no observation time · all 20", "No news story · all 20"]);
    expect(chips[0]).toHaveAttribute("title", "TECHNICALS · NO_OBSERVATION_TIME · 20 of 20 · AAA, BBB, CCC");
    const prose = screen.getByText("The model's own explanation").closest("details")!;
    expect(prose).not.toHaveAttribute("open");
    expect(prose).toHaveTextContent("Only price and volume were available.");
  });

  it("render nothing when there is nothing to say", () => {
    const { container } = render(<AiReasonChips reasons={[]} limitations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("run history", () => {
  const open = () => fireEvent(screen.getByText("Run history").closest("details")!, Object.assign(new Event("toggle"), {}));
  const openDetails = () => { const details = screen.getByText("Run history").closest("details")!; details.open = true; open(); };

  it("reads nothing until it is opened", () => {
    wrap(<AiRunHistory scope={scope} />);
    expect(api.history).not.toHaveBeenCalled();
  });

  it("lists stored passes with engine, result, tokens, model time and the change against the previous pass", async () => {
    api.history.mockResolvedValue({ schema_version: "screener-ai-screener-history/1.0.0", limit: 20, runs: [
      stored({ candidate_run_id: "run-3", previous_run_id: "run-2", added: [], removed: ["EQ:BBB"] }),
      stored({ candidate_run_id: "run-2", generated_at: "2026-10-07T13:50:00Z", state: "CURRENT", selected: [{ instrument_id: "EQ:BBB", rank: 1 }], selected_count: 1,
        previous_run_id: "run-1", added: ["EQ:BBB"], removed: ["EQ:AAA"], cache: "HIT" }),
      stored({ candidate_run_id: "run-x", generated_at: "2026-10-07T13:45:00Z", scope: { ...scope, sort: "price" }, state: "UNAVAILABLE", reason: "SYNTHESIS_DAILY_TOKEN_LIMIT",
        tokens_input: null, tokens_output: null, latency_ms: null }),
    ] });
    wrap(<AiRunHistory scope={scope} />);
    openDetails();
    const rows = (await screen.findAllByRole("row")).slice(1);
    expect(api.history).toHaveBeenCalledWith(20, expect.any(AbortSignal));
    expect(rows[0]).toHaveTextContent("09:58:12 ETclaude-haiku-4-5 · paidnothing selected0 of 2044k10.8sremoved EQ:BBB");
    expect(rows[1]).toHaveTextContent("09:50:00 ETclaude-haiku-4-5 · paidselected1 of 20 · EQ:BBBcached—added EQ:BBB · removed EQ:AAA");
    // A pass for another Screener query is listed, marked, and never compared with this one.
    expect(rows[2]).toHaveTextContent("09:45:00 ET · other scope (US_EQUITIES)");
    expect(rows[2]).toHaveTextContent("the run would exceed today's token budget (SYNTHESIS_DAILY_TOKEN_LIMIT)");
    expect(rows[2]).toHaveTextContent("first stored pass of this query");
    expect(rows[2]).toHaveClass("ai-run-history-other");
  });

  it("says so when nothing is stored or the history cannot be read", async () => {
    api.history.mockResolvedValue({ schema_version: "screener-ai-screener-history/1.0.0", limit: 20, runs: [] });
    const view = wrap(<AiRunHistory scope={scope} />);
    openDetails();
    expect(await screen.findByText("No pass has been stored on this machine yet.")).toBeInTheDocument();
    view.unmount();
    api.history.mockRejectedValue(new Error("offline"));
    wrap(<AiRunHistory scope={scope} />);
    openDetails();
    expect(await screen.findByRole("alert")).toHaveTextContent("Run history is unavailable.");
  });
});

describe("row marks", () => {
  const run = (overrides: Partial<AiScreenerRun> = {}, summary: Record<string, unknown> = {}): AiScreenerRun => ({ schema_version: "screener-ai-screener-run/1.0.0", run_id: "track-1", account_id: "paper",
    state: "COMPLETED", joined: false, scope, stage: null, stage_order: [], stages: [], started_at: "2026-10-07T13:58:00Z", finished_at: "2026-10-07T13:58:12Z", elapsed_ms: 12_000,
    engine: { provider_id: "p", model_id: "m", runtime: "PAID_API" }, timeout_seconds: 45, typical_latency_ms: null, typical_latency_samples: 0, intake_count: 3, sufficient_count: 1, packet_bytes: 1,
    result: null, error: null, summary: { state: "CURRENT", reason: null, candidate_run_id: "run-1", selected: [{ instrument_id: "EQ:AAA", rank: 1 }], intake: ["EQ:AAA", "EQ:BBB"],
      provider_id: "p", model_id: "m", runtime: "PAID_API", valid_until: "2099-01-01T00:00:00Z", limitations: [], ...summary }, ...overrides } as AiScreenerRun);

  it("mark the selected row with its rank, a row that was shown and not selected, and nothing else", () => {
    const { result } = renderHook(() => useAiRowMarks(run(), scope));
    const view = render(<><AiRowBadge marks={result.current} instrumentId="EQ:AAA" /><AiRowBadge marks={result.current} instrumentId="EQ:BBB" /><AiRowBadge marks={result.current} instrumentId="EQ:ZZZ" /></>);
    expect(screen.getByText("AI 1")).toHaveAttribute("title", "Selected by the AI Screener, rank 1 · pass finished 09:58:12 ET. A candidate for review, not an instruction to trade.");
    expect(screen.getByText("AI")).toHaveAttribute("title", "Shown to the AI Screener and not selected · pass finished 09:58:12 ET.");
    expect(view.container.querySelectorAll("span")).toHaveLength(2);
  });

  it("mark nothing for a pass that answered another query, failed, or produced no usable result", () => {
    expect(renderHook(() => useAiRowMarks(run({ scope: { ...scope, search: "B" } as AiScreenerRun["scope"] }), scope)).result.current).toBeNull();
    expect(renderHook(() => useAiRowMarks(run({ state: "FAILED", summary: null }), scope)).result.current).toBeNull();
    expect(renderHook(() => useAiRowMarks(run({}, { state: "UNAVAILABLE" }), scope)).result.current).toBeNull();
    expect(renderHook(() => useAiRowMarks(null, scope)).result.current).toBeNull();
    // The same query after a list refresh keeps its marks.
    expect(renderHook(() => useAiRowMarks(run(), { ...scope, result_set: "set-2" })).result.current?.ranks.get("EQ:AAA")).toBe(1);
  });

  it("strike a mark through at the moment its evidence expires, without a ticking clock", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-07T14:00:00Z"));
    const { result } = renderHook(() => useAiRowMarks(run({}, { valid_until: "2026-10-07T14:00:30Z" }), scope));
    expect(result.current?.expired).toBe(false);
    act(() => { vi.advanceTimersByTime(29_000); });
    expect(result.current?.expired).toBe(false);
    act(() => { vi.advanceTimersByTime(2_000); });
    expect(result.current?.expired).toBe(true);
    render(<AiRowBadge marks={result.current} instrumentId="EQ:AAA" />);
    expect(screen.getByText("AI 1")).toHaveClass("expired");
    expect(screen.getByText("AI 1").title).toContain("its evidence has expired: rerun before relying on it");
  });
});
