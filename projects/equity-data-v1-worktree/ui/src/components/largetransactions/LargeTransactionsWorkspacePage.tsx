import { useParams } from "react-router-dom";
import { useWorkspaceLargeTransactionsQuery } from "../../api/hooks";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { LargeTransactionsWorkspacePanel } from "./LargeTransactionsWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function LargeTransactionsWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_ORDER_FLOW_INSTRUMENT_ID;
  const largeTransactionsQuery = useWorkspaceLargeTransactionsQuery(instrumentId);

  return (
    <section className="page large-transactions-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Large Transactions Workspace</h1>
        <p>
          Size-anomaly prints from the admitted NVDA fixture. Large prints are not directional
          intent.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="large-transactions" />
      </header>
      <LargeTransactionsWorkspacePanel
        instrumentId={instrumentId}
        largeTransactions={largeTransactionsQuery.data ?? null}
        loading={largeTransactionsQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
