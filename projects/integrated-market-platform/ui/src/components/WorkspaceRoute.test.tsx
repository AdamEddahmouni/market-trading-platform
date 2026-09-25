import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceRoute } from "./WorkspaceRoute";

vi.mock("../api/hooks", () => ({
  useInstrumentQuery: () => ({ isLoading: false, error: null, data: { bars: [], features: [] } }),
  useWorkspaceSqueezeQuery: () => ({ isLoading: false, data: null }),
}));
vi.mock("./ModeWorkspacePage", () => ({
  ModeWorkspacePage: ({ initialPaperOrderDraft }: { initialPaperOrderDraft?: unknown }) => <output data-testid="draft">{initialPaperOrderDraft ? JSON.stringify(initialPaperOrderDraft) : "none"}</output>,
}));
vi.mock("./workspace/InvestigationPanel", () => ({ InvestigationPanel: () => null }));

const validDraft = { version: 1, instrumentId: "BIYA", side: "SELL", quantity: 12, orderType: "MARKET" };
const routeProps = { mode: "PAPER" as const, paperActionsPermitted: true, onScrub: vi.fn(), onExplain: vi.fn(), onInspect: vi.fn(), cursorIndex: 0, maxIndex: 0 };

function Launcher({ state }: { state: unknown }) {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate("/workspace/BIYA", { state })}>Open</button>;
}

function Switcher() {
  const navigate = useNavigate();
  return <>
    <button type="button" onClick={() => navigate("/workspace/BIYA", { state: validDraft })}>Open first</button>
    <button type="button" onClick={() => navigate("/workspace/NVDA")}>Open second</button>
    <button type="button" onClick={() => navigate("/workspace/NVDA", { state: { ...validDraft, instrumentId: "NVDA", quantity: 3 } })}>Trade second</button>
  </>;
}

function renderPush(state: unknown) {
  render(<MemoryRouter initialEntries={["/start"]}><Routes><Route path="/start" element={<Launcher state={state} />} /><Route path="/workspace/:symbol" element={<WorkspaceRoute {...routeProps} />} /></Routes></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Open" }));
}

describe("WorkspaceRoute Paper draft state", () => {
  it("accepts a matching version-1 draft from a fresh PUSH", async () => {
    renderPush(validDraft);
    expect(await screen.findByTestId("draft")).toHaveTextContent('"instrumentId":"BIYA"');
  });

  it.each([
    { ...validDraft, instrumentId: "NVDA" },
    { ...validDraft, risk_status: "PASS" },
    { ...validDraft, version: 2 },
  ])("ignores invalid or authority-bearing state", async (state) => {
    renderPush(state);
    expect(await screen.findByTestId("draft")).toHaveTextContent("none");
  });

  it("ignores history state on POP so reloads are ephemeral", async () => {
    render(<MemoryRouter initialEntries={[{ pathname: "/workspace/BIYA", state: validDraft }]}><Routes><Route path="/workspace/:symbol" element={<WorkspaceRoute {...routeProps} />} /></Routes></MemoryRouter>);
    expect(await screen.findByTestId("draft")).toHaveTextContent("none");
  });

  it("replaces the handoff when the mounted Workspace route changes instruments", async () => {
    render(<MemoryRouter initialEntries={["/start"]}><Switcher /><Routes><Route path="/workspace/:symbol" element={<WorkspaceRoute {...routeProps} />} /></Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Open first" }));
    expect(await screen.findByTestId("draft")).toHaveTextContent('"instrumentId":"BIYA"');
    fireEvent.click(screen.getByRole("button", { name: "Open second" }));
    expect(screen.getByTestId("draft")).toHaveTextContent("none");
    fireEvent.click(screen.getByRole("button", { name: "Trade second" }));
    expect(screen.getByTestId("draft")).toHaveTextContent('"instrumentId":"NVDA"');
  });
});
