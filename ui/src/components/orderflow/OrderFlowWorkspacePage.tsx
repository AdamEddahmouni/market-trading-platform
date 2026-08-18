import { useParams } from "react-router-dom";
import { useWorkspaceOrderFlowQuery } from "../../api/hooks";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { OrderFlowWorkspacePanel } from "./OrderFlowWorkspacePanel";

const ORDER_FLOW_SYMBOL = "NVDA";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OrderFlowWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ORDER_FLOW_SYMBOL;
  const orderFlowQuery = useWorkspaceOrderFlowQuery(instrumentId);

  return (
    <section className="page order-flow-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Order Flow Workspace</h1>
        <p>
          CVD series and signed-volume evidence from the admitted NVDA order-flow fixture.
          Unknown aggressor remains unknown.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="order-flow" />
      </header>
      <OrderFlowWorkspacePanel
        instrumentId={instrumentId}
        orderFlow={orderFlowQuery.data ?? null}
        loading={orderFlowQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
