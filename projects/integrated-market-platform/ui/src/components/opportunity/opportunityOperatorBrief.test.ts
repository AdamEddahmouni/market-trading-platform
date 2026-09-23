import { describe, expect, it } from "vitest";
import {
  buildLiveWithheldOperatorBrief,
  buildOpportunityEvidenceNavigation,
  buildOpportunityOperatorBrief,
  buildOpportunityQueueScan,
  collectOpportunityConflicts,
  collectOpportunityInvalidationLines,
  collectOpportunityProviderLabels,
  collectOpportunityUnknowns,
  liveFeedClockHonesty,
  readOpportunityFreshnessView,
} from "./opportunityOperatorBrief";
import {
  fixtureOpportunityRowBase,
  fixtureOpportunityRowProviderLinkageWarned,
  fixtureOpportunityRowStaleEligible,
} from "./opportunityDetailFixtures";

describe("opportunityOperatorBrief", () => {
  it("renders backend provider_linkage_warnings phrases and does not invent wrong ticker", () => {
    const brief = buildOpportunityOperatorBrief(fixtureOpportunityRowProviderLinkageWarned);
    const byQuestion = Object.fromEntries(brief.map((row) => [row.question, row]));
    expect(byQuestion["Provider linkage?"]?.answer).toBe(
      "uncorroborated, contextual concern, low confidence",
    );
    expect(byQuestion["Provider linkage?"]?.honesty).toBe("OBSERVED");
    expect(JSON.stringify(brief).toLowerCase()).not.toContain("wrong ticker");

    const clean = buildOpportunityOperatorBrief(fixtureOpportunityRowBase);
    expect(clean.some((row) => row.question === "Provider linkage?")).toBe(false);
  });

  it("keeps the TEST-ONLY STALE-eligible fixture lagged, not FRESH", () => {
    const brief = buildOpportunityOperatorBrief(fixtureOpportunityRowStaleEligible);
    const freshness = brief.find((row) => row.question === "How fresh?");
    expect(freshness?.answer.toUpperCase()).toContain("STALE");
    expect(freshness?.answer.toUpperCase()).not.toMatch(/\bFRESH\b/);
  });

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
    expect(happened?.answer).not.toMatch(fixtureOpportunityRowBase.headline);
    expect(happened?.honesty).toBe("OBSERVED");
    expect(invalidate?.honesty).toBe("DERIVED");
    expect(invalidate?.answer).toMatch(/STALE/);
    expect(invalidate?.answer).toMatch(/expired/i);
  });

  it("does not label IMP headline language as an OBSERVED what-happened fact", () => {
    const brief = buildOpportunityOperatorBrief(fixtureOpportunityRowBase);
    const happened = brief.find((item) => item.question === "What happened?");
    const inference = brief.find((item) => item.question === "Inference vs observation?");
    expect(happened?.honesty).toBe("OBSERVED");
    expect(happened?.answer).not.toContain(fixtureOpportunityRowBase.headline);
    expect(inference?.answer).toMatch(/derived by IMP|Evidence class/i);
  });

  it("does not classify platform eligibility_state as a raw OBSERVED what-happened fact", () => {
    const brief = buildOpportunityOperatorBrief({
      ...fixtureOpportunityRowBase,
      eligibility_state: "INELIGIBLE",
      next_safe_action: "STOP",
    });
    const happened = brief.find((item) => item.question === "What happened?");
    const eligibility = brief.find((item) => item.question === "Eligibility evaluation?");
    expect(happened?.honesty).toBe("OBSERVED");
    expect(happened?.answer).not.toMatch(/eligibility/i);
    expect(happened?.answer).not.toMatch(/INELIGIBLE/i);
    expect(eligibility?.honesty).toBe("DERIVED");
    expect(eligibility?.answer).toMatch(/ineligible/i);
    expect(eligibility?.answer).toMatch(/evaluation\/gate state|not a raw market observation/i);
  });

  it("surfaces attached expiry as invalidation without inventing thesis criteria", () => {
    const brief = buildOpportunityOperatorBrief({
      ...fixtureOpportunityRowBase,
      expires_at: "2026-09-21T20:00:00Z",
    });
    const invalidate = brief.find((item) => item.question === "What would invalidate it?");
    expect(invalidate?.honesty).toBe("DERIVED");
    expect(invalidate?.answer).toMatch(/2026-09-21T20:00:00Z/);
    expect(invalidate?.answer).toMatch(/time-bounded/i);
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

  it("answers withheld-live operator questions without a ranked row", () => {
    expect(buildLiveWithheldOperatorBrief({ unreadyReason: "PROVIDER_WARMUP" })).toBeNull();
    const brief = buildLiveWithheldOperatorBrief({
      unreadyReason: "LIVE_AS_OF_UNAVAILABLE",
      withheldRankedCount: 3,
      bookHonesty: "RANKED_ROWS_WITHHELD_NO_LIVE_CLOCK",
    });
    expect(brief).not.toBeNull();
    const byQuestion = Object.fromEntries((brief ?? []).map((row) => [row.question, row]));
    expect(byQuestion["How fresh?"]?.answer).toMatch(/NOT_APPLICABLE/);
    expect(byQuestion["How fresh?"]?.answer).not.toMatch(/Fresh(?!ness)/);
    expect(byQuestion["How many ranked rows were withheld?"]?.answer).toMatch(/withheld 3 ranked row/);
    expect(byQuestion["How many ranked rows were withheld?"]?.honesty).toBe("OBSERVED");
    expect(byQuestion["What would invalidate it?"]?.answer).toMatch(/missing live receive clock/i);
    expect(byQuestion["What would invalidate it?"]?.answer).not.toMatch(/calibrat/i);
    expect(byQuestion["Why might action be refused?"]?.answer).toMatch(/Live execution stays OFF/i);
    expect(byQuestion["Why might action be refused?"]?.answer).toMatch(/never grants live execution/i);
    expect(JSON.stringify(brief)).not.toMatch(/3\/3/);
    expect(JSON.stringify(brief)).not.toMatch(/place a (live|real-money) /i);

    const unknownCount = buildLiveWithheldOperatorBrief({
      unreadyReason: "LIVE_AS_OF_UNAVAILABLE",
    });
    const withheld = unknownCount?.find((row) => row.question === "How many ranked rows were withheld?");
    expect(withheld?.honesty).toBe("UNKNOWN");
    expect(withheld?.answer).toMatch(/not attached as a positive count/i);
  });

  it("labels agent contradiction as inferred conflict, not an observation", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      metadata: { agent_enrichment: { status: "CONTRADICTED" } },
    };
    expect(collectOpportunityConflicts(row)).toEqual(["Agent enrichment status CONTRADICTED"]);
    const brief = buildOpportunityOperatorBrief(row);
    const inference = brief.find((item) => item.question === "Inference vs observation?");
    const conflicts = brief.find((item) => item.question === "Which facts conflict?");
    expect(inference?.honesty).toBe("INFERRED");
    expect(inference?.answer).toMatch(/interpretive/i);
    expect(inference?.answer).toMatch(/not a provider observation/i);
    expect(conflicts?.honesty).toBe("OBSERVED");
    expect(conflicts?.answer).toMatch(/CONTRADICTED/);
  });

  it("does not let grounded-fact disposition hide a contradicted agent as observation", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      metadata: {
        grounded_fact_extraction: { disposition: "EXTRACTED" },
        agent_enrichment: { status: "CONTRADICTED" },
      },
    };
    const brief = buildOpportunityOperatorBrief(row);
    const inference = brief.find((item) => item.question === "Inference vs observation?");
    expect(inference?.honesty).toBe("INFERRED");
    expect(inference?.answer).toMatch(/CONTRADICTED/);
    expect(collectOpportunityConflicts(row)).toEqual(["Agent enrichment status CONTRADICTED"]);
  });

  it("surfaces evidence navigation without inventing live feeds", () => {
    const nav = buildOpportunityEvidenceNavigation(fixtureOpportunityRowBase, {
      items: [{ kind: "forecast", id: "fc-1" }],
      lineage_refs: [{ provider: "REPLAY" }],
    });
    expect(nav.question).toBe("Where is the evidence?");
    expect(nav.answer).toMatch(/explain:opportunity:opp-progressive-1/);
    expect(nav.answer).toMatch(/1 evidence item/);
    expect(nav.answer).toMatch(/Research evidence/);
    expect(nav.answer).not.toMatch(/place a (live|real-money) /i);
    const brief = buildOpportunityOperatorBrief(fixtureOpportunityRowBase, {
      items: [{ kind: "forecast", id: "fc-1" }],
    });
    expect(brief.some((row) => row.question === "Where is the evidence?")).toBe(true);
  });

  it("refuses action when eligibility is UNAVAILABLE without upgrading attention", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      eligibility_state: "UNAVAILABLE",
      next_safe_action: "OPEN_WORKSPACE",
    };
    const scan = buildOpportunityQueueScan(row, null, { paperActions: true });
    const refusal = scan.find((item) => item.question === "Why might action be refused?");
    expect(refusal?.answer).toMatch(/UNAVAILABLE/);
    expect(collectOpportunityInvalidationLines(row).join(" ")).toMatch(/UNAVAILABLE/);
  });

  it("merges pipeline_clocks from evidence when row freshness_evaluation is missing", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      data_quality: { status: "UNAVAILABLE", source: "LIVE_OBSERVATIONAL" },
    };
    const evidence = {
      pipeline_clocks: {
        created_at_is_persist_minted: true,
        live_receive_clock: null,
        freshness_status: "NOT_APPLICABLE",
        freshness_reason_code: "LIVE_AS_OF_UNAVAILABLE",
      },
    };
    const view = readOpportunityFreshnessView(row, evidence);
    expect(view.reasonCode).toBe("LIVE_AS_OF_UNAVAILABLE");
    expect(view.operatorAnswer).toMatch(/persist-minted created_at/i);
  });

  it("scans observed vs inferred on the queue without a next-action CTA", () => {
    const scan = buildOpportunityQueueScan(fixtureOpportunityRowBase, null, {
      paperActions: true,
    });
    const byQuestion = Object.fromEntries(scan.map((row) => [row.question, row]));
    expect(byQuestion["What happened?"]?.answer).toMatch(/^BIYA/);
    expect(byQuestion["What happened?"]?.answer).not.toMatch(/continuation candidate/i);
    expect(byQuestion["What happened?"]?.answer).not.toMatch(/eligibility/i);
    expect(byQuestion["What happened?"]?.honesty).toBe("OBSERVED");
    expect(byQuestion["Eligibility evaluation?"]?.honesty).toBe("DERIVED");
    expect(byQuestion["Eligibility evaluation?"]?.answer).toMatch(/Eligible/i);
    expect(byQuestion["Inference vs observation?"]?.answer).toMatch(/continuation candidate/i);
    expect(byQuestion["Inference vs observation?"]?.answer).toMatch(/not a provider observation/i);
    expect(byQuestion["Inference vs observation?"]?.honesty).toBe("DERIVED");
    expect(byQuestion["Which providers support it?"]?.answer).toBe("REPLAY");
    expect(byQuestion["Which facts conflict?"]?.answer).toMatch(/^UNKNOWN/);
    expect(byQuestion["Why might action be refused?"]?.answer).toMatch(
      /next_safe_action OPEN_WORKSPACE is a research gate/i,
    );
    expect(byQuestion["Why might action be refused?"]?.answer).toMatch(/never grants live execution/i);
    expect(scan.some((row) => row.question === "What action is available?")).toBe(false);
    expect(JSON.stringify(scan)).not.toMatch(/calibrat/i);
    expect(JSON.stringify(scan)).not.toMatch(/Item 9/);
    expect(JSON.stringify(scan)).not.toMatch(/3\/3/);
    expect(JSON.stringify(scan)).not.toMatch(/place a (live|real-money) /i);
  });

  it("keeps LIVE_AS_OF_UNAVAILABLE as withheld-clock honesty on the queue scan", () => {
    const row = {
      ...fixtureOpportunityRowBase,
      data_quality: {
        status: "UNAVAILABLE",
        freshness: "NOT_APPLICABLE",
        source: "LIVE_OBSERVATIONAL",
        freshness_evaluation: {
          status: "NOT_APPLICABLE",
          reason_code: "LIVE_AS_OF_UNAVAILABLE",
          source: "LIVE_OBSERVATIONAL",
          actionable: false,
        },
      },
    };
    const scan = buildOpportunityQueueScan(row, null, { readOnly: true, paperActions: false });
    const freshness = scan.find((item) => item.question === "How fresh?");
    const refusal = scan.find((item) => item.question === "Why might action be refused?");
    expect(freshness?.answer).toMatch(/live receive clock unavailable/i);
    expect(freshness?.answer).not.toMatch(/Fresh(?!ness)/);
    expect(refusal?.answer).toMatch(/withheld-clock honesty, not a repair/i);
    expect(refusal?.answer).not.toMatch(/Open Control to repair/i);
    expect(JSON.stringify(scan)).not.toMatch(/calibrat/i);
    expect(JSON.stringify(scan)).not.toMatch(/DEGRADED/);
  });

  it("does not treat persist-minted created_at as a live receive clock", () => {
    const persistNs = 1_700_000_000_000_000_000;
    const row = {
      ...fixtureOpportunityRowBase,
      created_at_ns: persistNs,
      data_quality: {
        status: "UNAVAILABLE",
        freshness: "NOT_APPLICABLE",
        source: "LIVE_OBSERVATIONAL",
        freshness_evaluation: {
          status: "NOT_APPLICABLE",
          reason_code: "LIVE_AS_OF_UNAVAILABLE",
          source: "LIVE_OBSERVATIONAL",
          actionable: false,
        },
      },
    };
    const evidence = {
      created_at_ns: persistNs,
      pipeline_clocks: {
        persist_created_at_ns: persistNs,
        created_at_is_persist_minted: true,
        live_receive_clock: null,
        freshness_status: "NOT_APPLICABLE",
        freshness_reason_code: "LIVE_AS_OF_UNAVAILABLE",
      },
    };
    const view = readOpportunityFreshnessView(row, evidence);
    expect(view.asOfTimeNs).toBeNull();
    expect(view.status).toBe("NOT_APPLICABLE");
    expect(view.reasonCode).toBe("LIVE_AS_OF_UNAVAILABLE");
    expect(view.operatorAnswer).toMatch(/created_at is not a live clock/i);
    expect(collectOpportunityUnknowns(row, evidence)).toContain("live_receive_clock");
  });

  it("keeps STALE distinct from FRESH and does not upgrade a lagged row", () => {
    const stale = readOpportunityFreshnessView({
      ...fixtureOpportunityRowBase,
      data_quality: {
        status: "DEGRADED",
        freshness: "STALE",
        source: "MOOMOO",
        freshness_evaluation: {
          status: "STALE",
          reason_code: "STALE_AFTER_THRESHOLD",
          source: "OBSERVATIONAL",
          actionable: false,
          as_of_time_ns: 1_700_000_000_005_000_001,
          age_ns: 5_000_001,
        },
      },
    });
    const fresh = readOpportunityFreshnessView({
      ...fixtureOpportunityRowBase,
      data_quality: {
        status: "PASS",
        freshness: "FRESH",
        source: "MOOMOO",
        freshness_evaluation: {
          status: "FRESH",
          reason_code: "FRESH",
          source: "OBSERVATIONAL",
          actionable: true,
          as_of_time_ns: 1_700_000_000_001_000_000,
          age_ns: 1_000_000,
        },
      },
    });
    expect(stale.status).toBe("STALE");
    expect(stale.actionable).toBe(false);
    expect(fresh.status).toBe("FRESH");
    expect(fresh.actionable).toBe(true);
    expect(stale.status).not.toBe(fresh.status);
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
