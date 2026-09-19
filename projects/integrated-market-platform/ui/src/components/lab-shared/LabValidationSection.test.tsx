import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LabValidationSection } from "./LabValidationSection";

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
}));

describe("LabValidationSection", () => {
  beforeEach(() => {
    modelsState.isLoading = false;
    modelsState.isError = false;
    modelsState.error = null;
    modelsState.data = modelsFixture;
    vi.clearAllMocks();
  });

  it("shows loading and error states", () => {
    modelsState.isLoading = true;
    const { rerender } = render(
      <MemoryRouter>
        <LabValidationSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/loading validation workflow/i);
    modelsState.isLoading = false;
    modelsState.isError = true;
    modelsState.data = undefined;
    rerender(
      <MemoryRouter>
        <LabValidationSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/validation workflow snapshot is unavailable/i);
  });

  it("presents process, recorded config, and a Research bridge without a Run control", () => {
    render(
      <MemoryRouter>
        <LabValidationSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Walk-forward model validation" })).toBeInTheDocument();
    expect(screen.getByText("Read-only")).toBeInTheDocument();
    expect(screen.getByText("naive_last_value.v1")).toBeInTheDocument();
    expect(screen.getByText("Dataset provenance")).toBeInTheDocument();
    expect(screen.getByText("Recorded parameters")).toBeInTheDocument();
    expect(screen.getByText("How this snapshot was produced")).toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
    expect(screen.getByText(/cannot be started, cancelled, or retried/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View interpretation in Research" })).toHaveAttribute(
      "href",
      "/research/validation",
    );
    expect(screen.queryByRole("button", { name: /run/i })).not.toBeInTheDocument();
    expect(screen.getByText("Research-only — not tradeable")).toBeInTheDocument();
  });

  it("keeps hashes copyable without leaking epoch ns", () => {
    render(
      <MemoryRouter>
        <LabValidationSection />
      </MemoryRouter>,
    );
    expect(screen.getByText("Methodology and technical detail")).toBeInTheDocument();
    expect(screen.queryByText("abc123def4567890")).not.toBeInTheDocument();
    expect(screen.queryByText("1757500000000000000")).not.toBeInTheDocument();
    expect(screen.getByText("Conflicting evidence")).toBeInTheDocument();
  });

  it("is honest when there are no interpretation rows", () => {
    modelsState.data = { ...modelsFixture, interpretations: [] };
    render(
      <MemoryRouter>
        <LabValidationSection />
      </MemoryRouter>,
    );
    expect(screen.getByText(/No interpretations fall inside the current replay window/i))
      .toBeInTheDocument();
  });
});
