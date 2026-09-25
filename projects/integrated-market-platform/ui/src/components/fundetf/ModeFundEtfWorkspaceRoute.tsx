import type { Mode } from "../mode-session/types";
import { InstrumentSelectionEmpty } from "../shared/InstrumentSelectionEmpty";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  FUND_ETF_MODULE_DESCRIPTION,
  FundEtfWorkspaceObservability,
} from "./FundEtfWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeFundEtfWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId();

  if (!instrumentId) {
    return <InstrumentSelectionEmpty mode={mode} laneLabel="Fund / ETF " />;
  }

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="fund-etf"
      pageClassName="fund-etf-workspace-page"
      moduleTitle="Fund / ETF Workspace"
      description={workspaceModuleModeDescription(FUND_ETF_MODULE_DESCRIPTION, mode, "fund-etf")}
    >
      <FundEtfWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
