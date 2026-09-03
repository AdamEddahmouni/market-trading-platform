import { useSearchParams } from "react-router-dom";
import type { Mode } from "../mode-session/types";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../../api/client";
import {
  SqueezeWorkspaceObservability,
  squeezeModuleDescription,
} from "./SqueezeWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
  onOpenHistory?: (symbol: string) => void;
};

export function ModeSqueezeWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_REPLAY_INSTRUMENT_ID);
  const [searchParams] = useSearchParams();
  const dataMode = searchParams.get("data_mode") === "current" ? "current" : "frozen";
  const squeezeQuery = dataMode === "current" ? "?data_mode=current" : "";

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="squeeze"
      pageClassName="squeeze-workspace-page"
      moduleTitle="Short Squeeze Workspace"
      description={workspaceModuleModeDescription(
        squeezeModuleDescription(dataMode),
        mode,
        "squeeze",
      )}
      squeezeQuery={squeezeQuery}
    >
      <SqueezeWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
