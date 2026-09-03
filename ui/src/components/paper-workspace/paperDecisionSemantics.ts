import type { WorkspaceEvidenceLane } from "../../api/schemas";
import type { PaperDecisionHint } from "../workspace-module-shared/laneModeContentTypes";
import type { LaneModuleId } from "../paper-now/paperOrderDraft";
import type { WorkspaceModuleId } from "../WorkspaceModuleNav";
import { laneModuleTitle } from "../workspace-module-shared/buildLaneModeContent";

export const EVIDENCE_LANE_TO_MODULE_ID: Record<string, WorkspaceModuleId> = {
  SHORT_SQUEEZE: "squeeze",
  ORDER_FLOW: "order-flow",
  MARKET_CONTEXT: "order-book",
  CATALYST: "catalyst",
  OPTIONS: "options",
  FUTURES: "futures",
  SHORT_INTELLIGENCE: "disclosure",
  WHALE_INSIDER: "institutional-flow",
};

export const MODULES_WITHOUT_EVIDENCE_LANE: LaneModuleId[] = ["large-transactions", "fund-etf"];

export function evidenceLaneToModuleId(lane: string): WorkspaceModuleId | null {
  return EVIDENCE_LANE_TO_MODULE_ID[lane] ?? null;
}

export function mapEvidenceDirectionToHint(direction: string | null | undefined): PaperDecisionHint {
  const normalized = (direction ?? "").toUpperCase();
  if (normalized === "POSITIVE") return "supports";
  if (normalized === "NEGATIVE") return "contradicts";
  if (normalized === "NEUTRAL") return "neutral";
  return "insufficient";
}

export function evidenceLaneQualityInsufficient(lane: WorkspaceEvidenceLane): boolean {
  const quality = (lane.quality ?? "").toUpperCase();
  if (!lane.summary || quality === "UNAVAILABLE" || quality === "MISSING") return true;
  if (lane.missing_evidence && lane.missing_evidence.length > 0 && !lane.direction) return true;
  return false;
}

export type DecisionBullet = {
  lane: string;
  moduleId: WorkspaceModuleId | null;
  text: string;
  hint: PaperDecisionHint;
  isOrigin: boolean;
  role: "primary" | "confirmation" | "context";
};

export function buildEvidenceLaneBullet(
  lane: WorkspaceEvidenceLane,
  originModuleId: WorkspaceModuleId | null,
): DecisionBullet {
  const moduleId = evidenceLaneToModuleId(lane.lane);
  const isOrigin = Boolean(moduleId && originModuleId && moduleId === originModuleId);
  const laneLabel = moduleId ? laneModuleTitle(moduleId) : lane.lane.replace(/_/g, " ");
  const hint = evidenceLaneQualityInsufficient(lane)
    ? "insufficient"
    : mapEvidenceDirectionToHint(lane.direction);

  const parts = [lane.summary];
  if (lane.relevance && lane.relevance !== "LOW") parts.push(`Relevance: ${lane.relevance}`);
  if (lane.freshness_label) parts.push(`Freshness: ${lane.freshness_label}`);
  if (lane.missing_evidence?.length) {
    parts.push(`Missing: ${lane.missing_evidence.join(", ")}`);
  }

  const role: DecisionBullet["role"] = isOrigin
    ? "primary"
    : hint === "supports" || hint === "contradicts"
      ? "confirmation"
      : "context";

  let text = parts.join(" · ");
  if (isOrigin) {
    text = `Primary handoff evidence — ${text}`;
  } else if (moduleId && originModuleId) {
    text = `${laneLabel} — ${hint === "supports" ? "confirmation" : hint === "contradicts" ? "contradiction" : "context"}: ${text}`;
  }

  return { lane: laneLabel, moduleId, text, hint, isOrigin, role };
}

export function buildModuleDataGapBullets(): DecisionBullet[] {
  return MODULES_WITHOUT_EVIDENCE_LANE.map((moduleId) => ({
    lane: laneModuleTitle(moduleId),
    moduleId,
    text: `${laneModuleTitle(moduleId)} — no workspace evidence lane available; review the lane module directly.`,
    hint: "insufficient" as const,
    isOrigin: false,
    role: "context" as const,
  }));
}
