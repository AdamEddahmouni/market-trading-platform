import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import type { PaperOrderDraft } from "../paper-now/paperOrderDraft";
import { OrderTicket } from "./OrderTicket";

const mocks = vi.hoisted(() => ({ previewPaperOrder: vi.fn(), submitPaperOrder: vi.fn() }));
vi.mock("../../api/hooks", () => ({
  usePreviewPaperOrderMutation: () => ({ mutateAsync: mocks.previewPaperOrder, isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: mocks.submitPaperOrder, isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  usePaperPortfolioQuery: () => ({ data: {}, refetch: vi.fn() }),
}));

const validDraft: PaperOrderDraft = { version: 1, instrumentId: "BIYA", side: "SELL", quantity: 12, orderType: "MARKET", sourceAttentionId: "attention-biya" };

function previewResponse(preview: Partial<PaperOrderPreviewResponse["preview"]>): PaperOrderPreviewResponse {
  return {
    as_of_context: { mode: "PAPER", data_mode: "FIXTURE_REPLAY", execution_mode: "INTERNAL_SIMULATION", execution_authority: "PAPER_ONLY", as_of_time: "2026-08-31T12:00:00Z", timezone: "America/New_York" },
    preview: { risk_status: "PASS", decision: "ALLOW", ...preview },
  };
}

function ticket(initialDraft?: PaperOrderDraft, maxOrderShares = 100) {
  return <OrderTicket symbol="BIYA" executionAuthority="PAPER_ONLY" executionMode="INTERNAL_SIMULATION" dataMode="FIXTURE_REPLAY" maxOrderShares={maxOrderShares} initialDraft={initialDraft} />;
}

function renderTicket(initialDraft?: PaperOrderDraft, maxOrderShares = 100) {
  return render(ticket(initialDraft, maxOrderShares));
}

describe("OrderTicket workspace revalidation", () => {
  beforeEach(() => { mocks.previewPaperOrder.mockReset(); mocks.submitPaperOrder.mockReset(); });

  it("imports a draft, auto-previews once, and gates Submit on the fresh PASS", async () => {
    let resolvePreview!: (value: PaperOrderPreviewResponse) => void;
    mocks.previewPaperOrder.mockReturnValueOnce(new Promise((resolve) => { resolvePreview = resolve; }));
    renderTicket(validDraft);
    expect(await screen.findByDisplayValue("12")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SELL" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(mocks.previewPaperOrder).toHaveBeenCalledTimes(1));
    expect(mocks.previewPaperOrder).toHaveBeenCalledWith(expect.objectContaining({ side: "SELL", quantity: 12, instrument_id: "BIYA" }));
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    resolvePreview(previewResponse({ risk_status: "PASS", decision: "ALLOW" }));
    expect(await screen.findByRole("heading", { name: "Revalidated in workspace" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  it("keeps Submit disabled for a blocked workspace preview", async () => {
    mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse({ risk_status: "BLOCKED", decision: "BLOCK", reason_codes: ["POSITION_LIMIT"] }));
    renderTicket(validDraft);
    expect(await screen.findByText(/POSITION_LIMIT/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  it("retains the imported draft when automatic preview fails", async () => {
    mocks.previewPaperOrder.mockRejectedValueOnce(new Error("offline"));
    renderTicket(validDraft);
    expect(await screen.findByText("Preview failed")).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Quantity" })).toHaveValue(12);
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  it("does not auto-preview an ordinary workspace ticket", () => {
    renderTicket();
    expect(mocks.previewPaperOrder).not.toHaveBeenCalled();
  });

  it("invalidates a workspace PASS when the user edits the draft", async () => {
    mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse({ risk_status: "PASS", decision: "ALLOW" }));
    renderTicket(validDraft);
    expect(await screen.findByRole("heading", { name: "Revalidated in workspace" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity" }), { target: { value: "13" } });
    expect(screen.queryByRole("heading", { name: "Revalidated in workspace" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  it("ignores an in-flight workspace preview after the visible order changes", async () => {
    let resolvePreview!: (value: PaperOrderPreviewResponse) => void;
    mocks.previewPaperOrder.mockReturnValueOnce(new Promise((resolve) => { resolvePreview = resolve; }));
    renderTicket(validDraft);
    await waitFor(() => expect(mocks.previewPaperOrder).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity" }), { target: { value: "13" } });
    await act(async () => { resolvePreview(previewResponse({ risk_status: "PASS", decision: "ALLOW" })); });

    expect(screen.queryByRole("heading", { name: "Revalidated in workspace" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  it("invalidates a PASS when the current account share limit drops", async () => {
    mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse({ risk_status: "PASS", decision: "ALLOW" }));
    const view = renderTicket(validDraft);
    expect(await screen.findByRole("heading", { name: "Revalidated in workspace" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();

    view.rerender(ticket(validDraft, 10));

    await waitFor(() => expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled());
    expect(screen.queryByRole("heading", { name: "Revalidated in workspace" })).not.toBeInTheDocument();
  });
});
