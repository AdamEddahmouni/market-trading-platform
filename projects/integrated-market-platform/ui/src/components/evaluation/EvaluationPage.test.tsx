import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { EvaluationView } from "./EvaluationPage";
import fixture from "./evaluationFixture.json";
import { EvaluationSummarySchema } from "../../api/prospectiveEvaluation";

describe("Outcome evaluation", () => {
  it("shows class, cutoff, N, costs and low-sample limits", () => {
    render(<MemoryRouter><EvaluationView report={EvaluationSummarySchema.parse(fixture)} records={fixture.inputs.records} onDetail={vi.fn()} /></MemoryRouter>);
    expect(screen.getByText("SOFTWARE_CONTROLLED", {selector:"strong"})).toBeInTheDocument();
    expect(screen.getByText(/Insufficient sample for strong performance conclusions/, {selector:"p"})).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Weekly Paper results" })).toBeInTheDocument();
    expect(screen.getByText("Expectancy / completed trade")).toBeInTheDocument();
    expect(screen.getByText("Explicit costs")).toBeInTheDocument();
    expect(screen.getByText(fixture.cutoff, {selector:"time"})).toBeInTheDocument();
  });
  it("changes segment N and opens a record without execution", () => {
    const detail=vi.fn();
    render(<MemoryRouter><EvaluationView report={EvaluationSummarySchema.parse(fixture)} records={fixture.inputs.records} onDetail={detail} /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Group by"),{target:{value:"model"}});
    expect(screen.getByRole("table",{name:"Segment comparison"})).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button",{name:/Inspect/})[0]);
    expect(detail).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button",{name:/Submit|Promote|Activate/})).not.toBeInTheDocument();
  });
});
