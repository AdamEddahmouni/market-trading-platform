import { describe, expect, it } from "vitest";
import {
  buildOpportunityEpistemicLayers,
  hasNonFactualResearchOutput,
} from "./opportunityEpistemicLayers";
import {
  fixtureOpportunityEvidenceRefresh,
  fixtureOpportunityRowBase,
} from "./opportunityDetailFixtures";

describe("opportunityEpistemicLayers", () => {
  it("marks agent enrichment as non-factual model output", () => {
    const layers = buildOpportunityEpistemicLayers(
      {
        ...fixtureOpportunityRowBase,
        metadata: { agent_enrichment: { status: "PARTIAL", count: 2 } },
      },
      fixtureOpportunityEvidenceRefresh,
    );
    expect(layers.model_research.some((row) => row.nonFactual && /agent/i.test(row.label))).toBe(true);
    expect(hasNonFactualResearchOutput(layers)).toBe(true);
  });

  it("surfaces grounded fact disposition when metadata carries extraction", () => {
    const layers = buildOpportunityEpistemicLayers({
      ...fixtureOpportunityRowBase,
      metadata: {
        grounded_fact_extraction: {
          disposition: "SUPPORTED_ANSWER",
          answer: "42",
          grounded_fact_extraction_version: "imp.grounded-fact-extraction/1.0.0",
        },
      },
    });
    expect(layers.observed.some((row) => row.label === "Grounded fact disposition")).toBe(true);
  });

  it("does not treat an empty conflict list as a verified empty set", () => {
    const layers = buildOpportunityEpistemicLayers(fixtureOpportunityRowBase);
    expect(layers.contradiction[0]?.value).toMatch(/^UNKNOWN/);
    expect(layers.unknown.some((row) => /UNKNOWN|MISSING/.test(row.value))).toBe(true);
  });

  it("keeps STALE freshness in the derived layer instead of promoting it to FRESH", () => {
    const layers = buildOpportunityEpistemicLayers({
      ...fixtureOpportunityRowBase,
      data_quality: { status: "DEGRADED", freshness: "STALE", source: "FINVIZ_ELITE" },
    });
    expect(layers.derived.find((row) => row.label === "Data freshness")?.value).toMatch(/STALE/i);
    expect(JSON.stringify(layers.observed)).not.toMatch(/FRESH/);
  });

  it("surfaces attached contradictions without inventing a clean conflict set", () => {
    const layers = buildOpportunityEpistemicLayers({
      ...fixtureOpportunityRowBase,
      supersession_reason: "REPLACED_BY_NEWER",
      metadata: { agent_enrichment: { status: "CONTRADICTED", count: 1 } },
    });
    expect(layers.contradiction.map((row) => row.value).join(" ")).toMatch(/REPLACED_BY_NEWER/);
    expect(layers.contradiction.map((row) => row.value).join(" ")).toMatch(/CONTRADICTED/);
    expect(layers.model_research.some((row) => row.nonFactual)).toBe(true);
  });
});
