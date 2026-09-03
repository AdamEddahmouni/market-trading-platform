import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HistoricalSqueezeContextBlock } from "./HistoricalSqueezeContextBlock";

describe("HistoricalSqueezeContextBlock", () => {
  it("renders cohort member details", () => {
    render(
      <HistoricalSqueezeContextBlock
        context={{
          available: true,
          membership: "IN_COHORT",
          cohort_id: "phase_3f_historical_calibration_v1",
          case_boundary_count: 35,
          unique_symbol_count: 29,
          policy_review_status: "COMPLETE",
          policy_review_date: "2026-08-17",
          detection_policy: "phase_3b_research_detection_policy.v1",
          outcome_policy: "phase_3b_outcome_label_policy.v1",
          primary_case: {
            case_id: "AVTX_ARTIFACT_DISCOVERY",
            symbol: "AVTX",
            case_type: "ORIGINAL_PLATFORM_STATUS_UNKNOWN",
            research_detection_status: "UNEVALUABLE",
            outcome_label: "NO_SUBSTANTIAL_UPWARD_MOVE",
            research_classification: "UNEVALUABLE",
            maximum_observed_move_percent: 0.72,
            maximum_adverse_move_percent: -7.07,
            evaluation_as_of: "2026-07-18T13:37:55.017661Z",
            in_frozen_demo: true,
          },
          case_boundaries: [
            {
              case_id: "AVTX_ARTIFACT_DISCOVERY",
              symbol: "AVTX",
              case_type: "ORIGINAL_PLATFORM_STATUS_UNKNOWN",
              research_detection_status: "UNEVALUABLE",
              outcome_label: "NO_SUBSTANTIAL_UPWARD_MOVE",
              research_classification: "UNEVALUABLE",
              maximum_observed_move_percent: 0.72,
              maximum_adverse_move_percent: -7.07,
              evaluation_as_of: "2026-07-18T13:37:55.017661Z",
              in_frozen_demo: true,
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("Historical squeeze context")).toBeInTheDocument();
    expect(screen.getByText("AVTX_ARTIFACT_DISCOVERY")).toBeInTheDocument();
    expect(screen.getByText("NO_SUBSTANTIAL_UPWARD_MOVE")).toBeInTheDocument();
  });

  it("renders not-in-cohort reason", () => {
    render(
      <HistoricalSqueezeContextBlock
        context={{
          available: false,
          membership: "NOT_IN_COHORT",
          reason: "ZZZZ is not in the Phase 3F historical calibration cohort.",
          case_boundary_count: 35,
          policy_review_status: "COMPLETE",
          policy_review_date: "2026-08-17",
        }}
      />,
    );
    expect(screen.getByText(/ZZZZ is not in the Phase 3F historical calibration cohort/)).toBeInTheDocument();
  });
});
