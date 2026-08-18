import type { WorkspaceSqueezeResponse } from "../../api/client";

export const frozenSqueezeFixture: WorkspaceSqueezeResponse = {
  symbol: "AVTX",
  source: "short-squeeze-project",
  bridge_mode: "READ_ONLY",
  available: true,
  replay_chart_available: false,
  ignition_state: "WATCH",
  freshness: "FROZEN",
  disclaimer: "Donor squeeze evidence is read-only research. No trade recommendation.",
  explanation_ref: "explain:squeeze:AVTX",
  outcome_status: "NO_SUBSTANTIAL_UPWARD_MOVE",
  evidence_coverage: "partial",
  research_detection: "DETECTED",
  phase3a_summary: "2 PASS / 3 FAIL / 1 UNKNOWN",
  mode_label: "FROZEN_RESEARCH",
  epistemic_class: "OBSERVED",
  rules: [
    {
      rule_id: "FLOAT_MAXIMUM",
      category: "SHORT_PRESSURE_CONFIRMATION",
      outcome: "FAIL",
      reason: "float above threshold",
    },
  ],
  ignition_evidence: [
    {
      label: "SI / Float",
      state: "FROZEN",
      detail: "1 FAIL",
      epistemic_class: "OBSERVED",
    },
    {
      label: "Borrow",
      state: "UNAVAILABLE",
      detail: "No borrow rules in frozen aggregate",
      epistemic_class: "OBSERVED",
    },
    {
      label: "Options",
      state: "UNAVAILABLE",
      detail: "Options flow not included in sanitized frozen aggregate",
      epistemic_class: "OBSERVED",
    },
  ],
  state_machine: {
    current_state: "WATCH",
    last_transition_label: "frozen — no live transition stream",
    changed_criteria: [
      {
        rule_id: "FLOAT_MAXIMUM",
        category: "SHORT_PRESSURE_CONFIRMATION",
        outcome: "FAIL",
        reason: "float above threshold",
      },
    ],
    unchanged_criteria: [],
    transitions: [
      {
        at_label: "FROZEN",
        from_state: "INITIAL",
        kind: "frozen_snapshot",
        to_state: "WATCH",
        trigger: "FROZEN_DEMO aggregate load",
      },
    ],
  },
  readiness: {
    freshness_state: "FROZEN",
    provenance_admissible: true,
    rule_outcome_totals: { FAIL: 1, PASS: 0, UNKNOWN: 0, INCOMPLETE: 0 },
  },
};
