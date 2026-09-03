import type { WorkspaceEvidenceResponse } from "../../api/schemas";
import type { WorkspaceModuleId } from "../WorkspaceModuleNav";
import {
  buildEvidenceLaneBullet,
  buildModuleDataGapBullets,
  type DecisionBullet,
} from "./paperDecisionSemantics";

export type EvidenceQueryPhase = "loading" | "error" | "empty" | "ready";

export type PaperDecisionSnapshot = {
  supports: DecisionBullet[];
  contradicts: DecisionBullet[];
  unclear: DecisionBullet[];
  dataGaps: DecisionBullet[];
  overallInsufficient: boolean;
  originLane: WorkspaceModuleId | null;
  phase: EvidenceQueryPhase;
  phaseMessage?: string;
};

function bucketBullet(snapshot: PaperDecisionSnapshot, bullet: DecisionBullet) {
  if (bullet.hint === "supports") snapshot.supports.push(bullet);
  else if (bullet.hint === "contradicts") snapshot.contradicts.push(bullet);
  else if (bullet.hint === "insufficient") snapshot.dataGaps.push(bullet);
  else snapshot.unclear.push(bullet);
}

export function buildPaperDecisionSnapshot(
  evidence: WorkspaceEvidenceResponse | undefined,
  phase: EvidenceQueryPhase,
  originModuleId: WorkspaceModuleId | null,
  phaseMessage?: string,
): PaperDecisionSnapshot {
  const snapshot: PaperDecisionSnapshot = {
    supports: [],
    contradicts: [],
    unclear: [],
    dataGaps: [],
    overallInsufficient: false,
    originLane: originModuleId,
    phase,
    phaseMessage,
  };

  if (phase !== "ready" || !evidence) {
    snapshot.overallInsufficient = phase !== "ready";
    if (phase === "empty") {
      snapshot.dataGaps.push({
        lane: "Workspace evidence",
        moduleId: null,
        text: "No workspace evidence returned for this instrument.",
        hint: "insufficient",
        isOrigin: false,
        role: "context",
      });
    }
    return snapshot;
  }

  for (const lane of evidence.lanes) {
    bucketBullet(snapshot, buildEvidenceLaneBullet(lane, originModuleId));
  }

  for (const gap of buildModuleDataGapBullets()) {
    if (!originModuleId || gap.moduleId !== originModuleId) {
      snapshot.dataGaps.push(gap);
    }
  }

  const directionalCount = snapshot.supports.length + snapshot.contradicts.length;
  snapshot.overallInsufficient = directionalCount === 0;

  return snapshot;
}
