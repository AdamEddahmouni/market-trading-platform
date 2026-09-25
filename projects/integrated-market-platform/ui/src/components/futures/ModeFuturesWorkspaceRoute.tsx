import type { Mode } from "../mode-session/types";
import { InstrumentSelectionEmpty } from "../shared/InstrumentSelectionEmpty";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  FUTURES_MODULE_DESCRIPTION,
  FuturesWorkspaceObservability,
} from "./FuturesWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeFuturesWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId();

  if (!instrumentId) {
    return <InstrumentSelectionEmpty mode={mode} laneLabel="Futures " />;
  }

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="futures"
      pageClassName="futures-workspace-page"
      moduleTitle="Futures Workspace"
      description={workspaceModuleModeDescription(FUTURES_MODULE_DESCRIPTION, mode, "futures")}
    >
      <FuturesWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
