import type { Mode } from "../mode-session/types";
import { ADMITTED_CATALYST_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  CATALYST_MODULE_DESCRIPTION,
  CatalystWorkspaceObservability,
} from "./CatalystWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeCatalystWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_CATALYST_INSTRUMENT_ID);

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="catalyst"
      pageClassName="catalyst-workspace-page"
      moduleTitle="Catalyst Workspace"
      description={workspaceModuleModeDescription(CATALYST_MODULE_DESCRIPTION, mode, "catalyst")}
    >
      <CatalystWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
