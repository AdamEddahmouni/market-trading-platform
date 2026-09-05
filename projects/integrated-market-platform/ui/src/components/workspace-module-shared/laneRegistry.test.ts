import { describe, expect, it } from "vitest";
import { LANE_MODULE_IDS, isKnownLaneModuleId, laneModuleLabel } from "../paper-now/paperOrderDraft";
import {
  EVIDENCE_LANE_TO_MODULE_ID,
  MODULES_WITHOUT_EVIDENCE_LANE,
} from "../paper-workspace/paperDecisionSemantics";
import {
  WORKSPACE_LANE_LABELS,
  WORKSPACE_LANE_MODULE_IDS,
  WORKSPACE_LANE_REGISTRY,
  workspaceLanePath,
} from "./laneRegistry";

const REGISTRY_LANE_IDS = WORKSPACE_LANE_REGISTRY.filter((entry) => entry.id !== "overview").map(
  (entry) => entry.id,
);

describe("canonical lane-module registry", () => {
  it("keeps the workspace overview page separate from lane modules", () => {
    expect(WORKSPACE_LANE_REGISTRY.some((entry) => entry.id === "overview")).toBe(true);
    expect(WORKSPACE_LANE_MODULE_IDS).not.toContain("overview");
  });

  it("exposes exactly the lane modules from the single registry (no duplication)", () => {
    expect([...WORKSPACE_LANE_MODULE_IDS]).toEqual(REGISTRY_LANE_IDS);
    expect([...WORKSPACE_LANE_MODULE_IDS].sort()).toEqual([...LANE_MODULE_IDS].sort());
    expect(new Set(WORKSPACE_LANE_MODULE_IDS).size).toBe(WORKSPACE_LANE_MODULE_IDS.length);
  });

  it("derives a display label for every lane module", () => {
    for (const moduleId of WORKSPACE_LANE_MODULE_IDS) {
      expect(WORKSPACE_LANE_LABELS[moduleId]).toBeTruthy();
      expect(laneModuleLabel(moduleId)).toBe(WORKSPACE_LANE_LABELS[moduleId]);
    }
  });

  it("recognizes every canonical module id and rejects overview and unknown ids as lanes", () => {
    for (const moduleId of WORKSPACE_LANE_MODULE_IDS) {
      expect(isKnownLaneModuleId(moduleId)).toBe(true);
    }
    expect(isKnownLaneModuleId("overview")).toBe(false);
    expect(isKnownLaneModuleId("not-a-lane")).toBe(false);
  });

  it("maps only canonical lane modules from evidence lanes", () => {
    for (const moduleId of Object.values(EVIDENCE_LANE_TO_MODULE_ID)) {
      expect(WORKSPACE_LANE_MODULE_IDS).toContain(moduleId);
    }
  });

  it("keeps evidence-mapped and unmapped modules disjoint and exhaustive over the registry", () => {
    const mapped = new Set(Object.values(EVIDENCE_LANE_TO_MODULE_ID));
    const without = new Set(MODULES_WITHOUT_EVIDENCE_LANE);
    for (const moduleId of WORKSPACE_LANE_MODULE_IDS) {
      const isMapped = mapped.has(moduleId);
      const isWithout = without.has(moduleId);
      expect(isMapped || isWithout).toBe(true);
      expect(isMapped && isWithout).toBe(false);
    }
  });

  it("routes every lane module through workspaceLanePath", () => {
    for (const moduleId of WORKSPACE_LANE_MODULE_IDS) {
      expect(workspaceLanePath("BIYA", moduleId)).toBe(`/workspace/BIYA/${moduleId}`);
    }
  });
});
