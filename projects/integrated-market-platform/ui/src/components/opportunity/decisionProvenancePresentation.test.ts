import { describe, expect, it } from "vitest";
import {
  buildDecisionProvenancePresentation,
  classifyThesisHonesty,
} from "./decisionProvenancePresentation";
import {
  fixtureOpportunityDecisionProvenanceEvidence,
  fixtureOpportunityEvidenceRefresh,
  fixtureOpportunityRowBase,
} from "./opportunityDetailFixtures";

describe("decisionProvenancePresentation", () => {
  it("returns absent when no decision provenance is attached", () => {
    const presentation = buildDecisionProvenancePresentation(
      fixtureOpportunityEvidenceRefresh,
      fixtureOpportunityRowBase,
    );
    expect(presentation.present).toBe(false);
    expect(presentation.fields).toEqual([]);
  });

  it("labels origin, thesis, invalidation, freshness, and actionability without inventing scores", () => {
    const presentation = buildDecisionProvenancePresentation(
      fixtureOpportunityDecisionProvenanceEvidence,
      fixtureOpportunityRowBase,
    );
    expect(presentation.present).toBe(true);
    const byLabel = Object.fromEntries(presentation.fields.map((row) => [row.label, row]));
    expect(byLabel["Origin"]?.value).toMatch(/STRATEGY_MATCH/);
    expect(byLabel["Origin"]?.value).toMatch(/momentum-5m/);
    expect(byLabel["Thesis statement"]?.value).toMatch(/Momentum continuation/);
    expect(byLabel["Thesis statement"]?.value).toMatch(/derived/i);
    expect(byLabel["Thesis statement"]?.value).toMatch(/not an observed market fact/i);
    expect(byLabel["Thesis statement"]?.honesty).toBe("DERIVED");
    expect(byLabel["Invalidation criteria"]?.value).toMatch(/TREND_BREAK/);
    expect(byLabel["Invalidation criteria"]?.value).toMatch(/SPREAD_TOO_WIDE/);
    expect(byLabel["Freshness window"]?.value).toMatch(/valid_until_ns/);
    expect(byLabel["Why still actionable \/ why not"]?.value).toMatch(/ACTIONABLE/);
    expect(byLabel["Why still actionable \/ why not"]?.value).toMatch(/LIFECYCLE_ELIGIBLE/);
    const blob = JSON.stringify(presentation);
    expect(blob).not.toMatch(/rank_score/i);
    expect(blob).not.toMatch(/probability/i);
    expect(blob).not.toMatch(/universal_score/i);
  });

  it("never classifies thesis honesty as OBSERVED", () => {
    expect(classifyThesisHonesty("OBSERVED")).toBe("ASSERTED");
    expect(classifyThesisHonesty("DERIVED")).toBe("DERIVED");
    const coerced = buildDecisionProvenancePresentation(
      {
        ...fixtureOpportunityDecisionProvenanceEvidence,
        decision_provenance: {
          ...(fixtureOpportunityDecisionProvenanceEvidence.decision_provenance as Record<string, unknown>),
          thesis: {
            statement: "Should never look observed",
            honesty: "OBSERVED",
            invalidation_criteria: ["TREND_BREAK"],
          },
        },
      },
      fixtureOpportunityRowBase,
    );
    const thesis = coerced.fields.find((row) => row.label === "Thesis statement");
    expect(thesis?.honesty).not.toBe("OBSERVED");
    expect(thesis?.honesty).toBe("ASSERTED");
    expect(thesis?.value).toMatch(/asserted/i);
    expect(thesis?.value).toMatch(/not an observed market fact/i);
  });

  it("keeps AI-assisted notes visually non-authoritative and separate", () => {
    const presentation = buildDecisionProvenancePresentation(
      fixtureOpportunityDecisionProvenanceEvidence,
      fixtureOpportunityRowBase,
    );
    expect(presentation.aiAssistedNotes.every((row) => row.nonAuthoritative)).toBe(true);
    expect(presentation.aiAssistedNotes.some((row) => /Model paraphrase/.test(row.value))).toBe(true);
    expect(presentation.fields.every((row) => !row.nonAuthoritative)).toBe(true);
  });
});
