import type { ReactNode } from "react";
import type { Mode } from "../mode-session/types";
import type { WorkspaceLaneModuleId } from "./laneRegistry";
import { buildLaneModeContent } from "./buildLaneModeContent";
import { LaneModeContextPanel } from "./LaneModeContextPanel";
import type { BuildLaneModeContentArgs, LaneQueryState } from "./laneModeContentTypes";
import { LiveLaneOperationalStrip } from "./LiveLaneOperationalStrip";

type Props = {
  mode: Mode;
  moduleId: WorkspaceLaneModuleId;
  instrumentId: string;
  queryState: LaneQueryState;
  data: unknown;
  dataMode?: "frozen" | "current";
  children: ReactNode;
};

export function ModeAwareWorkspaceLane({
  mode,
  moduleId,
  instrumentId,
  queryState,
  data,
  dataMode,
  children,
}: Props) {
  const contentArgs: BuildLaneModeContentArgs = {
    mode,
    moduleId,
    instrumentId,
    queryState,
    data,
    dataMode,
  };
  const content = buildLaneModeContent(contentArgs);

  return (
    <div className="workspace-lane-stack">
      <LaneModeContextPanel
        mode={mode}
        moduleId={moduleId}
        instrumentId={instrumentId}
        queryState={queryState}
        content={content}
      />
      {mode === "LIVE" ? <LiveLaneOperationalStrip laneId={moduleId} /> : null}
      <div className="workspace-lane-evidence">{children}</div>
    </div>
  );
}
