import type { Mode } from "../mode-session/types";
import type { WorkspaceLaneModuleId } from "./laneRegistry";

import type { LaneProvenance } from "./laneProvenance";

export type LaneQueryPhase = "loading" | "error" | "empty" | "ready";

export type LaneQueryState = {
  phase: LaneQueryPhase;
  message?: string;
  stale?: boolean;
  degraded?: boolean;
  provenance?: LaneProvenance;
};

export type LaneModeContentSection = {
  title: string;
  body: string;
  emphasis?: "info" | "warning" | "success" | "neutral";
  bullets?: string[];
};

export type PaperDecisionHint = "supports" | "contradicts" | "neutral" | "insufficient";

export type LaneModeContent = {
  headline: string;
  summary: string;
  sections: LaneModeContentSection[];
  decisionHint?: PaperDecisionHint;
  limitations?: string[];
  relatedLinks?: Array<{ label: string; to: string }>;
};

export type BuildLaneModeContentArgs = {
  mode: Mode;
  moduleId: WorkspaceLaneModuleId;
  instrumentId: string;
  queryState: LaneQueryState;
  data: unknown;
  dataMode?: "frozen" | "current";
};
