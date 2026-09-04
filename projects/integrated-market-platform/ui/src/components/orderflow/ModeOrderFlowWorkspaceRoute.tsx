import type { Mode } from "../mode-session/types";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleModeShell } from "../workspace-module-shared/WorkspaceModuleModeShell";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { workspaceModuleModeDescription } from "../workspace-module-shared/workspaceModuleModeDescription";
import {
  ORDER_FLOW_MODULE_DESCRIPTION,
  OrderFlowWorkspaceObservability,
} from "./OrderFlowWorkspaceObservability";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function ModeOrderFlowWorkspaceRoute({ mode, ...props }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_ORDER_FLOW_INSTRUMENT_ID);

  return (
    <WorkspaceModuleModeShell
      mode={mode}
      instrumentId={instrumentId}
      active="order-flow"
      pageClassName="order-flow-workspace-page"
      moduleTitle="Order Flow Workspace"
      description={workspaceModuleModeDescription(
        ORDER_FLOW_MODULE_DESCRIPTION,
        mode,
        "order-flow",
      )}
    >
      <OrderFlowWorkspaceObservability mode={mode} {...props} />
    </WorkspaceModuleModeShell>
  );
}
