import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceIndex } from "./WorkspaceIndex";

const contextMock = vi.hoisted(() => ({
  isLoading: false,
  isError: false,
  data: undefined as
    | {
        as_of_context: { data_mode: string };
        active_instrument: string | null;
        scope_symbols: string[];
      }
    | undefined,
  refetch: vi.fn(),
}));
const investigationsMock = vi.hoisted(() => ({
  isLoading: false, isError: false, refetch: vi.fn(),
  data: { investigations: [] as Array<Record<string, unknown>> },
}));

vi.mock("@tanstack/react-query", () => ({ useQuery: () => investigationsMock }));

vi.mock("../api/hooks", () => ({
  useContextQuery: () => contextMock,
  queryKeys: { investigations: ["operator", "investigations"] },
}));

describe("WorkspaceIndex", () => {
  beforeEach(() => {
    contextMock.isLoading = false;
    contextMock.isError = false;
    contextMock.data = undefined;
    contextMock.refetch.mockReset();
    investigationsMock.data.investigations = [];
  });

  it("does not assume the Demo replay fixture when context fails", () => {
    contextMock.isError = true;
    render(
      <MemoryRouter>
        <WorkspaceIndex />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/workspace context is unavailable/i);
    expect(screen.queryByRole("heading", { name: /select an instrument/i })).not.toBeInTheDocument();
  });

  it("lists a durable investigation with a direct resume link", () => {
    contextMock.data = { as_of_context: { data_mode: "FIXTURE_REPLAY" }, active_instrument: "BIYA", scope_symbols: ["BIYA"] };
    investigationsMock.data.investigations = [{
      workspace_id: "ws-1", title: "BIYA catalyst", instrument_id: "BIYA",
      source_kind: "radar_attention", opportunity_id: "opp-1", status: "ACTIVE",
      updated_at: 1_780_000_000_000_000_000,
    }];
    render(<MemoryRouter><WorkspaceIndex /></MemoryRouter>);
    expect(screen.getByText(/Opportunity opp-1/)).toHaveTextContent("BIYA catalyst");
    expect(screen.getByRole("link", { name: "Resume" })).toHaveAttribute("href", "/workspace/BIYA?work=ws-1");
  });
});
