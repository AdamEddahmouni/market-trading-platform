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
});
