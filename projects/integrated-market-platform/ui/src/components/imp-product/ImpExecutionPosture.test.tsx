import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ImpExecutionPosture } from "./ImpExecutionPosture";

vi.mock("../../api/hooks", () => ({
  usePaperPortfolioQuery: () => ({
    data: { account: { paper_account_id: "paper-acct-99" } },
  }),
}));

describe("ImpExecutionPosture", () => {
  it("shows paper account chip in paper mode", () => {
    render(<ImpExecutionPosture mode="PAPER" />);
    const chip = screen.getByTestId("imp-ui-copyable-id");
    expect(chip).toHaveTextContent("Acct pape…t-99");
    expect(chip).toHaveAttribute("title", "paper-acct-99");
  });
});
