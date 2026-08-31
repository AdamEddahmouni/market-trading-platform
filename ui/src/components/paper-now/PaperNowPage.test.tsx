import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import { PaperNowPage, type PaperNowPageProps } from "./PaperNowPage";
import { attentionItem, paperPortfolio } from "./paperNowTestFixtures";

const mocks = vi.hoisted(() => ({ previewPaperOrder: vi.fn() }));

vi.mock("../../api/hooks", () => ({
  usePreviewPaperOrderMutation: () => ({ mutateAsync: mocks.previewPaperOrder, isPending: false }),
}));

function previewResponse(preview: Partial<PaperOrderPreviewResponse["preview"]> = {}): PaperOrderPreviewResponse {
  return {
    as_of_context: {
      mode: "PAPER",
      data_mode: "FIXTURE_REPLAY",
      execution_mode: "INTERNAL_SIMULATION",
      execution_authority: "PAPER_ONLY",
      as_of_time: "2026-08-31T12:00:00Z",
      timezone: "America/New_York",
    },
    preview: { risk_status: "PASS", decision: "ALLOW", ...preview },
  };
}

function pageProps(overrides: Partial<PaperNowPageProps> = {}): PaperNowPageProps {
  return {
    items: [
      attentionItem({ attention_id: "attention-macro", priority_rank: 1, instrument_id: undefined, headline: "Macro review" }),
      attentionItem({ attention_id: "attention-biya", priority_rank: 2, instrument_id: "BIYA", headline: "BIYA setup" }),
      attentionItem({ attention_id: "attention-nvda", priority_rank: 3, instrument_id: "NVDA", headline: "NVDA setup" }),
    ],
    attentionState: "ready",
    portfolio: paperPortfolio(),
    portfolioState: "ready",
    paperActionsPermitted: true,
    onWhy: vi.fn(),
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
    onContinue: vi.fn(),
    ...overrides,
  };
}

function renderPage(overrides: Partial<PaperNowPageProps> = {}) {
  const props = pageProps(overrides);
  return { props, ...render(<MemoryRouter><PaperNowPage {...props} /></MemoryRouter>) };
}

function completeDraft(quantity = "10") {
  fireEvent.click(screen.getByRole("radio", { name: "BUY" }));
  fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity" }), { target: { value: quantity } });
}

describe("PaperNowPage", () => {
  beforeEach(() => {
    mocks.previewPaperOrder.mockReset();
  });

  it("composes one Paper Command heading and four named decision regions", () => {
    renderPage();
    expect(screen.getByRole("heading", { level: 1, name: "Paper Command" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Risk summary" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Candidate queue" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Order preview" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Active exceptions" })).toBeInTheDocument();
  });

  it("selects the highest-priority instrument candidate and keeps research-only items available", () => {
    renderPage();
    expect(screen.getByRole("radio", { name: /BIYA candidate/ })).toBeChecked();
    expect(screen.getByText("Macro review").closest("article")).toHaveTextContent("Research only");
    expect(screen.getByRole("button", { name: "Explain Macro review" })).toBeEnabled();
  });

  it("starts with neutral direction, empty quantity, and Preview disabled", () => {
    renderPage();
    expect(screen.getByRole("radio", { name: "BUY" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "SELL" })).not.toBeChecked();
    expect(screen.getByRole("spinbutton", { name: "Quantity" })).toHaveValue(null);
    expect(screen.getByRole("button", { name: "Preview order" })).toBeDisabled();
  });

  it("enables Preview only with global permission and current Paper authority", () => {
    const deniedProps = pageProps({ paperActionsPermitted: false });
    const view = render(<MemoryRouter><PaperNowPage {...deniedProps} /></MemoryRouter>);
    completeDraft();
    expect(screen.getByRole("button", { name: "Preview order" })).toBeDisabled();

    const invalidAuthority = pageProps({ portfolio: paperPortfolio({ account: { execution_authority: "NONE" } }) });
    view.rerender(<MemoryRouter><PaperNowPage {...invalidAuthority} /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Preview order" })).toBeDisabled();

    view.rerender(<MemoryRouter><PaperNowPage {...pageProps()} /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Preview order" })).toBeEnabled();
  });

  it("previews an explicit MARKET request with a fresh shared attempt key", async () => {
    mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse());
    renderPage();
    completeDraft();
    fireEvent.click(screen.getByRole("button", { name: "Preview order" }));

    await waitFor(() => expect(mocks.previewPaperOrder).toHaveBeenCalledTimes(1));
    const request = mocks.previewPaperOrder.mock.calls[0][0];
    expect(request).toMatchObject({ side: "BUY", quantity: 10, order_type: "MARKET", instrument_id: "BIYA", symbol: "BIYA" });
    expect(request.client_order_id).toMatch(/^paper-now-/);
    expect(request.idempotency_key).toBe(request.client_order_id);
  });

  it("shows PASS evidence and emits only the validated draft for workspace revalidation", async () => {
    mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse({
      current_position_shares: 2,
      projected_position_shares: 12,
      current_gross_exposure_shares: 20,
      estimated_gross_exposure_shares: 30,
      risk_limits: { max_order_shares: 100, max_position_shares: 500, max_open_orders: 5 },
      risk_utilization: { position: "2.4%" },
      quality_state: "CURRENT",
      fill_preview_available: true,
      execution_model: "INTERNAL_FILL",
      execution_model_version: "v1",
    }));
    const { props } = renderPage();
    completeDraft();
    fireEvent.click(screen.getByRole("button", { name: "Preview order" }));

    expect(await screen.findByText(/Current position/)).toBeInTheDocument();
    expect(screen.getByText(/Projected position/)).toBeInTheDocument();
    expect(screen.getByText(/Limits: order 100/)).toBeInTheDocument();
    expect(screen.getByText("2.4%").closest("li")).toHaveTextContent("position");
    expect(screen.getByText(/Quality CURRENT/)).toBeInTheDocument();
    expect(screen.getByText(/Model INTERNAL_FILL · v1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open workspace and revalidate" }));
    expect(props.onContinue).toHaveBeenCalledWith({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 10,
      orderType: "MARKET",
      sourceAttentionId: "attention-biya",
    });
  });

  it("shows BLOCKED reasons without offering continuation", async () => {
    mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse({ risk_status: "BLOCKED", decision: "BLOCK", reason_codes: ["POSITION_LIMIT"] }));
    renderPage();
    completeDraft();
    fireEvent.click(screen.getByRole("button", { name: "Preview order" }));
    expect(await screen.findByText(/POSITION_LIMIT/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open workspace and revalidate" })).not.toBeInTheDocument();
  });

  it("invalidates a PASS immediately when the draft changes", async () => {
    mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse());
    renderPage();
    completeDraft();
    fireEvent.click(screen.getByRole("button", { name: "Preview order" }));
    expect(await screen.findByRole("button", { name: "Open workspace and revalidate" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity" }), { target: { value: "11" } });
    expect(screen.queryByRole("button", { name: "Open workspace and revalidate" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Preview result" })).not.toBeInTheDocument();
  });

  it("ignores a stale preview response after a newer draft is confirmed", async () => {
    let resolveFirst!: (value: PaperOrderPreviewResponse) => void;
    let resolveSecond!: (value: PaperOrderPreviewResponse) => void;
    mocks.previewPaperOrder
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve; }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveSecond = resolve; }));
    renderPage();
    completeDraft("10");
    fireEvent.click(screen.getByRole("button", { name: "Preview order" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity" }), { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview order" }));

    await act(async () => { resolveSecond(previewResponse({ projected_position_shares: 11 })); });
    expect(await screen.findByText("11 sh")).toBeInTheDocument();
    await act(async () => { resolveFirst(previewResponse({ projected_position_shares: 10 })); });
    expect(screen.queryByText("10 sh")).not.toBeInTheDocument();
    expect(screen.getByText("11 sh")).toBeInTheDocument();
  });

  it("preserves the draft and offers Retry after preview failure", async () => {
    mocks.previewPaperOrder.mockRejectedValueOnce(new Error("offline"));
    renderPage();
    completeDraft("17");
    fireEvent.click(screen.getByRole("button", { name: "Preview order" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Preview failed");
    expect(screen.getByRole("radio", { name: "BUY" })).toBeChecked();
    expect(screen.getByRole("spinbutton", { name: "Quantity" })).toHaveValue(17);
    expect(screen.getByRole("button", { name: "Retry preview" })).toBeEnabled();
  });

  it("contains no submission, cancellation, or session mutation controls", () => {
    renderPage();
    for (const name of ["Submit", "Cancel order", "Open session", "Close session", "Archive session", "New Paper Session"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});
