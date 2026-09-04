import type { Mode } from "../mode-session/types";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  OptionsModuleHeaderExtra,
  OptionsWorkspaceObservability,
  optionsModuleDescription,
} from "./OptionsWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeOptionsWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_REPLAY_INSTRUMENT_ID);

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="options"
      pageClassName="options-workspace-page"
      moduleTitle="Options Workspace"
      description={workspaceModuleModeDescription(
        optionsModuleDescription(instrumentId),
        mode,
        "options",
      )}
      headerExtra={<OptionsModuleHeaderExtra instrumentId={instrumentId} />}
    >
      <OptionsWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
