import type { Mode } from "../mode-session/types";
import { InstrumentSelectionEmpty } from "../shared/InstrumentSelectionEmpty";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  DISCLOSURE_MODULE_DESCRIPTION,
  DisclosureWorkspaceObservability,
} from "./DisclosureWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeDisclosureWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId();

  if (!instrumentId) {
    return <InstrumentSelectionEmpty mode={mode} laneLabel="Disclosure " />;
  }

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="disclosure"
      pageClassName="disclosure-workspace-page"
      moduleTitle="Disclosure Workspace"
      description={workspaceModuleModeDescription(
        DISCLOSURE_MODULE_DESCRIPTION,
        mode,
        "disclosure",
      )}
    >
      <DisclosureWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
