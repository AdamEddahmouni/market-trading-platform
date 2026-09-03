import { useWorkspaceInstitutionalFlowQuery } from "../../api/hooks";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { InstitutionalFlowWorkspacePanel } from "./InstitutionalFlowWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function InstitutionalFlowWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId();
  const flowQuery = useWorkspaceInstitutionalFlowQuery(instrumentId);
  const queryState = deriveLaneQueryState(flowQuery, "institutional-flow");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="institutional-flow"
      instrumentId={instrumentId}
      queryState={queryState}
      data={flowQuery.data}
    >
      <InstitutionalFlowWorkspacePanel
        instrumentId={instrumentId}
        payload={flowQuery.data ?? null}
        loading={flowQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const INSTITUTIONAL_FLOW_MODULE_DESCRIPTION =
  "Eight separately inspectable whale evidence families per Swim With the Whales doctrine. Unknown aggressor remains unknown.";
