import { useParams } from "react-router-dom";
import { useWorkspaceFuturesQuery } from "../../api/hooks";
import { ADMITTED_FUTURES_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { FuturesWorkspacePanel } from "./FuturesWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function FuturesWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_FUTURES_INSTRUMENT_ID;
  const futuresQuery = useWorkspaceFuturesQuery(instrumentId);

  return (
    <section className="page futures-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Futures Workspace</h1>
        <p>
          ES CME depth snapshots from the admitted synthetic fixture. Imbalance signals are
          depth-derived, not CFTC positioning.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="futures" />
      </header>
      <FuturesWorkspacePanel
        instrumentId={instrumentId}
        futures={futuresQuery.data ?? null}
        loading={futuresQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
