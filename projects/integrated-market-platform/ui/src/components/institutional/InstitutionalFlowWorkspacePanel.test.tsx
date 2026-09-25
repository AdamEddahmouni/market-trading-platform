import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { InstitutionalFlowWorkspacePanel } from "./InstitutionalFlowWorkspacePanel";

const flowFixture = {
  symbol: "BIYA",
  family_count: 2,
  available_family_count: 1,
  disclaimer: "Composite only.",
  families: [
    {
      family_id: "regulatory_disclosure",
      label: "Disclosure",
      entitled_symbol: "BIYA",
      route_path: "/workspace/BIYA/disclosure",
      available: true,
      reason: null,
      explanation_ref: "explain:disclosure:BIYA",
    },
    {
      family_id: "order_flow",
      label: "Order Flow",
      entitled_symbol: "NVDA",
      route_path: "/workspace/NVDA/order-flow",
      available: false,
      reason: "WHALE_NO_PIT_ELIGIBLE_OR_UNSUPPORTED",
      explanation_ref: "explain:order-flow:NVDA",
    },
  ],
};

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("InstitutionalFlowWorkspacePanel", () => {
  it("selects the first family when data arrives after loading", () => {
    const view = renderWithClient(
      <InstitutionalFlowWorkspacePanel instrumentId="BIYA" payload={null} loading />,
    );
    view.rerender(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <InstitutionalFlowWorkspacePanel instrumentId="BIYA" payload={flowFixture} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("tab", { name: /Disclosure/ })).toHaveAttribute("aria-selected", "true");
  });

  it("does not substitute fixture symbols when no family is entitled", () => {
    renderWithClient(
      <InstitutionalFlowWorkspacePanel
        instrumentId="BIYA"
        payload={{ ...flowFixture, families: [], family_count: 0, available_family_count: 0 }}
      />,
    );
    expect(screen.getByText("No entitled institutional-flow family is available.")).toBeInTheDocument();
    expect(screen.queryByText("NVDA")).not.toBeInTheDocument();
  });

  it("shows unavailable reason instead of fake rows", () => {
    renderWithClient(
      <InstitutionalFlowWorkspacePanel instrumentId="BIYA" payload={flowFixture} />,
    );
    expect(screen.getByText("WHALE_NO_PIT_ELIGIBLE_OR_UNSUPPORTED")).toBeInTheDocument();
    expect(screen.getByText("UNAVAILABLE")).toBeInTheDocument();
  });
});
