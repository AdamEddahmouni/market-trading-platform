import { useWorkspaceOrderBookQuery } from "../../api/hooks";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { OrderBookWorkspacePanel } from "./OrderBookWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OrderBookWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_ORDER_FLOW_INSTRUMENT_ID);
  const orderBookQuery = useWorkspaceOrderBookQuery(instrumentId);
  const queryState = deriveLaneQueryState(orderBookQuery, "order-book");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="order-book"
      instrumentId={instrumentId}
      queryState={queryState}
      data={orderBookQuery.data}
    >
      <OrderBookWorkspacePanel
        instrumentId={instrumentId}
        orderBook={orderBookQuery.data ?? null}
        loading={orderBookQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const ORDER_BOOK_MODULE_DESCRIPTION =
  "Visible liquidity snapshots from the admitted NVDA fixture. Depth imbalance is not participant intent.";
