import { useParams } from "react-router-dom";
import { useWorkspaceOrderBookQuery } from "../../api/hooks";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { OrderBookWorkspacePanel } from "./OrderBookWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OrderBookWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_ORDER_FLOW_INSTRUMENT_ID;
  const orderBookQuery = useWorkspaceOrderBookQuery(instrumentId);

  return (
    <section className="page order-book-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Order Book Workspace</h1>
        <p>
          Visible liquidity snapshots from the admitted NVDA fixture. Depth imbalance is not
          participant intent.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="order-book" />
      </header>
      <OrderBookWorkspacePanel
        instrumentId={instrumentId}
        orderBook={orderBookQuery.data ?? null}
        loading={orderBookQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
