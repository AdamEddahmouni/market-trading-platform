import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AiScreenerPanel from "./AiScreenerPanel";
import { SpecialistContext, type SpecialistSelection } from "./shared";
import { AI_RUNS_KEY } from "../ai/useAiScreenerRuns";

const mocks = vi.hoisted(() => ({ runs: vi.fn() }));
vi.mock("../../../api/screenerAi", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerAi")>(), fetchAiScreenerRuns: mocks.runs }));

const scope = { universe: "US_EQUITIES" as const, search: "", sort: "volume", descending: true, filters: [] };
const selection = (overrides: Partial<SpecialistSelection> = {}): SpecialistSelection => ({
  row: null, universe: "US_EQUITIES", supportedPanels: new Set(["ai_screener"]), settledId: null, quote: undefined, filters: [],
  screenerScope: scope, openInstrument: vi.fn(), demand: null, actions: { close: vi.fn(), move: vi.fn(), resize: vi.fn() }, ...overrides,
});
const renderPanel = (value: SpecialistSelection, client = new QueryClient()) => render(<QueryClientProvider client={client}>
  <SpecialistContext.Provider value={value}><AiScreenerPanel /></SpecialistContext.Provider>
</QueryClientProvider>);

describe("AI Screener dock shortcut", () => {
  it("points to the right rail and shows the AI tab when asked", () => {
    const openAiRail = vi.fn();
    renderPanel(selection({ openAiRail }));
    expect(screen.getByText(/results, decisions and reevaluation controls are in the right rail’s AI tab/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show in right rail" }));
    expect(openAiRail).toHaveBeenCalledTimes(1);
  });

  it("states the latest pass from the cache the AI strip keeps, and requests nothing itself", () => {
    const client = new QueryClient();
    client.setQueryData(AI_RUNS_KEY, { state: "IDLE", active: null, latest: { state: "COMPLETED", summary: { selected: [{ instrument_id: "MSFT", rank: 1 }] } } });
    renderPanel(selection({ openAiRail: vi.fn() }), client);
    expect(screen.getByText("Latest pass: completed · 1 selected.")).toBeInTheDocument();
    expect(mocks.runs).not.toHaveBeenCalled();
    // None of the controls are mounted here as well.
    expect(screen.queryByRole("button", { name: /Run AI Screener/ })).toBeNull();
  });
});
