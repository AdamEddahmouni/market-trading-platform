import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemoWorkspacePage } from "./DemoWorkspacePage";

vi.mock("../../api/hooks", () => ({
  useContextQuery: () => ({
    data: {
      as_of_context: {
        mode: "REPLAY",
        data_mode: "FIXTURE_REPLAY",
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
        as_of_time: "2026-08-30T12:00:00Z",
        timezone: "America/New_York",
      },
      quality_summary: { state: "PASS" },
    },
  }),
  useWorkspaceEvidenceQuery: () => ({ data: undefined, isLoading: false }),
}));

vi.mock("../live/LiveMarketPanel", () => ({
  LiveMarketPanel: () => null,
}));

const observabilityProps = {
  instrumentId: "BIYA",
  bars: [],
  features: [],
  squeeze: null,
  replayChartAvailable: false,
  onScrub: () => undefined,
  cursorIndex: 0,
  maxIndex: 0,
};

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DemoWorkspacePage {...observabilityProps} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DemoWorkspacePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );
  });

  it("renders read-only demo workspace without order controls", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "BIYA" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  });
});
