import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PaperPreviewStatus } from "./PaperPreviewStatus";
import type { PaperPreviewPresentationState } from "./paperPreviewPresentation";

function renderState(state: PaperPreviewPresentationState) {
  return render(<PaperPreviewStatus state={state} />);
}

describe("PaperPreviewStatus", () => {
  it.each([
    ["NOT_PREVIEWED", "Not previewed"],
    ["PREVIEWING", "Previewing"],
    ["ACCEPTED", "Preview accepted"],
    ["REJECTED", "Preview rejected"],
    ["REVALIDATION_REQUIRED", "Revalidation required"],
    ["AUTHORITY_UNAVAILABLE", "Authority unavailable"],
    ["ERROR", "Preview error"],
  ] as const)("renders %s", (status, title) => {
    renderState({
      status,
      title,
      message: "detail",
      canSubmit: false,
    });
    expect(screen.getByRole("heading", { name: "Preview status" })).toBeInTheDocument();
    expect(screen.getByText(title)).toBeInTheDocument();
  });

  it("surfaces previewed order and placeholder confirmation guidance", () => {
    renderState({
      status: "ACCEPTED",
      title: "Revalidated in workspace",
      message: "Confirm the placeholder side and quantity are intentional before submit.",
      canSubmit: false,
      previewedOrderLabel: "BUY × 1 MARKET",
      requiresPlaceholderConfirmation: true,
    });
    expect(screen.getByTestId("paper-previewed-order-label")).toHaveTextContent(
      /BUY × 1 MARKET \(placeholder — confirm before submit\)/i,
    );
    expect(
      screen.getByText(/Submit stays disabled until you confirm the editable placeholder/i),
    ).toBeInTheDocument();
  });
});
