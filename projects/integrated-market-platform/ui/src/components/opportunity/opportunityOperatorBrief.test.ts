import { describe, expect, it } from "vitest";
import {
  buildOpportunityOperatorBrief,
  collectOpportunityConflicts,
  collectOpportunityInvalidationLines,
  collectOpportunityProviderLabels,
  collectOpportunityUnknowns,
  liveFeedClockHonesty,
  readOpportunityFreshnessView,
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
    expect(JSON.stringify(brief)).not.toMatch(/Item 9/);
    expect(JSON.stringify(brief)).not.toMatch(/3\/3/);
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

  it("treats STALE freshness and expired lifecycle as invalidation, not current evidence", () => {
    const brief = buildOpportunityOperatorBrief({
      ...fixtureOpportunityRowBase,
      lifecycle_state: "EXPIRED",
      data_quality: { status: "PASS", freshness: "STALE", source: "MOOMOO" },
    });
    const freshness = brief.find((item) => item.question === "How fresh?");
    const happened = brief.find((item) => item.question === "What happened?");
    const invalidate = brief.find((item) => item.question === "What would invalidate it?");
    expect(freshness?.answer.toUpperCase()).toContain("STALE");
    expect(happened?.answer).toMatch(/Expired/i);
    expect(invalidate?.honesty).toBe("DERIVED");
    expect(invalidate?.answer).toMatch(/STALE/);
    expect(invalidate?.answer).toMatch(/expired/i);
  });

  it("refuses action when eligibility is INELIGIBLE", () => {
    const brief = buildOpportunityOperatorBrief(
      {
        ...fixtureOpportunityRowBase,
        eligibility_state: "INELIGIBLE",
        next_safe_action: "STOP",
      },
      null,
      { paperActions: true },
    );
    const action = brief.find((item) => item.question === "What action is available?");
    const refusal = brief.find((item) => item.question === "Why might action be refused?");
    expect(action?.answer).not.toMatch(/live order/i);
    expect(refusal?.answer).toMatch(/INELIGIBLE/i);
    expect(refusal?.answer).toMatch(/never grants live execution/i);
  });

  it("does not treat a shared receive/event clock as independent lag", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      data_quality: {
        status: "UNAVAILABLE",
        freshness: "FRESH",
        source: "LIVE_OBSERVATIONAL",
        freshness_evaluation: {
          status: "FRESH",
          reason_code: "FRESH",
          source: "LIVE_OBSERVATIONAL",
          actionable: true,
          as_of_time_ns: 1_700_000_000_000_000_000,
          age_ns: 0,
        },
      },
    };
    const view = readOpportunityFreshnessView(row);
    expect(view.sameClock).toBe(true);
    expect(view.honesty).toBe("DERIVED");
    expect(view.operatorAnswer).toMatch(/lag UNKNOWN/i);
    expect(collectOpportunityUnknowns(row)).toContain("event_vs_receive_lag");
    const brief = buildOpportunityOperatorBrief(row, null, {
      feed: { as_of_time: "2026-09-19T11:00:00Z", as_of_provenance: "live_receive", data_mode: "LIVE_OBSERVATIONAL" },
    });
    const freshness = brief.find((item) => item.question === "How fresh?");
    expect(freshness?.answer).toMatch(/Feed as-of 2026-09-19T11:00:00Z/);
    expect(freshness?.answer).not.toMatch(/created_at is live/i);
  });

  it("keeps missing live receive clocks as NOT_APPLICABLE, not FRESH", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      data_quality: {
        status: "UNAVAILABLE",
        freshness: "NOT_APPLICABLE",
        source: "LIVE_OBSERVATIONAL",
        reason_codes: ["LIVE_OBSERVATIONAL_NOT_ENGINE_QUALITY"],
        freshness_evaluation: {
          status: "NOT_APPLICABLE",
          reason_code: "LIVE_AS_OF_UNAVAILABLE",
          source: "LIVE_OBSERVATIONAL",
          actionable: false,
        },
      },
    };
    const view = readOpportunityFreshnessView(row);
    expect(view.status).toBe("NOT_APPLICABLE");
    expect(view.reasonCode).toBe("LIVE_AS_OF_UNAVAILABLE");
    expect(view.operatorAnswer).not.toMatch(/Fresh(?!ness)/);
    const brief = buildOpportunityOperatorBrief(row, null, {
      readOnly: true,
      unreadyReason: "LIVE_AS_OF_UNAVAILABLE",
      withheldRankedCount: 4,
      bookHonesty: "RANKED_ROWS_WITHHELD_NO_LIVE_CLOCK",
    });
    const blob = JSON.stringify(brief);
    expect(blob).toMatch(/LIVE_AS_OF_UNAVAILABLE|live receive clock/i);
    expect(blob).toMatch(/4 ranked row/);
    expect(blob).not.toMatch(/calibrat/i);
    expect(blob).not.toMatch(/3\/3/);
    expect(liveFeedClockHonesty({ unreadyReason: "LIVE_AS_OF_UNAVAILABLE", withheldRankedCount: 4 })).toMatch(
      /Live execution stays OFF/i,
    );
    expect(liveFeedClockHonesty({ unreadyReason: "LIVE_AS_OF_UNAVAILABLE", withheldRankedCount: 4 })).toMatch(
      /not Item 9 calibration/i,
    );
  });

  it("does not claim live freshness for honesty-source evaluations", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      data_quality: {
        status: "GOOD",
        freshness: "UNAVAILABLE",
        source: "REPLAY",
        freshness_evaluation: {
          status: "NOT_APPLICABLE",
          reason_code: "HONESTY_SOURCE_NOT_LIVE_FRESHNESS",
          source: "REPLAY",
          actionable: false,
        },
      },
    };
    const view = readOpportunityFreshnessView(row);
    expect(view.operatorAnswer).toMatch(/does not claim live freshness/i);
    expect(view.queueBackendLabel).toBe("NOT_APPLICABLE");
  });
});
