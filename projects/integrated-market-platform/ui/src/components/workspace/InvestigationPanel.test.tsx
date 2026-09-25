import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { InvestigationPanel } from "./InvestigationPanel";

const backend = vi.hoisted(() => ({
  note: "initial note",
  post: vi.fn(),
}));

vi.mock("../../api/hooks", () => ({
  queryKeys: {
    investigations: ["operator", "investigations"],
    investigation: (id: string | null) => ["operator", "investigations", id],
  },
  useContextQuery: () => ({ data: { as_of_context: {
    data_mode: "FIXTURE_REPLAY", execution_mode: "INTERNAL_SIMULATION", execution_authority: "PAPER_ONLY",
  } } }),
}));

vi.mock("../../api/fetchJson", () => ({
  fetchJson: async (path: string) => {
    const row = {
      workspace_id: "ws-1", title: "BIYA investigation", instrument_id: "BIYA",
      source_kind: "instrument", source_id: null, opportunity_id: null,
      status: "ACTIVE", note: backend.note, created_at: 1, updated_at: 1,
    };
    return path === "/operator/investigations" ? { investigations: [row] } : row;
  },
  postJson: backend.post,
}));

describe("InvestigationPanel notes", () => {
  it("keeps Demo and Live investigation controls read-only", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/workspace/BIYA?attention=radar-1"]}>
      <InvestigationPanel instrumentId="BIYA" mode="LIVE" />
    </MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText(/Radar context is read-only in this mode/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New investigation" })).not.toBeInTheDocument();
    expect(backend.post).not.toHaveBeenCalled();
  });

  it("keeps a draft and uses its original base note when the server refetches", async () => {
    backend.note = "initial note";
    backend.post.mockReset().mockRejectedValue(new Error("conflict"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/workspace/BIYA?work=ws-1"]}>
      <InvestigationPanel instrumentId="BIYA" mode="PAPER" />
    </MemoryRouter></QueryClientProvider>);
    const editor = await screen.findByRole("textbox", { name: "Investigation notes" });
    await waitFor(() => expect(editor).toHaveValue("initial note"));
    fireEvent.change(editor, { target: { value: "unsaved draft" } });
    backend.note = "other editor's note";
    await client.invalidateQueries({ queryKey: ["operator", "investigations", "ws-1"] });
    expect(editor).toHaveValue("unsaved draft");
    fireEvent.click(screen.getByRole("button", { name: "Save notes" }));
    await waitFor(() => expect(backend.post).toHaveBeenCalledWith(
      "/operator/investigations/ws-1/note",
      { note: "unsaved draft", expected_note: "initial note" },
      expect.anything(),
    ));
  });
});
