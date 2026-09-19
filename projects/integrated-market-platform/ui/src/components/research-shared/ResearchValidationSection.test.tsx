import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchValidationSection } from "./ResearchValidationSection";

const modelsFixture = {
  as_of_context: { mode: "REPLAY", as_of_time: "2026-09-15T13:30:00Z", timezone: "UTC" },
  authority_boundary: "READ_ONLY_RESEARCH",
  disclaimer: "Model lab only.",
  epistemic_class: "RESEARCH_PROJECTION",
  walk_forward_fold_count: 5,
  preregistration_status: "PASS",
  model_summary: {
    model_family: "naive_last_value.v1",
    alignment_type: "FORECAST_MOMENTUM",
    strategy_identity_hash: "abc123def4567890",
    dataset_fingerprint: "fff000eee1112222",
  },
  strategy_spec: { alignment_type: "FORECAST_MOMENTUM" },
  dataset_manifest: {},
  preregistration: { registered_at: "2026-09-01T00:00:00Z" },
  interpretation_summary: { abstention_count: 1, signal_count: 1, total_at_cutoff: 2 },
  interpretations: [
    {
      observation_time: 1_757_500_000_000_000_000,
      outcome: "signal",
      prediction_cutoff: 1_757_500_300_000_000_000,
      alignment_decision: "ALIGNED",
      abstention_reason_codes: [],
    },
    {
      observation_time: 1_757_501_000_000_000_000,
      outcome: "abstention",
      prediction_cutoff: 1_757_501_300_000_000_000,
      abstention_reason_codes: ["ABSTAIN_CONFLICTING_EVIDENCE"],
    },
  ],
};

const modelsState = {
  isLoading: false,
  isError: false,
  error: null as Error | null,
  data: modelsFixture as typeof modelsFixture | undefined,
  refetch: vi.fn(),
};

vi.mock("../../api/hooks", () => ({
  useResearchModelsQuery: () => modelsState,
  usePaperStrategyProfitabilityQuery: () => ({ isLoading: false, isError: true, data: undefined }),
}));

function renderSection(mode: "DEMO" | "PAPER" | "LIVE" = "DEMO", path = "/research/validation") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ResearchValidationSection mode={mode} />
    </MemoryRouter>,
  );
}

describe("ResearchValidationSection", () => {
  beforeEach(() => {
    modelsState.isLoading = false;
    modelsState.isError = false;
    modelsState.error = null;
    modelsState.data = modelsFixture;
    vi.clearAllMocks();
  });

  it("shows a loading state", () => {
    modelsState.isLoading = true;
    renderSection();
    expect(screen.getByRole("status")).toHaveTextContent(/loading strategy validation/i);
  });

  it("shows a humanized error state with retry", () => {
    modelsState.isError = true;
    modelsState.data = undefined;
    renderSection();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /strategy validation is unavailable right now/i,
    );
  });

  it("leads with a human validation summary and preregistration state", () => {
    renderSection();
    expect(screen.getByText(/Model family naive_last_value\.v1/i)).toBeInTheDocument();
    expect(screen.getByText("Preregistered")).toBeInTheDocument();
    expect(screen.getByText("Research-only — not tradeable")).toBeInTheDocument();
  });

  it("humanizes interpretation outcomes and abstention reasons", () => {
    renderSection();
    expect(screen.getByText("Signal")).toBeInTheDocument();
    expect(screen.getByText("Abstained")).toBeInTheDocument();
    expect(screen.getByText("Conflicting evidence")).toBeInTheDocument();
    const conflicted = screen.getByText("Conflicting evidence").closest("tr");
    expect(conflicted).toHaveAttribute("data-conflicted", "true");
    // Raw epoch-ns timestamps must not leak into the primary table.
    expect(screen.queryByText("1757500000000000000")).not.toBeInTheDocument();
  });

  it("keeps identity hashes inside the methodology disclosure", () => {
    renderSection();
    const methodology = screen.getByText("Methodology and technical detail");
    expect(methodology).toBeInTheDocument();
    // Full hashes are never rendered; CopyableIdentifier truncates in the middle.
    expect(screen.queryByText("abc123def4567890")).not.toBeInTheDocument();
    expect(screen.getByText("abc123…567890")).toBeInTheDocument();
  });

  it("is honest when no interpretations fall inside the window", () => {
    modelsState.data = { ...modelsFixture, interpretations: [] };
    renderSection();
    expect(screen.getByText(/No interpretations fall inside the current replay window/i))
      .toBeInTheDocument();
  });

  it("filters to contract-backed conflicts when ?conflict=1", () => {
    renderSection("DEMO", "/research/validation?conflict=1");
    expect(screen.getByText("Conflicting evidence")).toBeInTheDocument();
    expect(screen.queryByText("Signal")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Show the full interpretation record" })).toHaveAttribute(
      "href",
      "/research/validation",
    );
  });

  it("renders the Paper strategy context only in Paper mode", () => {
    renderSection("PAPER");
    expect(
      screen.getByRole("heading", { name: "Strategy outcomes in Paper" }),
    ).toBeInTheDocument();
  });

  it("does not follow squeeze into a fake Lab validation process hop", () => {
    renderSection("DEMO", "/research/validation?claim=squeeze_outcomes");
    expect(screen.queryByRole("link", { name: "Follow implementation" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inspect this validation workflow in Lab" })).toHaveAttribute(
      "href",
      "/lab/validation",
    );
  });
});
