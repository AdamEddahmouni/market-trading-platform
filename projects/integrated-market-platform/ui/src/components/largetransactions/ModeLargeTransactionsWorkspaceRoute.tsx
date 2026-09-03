import type { Mode } from "../mode-session/types";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  LARGE_TRANSACTIONS_MODULE_DESCRIPTION,
  LargeTransactionsWorkspaceObservability,
} from "./LargeTransactionsWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeLargeTransactionsWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_ORDER_FLOW_INSTRUMENT_ID);

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="large-transactions"
      pageClassName="large-transactions-workspace-page"
      moduleTitle="Large Transactions Workspace"
      description={workspaceModuleModeDescription(
        LARGE_TRANSACTIONS_MODULE_DESCRIPTION,
        mode,
        "large-transactions",
      )}
    >
      <LargeTransactionsWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
