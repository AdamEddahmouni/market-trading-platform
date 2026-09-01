import type { Mode } from "../mode-session/types";
import { InstrumentSelectionEmpty } from "../shared/InstrumentSelectionEmpty";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  INSTITUTIONAL_FLOW_MODULE_DESCRIPTION,
  InstitutionalFlowWorkspaceObservability,
} from "./InstitutionalFlowWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeInstitutionalFlowWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId();

  if (!instrumentId) {
    return <InstrumentSelectionEmpty mode={mode} laneLabel="Institutional Flow " />;
  }

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="institutional-flow"
      pageClassName="institutional-flow-workspace-page"
      moduleTitle="Institutional Flow"
      description={workspaceModuleModeDescription(
        INSTITUTIONAL_FLOW_MODULE_DESCRIPTION,
        mode,
        "institutional-flow",
      )}
    >
      <InstitutionalFlowWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
