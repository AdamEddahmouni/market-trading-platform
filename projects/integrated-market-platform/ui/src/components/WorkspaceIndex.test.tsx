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

vi.mock("../api/hooks", () => ({
  useContextQuery: () => contextMock,
}));

describe("WorkspaceIndex", () => {
  beforeEach(() => {
    contextMock.isLoading = false;
    contextMock.isError = false;
    contextMock.data = undefined;
    contextMock.refetch.mockReset();
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
});
