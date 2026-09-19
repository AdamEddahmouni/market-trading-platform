import { describe, expect, it } from "vitest";
import {
  buildOpportunityOperatorBrief,
  collectOpportunityConflicts,
  collectOpportunityInvalidationLines,
  collectOpportunityProviderLabels,
  collectOpportunityUnknowns,
} from "./opportunityOperatorBrief";
import { fixtureOpportunityRowBase } from "./opportunityDetailFixtures";

describe("opportunityOperatorBrief", () => {
  it("keeps missing providers, conflicts, and invalidation as UNKNOWN", () => {
    const brief = buildOpportunityOperatorBrief(fixtureOpportunityRowBase, null, {
      paperActions: true,
    });
    const byQuestion = Object.fromEntries(brief.map((row) => [row.question, row]));
    expect(byQuestion["Which providers support it?"]?.answer).toBe("REPLAY");
    expect(byQuestion["Which facts conflict?"]?.answer).toMatch(/^UNKNOWN/);
    expect(byQuestion["What would invalidate it?"]?.honesty).toBe("UNKNOWN");
    expect(byQuestion["What action is available?"]?.answer).toMatch(/Not a live order/i);
    expect(JSON.stringify(brief)).not.toMatch(/calibrat/i);
    expect(JSON.stringify(brief)).not.toMatch(/place a (live|real-money) /i);
  });

  it("lists attached providers and missing ranking inputs without inventing scores", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      data_quality: { status: "PASS", freshness: "FRESH", source: "FINVIZ_ELITE" },
      lineage_refs: [{ provider: "MOOMOO" }],
      ranking_vector: {
        basis: "COMPARATOR_LEXICOGRAPHIC",
        dimensions: [
          { name: "attention_score", status: "PRESENT", value: 74.5 },
          { name: "freshness", status: "PRESENT", value: "FRESH" },
          { name: "liquidity", status: "MISSING" },
        ],
      },
      unavailable_fields: ["spread"],
    };
    expect(collectOpportunityProviderLabels(row)).toEqual(["FINVIZ_ELITE", "MOOMOO"]);
    expect(collectOpportunityUnknowns(row)).toEqual(["spread", "ranking.liquidity MISSING"]);
    const brief = buildOpportunityOperatorBrief(row);
    const unknown = brief.find((item) => item.question === "What is unknown?");
    expect(unknown?.answer).toMatch(/liquidity/);
    expect(unknown?.answer).not.toMatch(/probability/i);
  });

  it("reports attached conflicts and does not claim an empty conflict set", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      supersession_reason: "REPLACED_BY_NEWER",
    };
    expect(collectOpportunityConflicts(row)).toEqual(["Supersession: REPLACED_BY_NEWER"]);
    expect(collectOpportunityInvalidationLines(row).join(" ")).toMatch(/supersession/i);
  });

  it("refuses fake actionability in Demo read-only", () => {
    const brief = buildOpportunityOperatorBrief(fixtureOpportunityRowBase, null, {
      readOnly: true,
      paperActions: false,
    });
    const action = brief.find((item) => item.question === "What action is available?");
    const refusal = brief.find((item) => item.question === "Why might action be refused?");
    expect(action?.answer).toMatch(/Inspect and explain only/i);
    expect(refusal?.answer).toMatch(/read-only/i);
    expect(refusal?.answer).toMatch(/never grants live execution/i);
  });
});
