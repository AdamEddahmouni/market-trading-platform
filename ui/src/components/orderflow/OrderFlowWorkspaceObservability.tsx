import { useWorkspaceOrderFlowQuery } from "../../api/hooks";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { OrderFlowWorkspacePanel } from "./OrderFlowWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OrderFlowWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_ORDER_FLOW_INSTRUMENT_ID);
  const orderFlowQuery = useWorkspaceOrderFlowQuery(instrumentId);
  const queryState = deriveLaneQueryState(orderFlowQuery, "order-flow");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="order-flow"
      instrumentId={instrumentId}
      queryState={queryState}
      data={orderFlowQuery.data}
    >
      <OrderFlowWorkspacePanel
        instrumentId={instrumentId}
        orderFlow={orderFlowQuery.data ?? null}
        loading={orderFlowQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const ORDER_FLOW_MODULE_DESCRIPTION =
  "CVD series and signed-volume evidence from the admitted NVDA order-flow fixture. Unknown aggressor remains unknown.";
