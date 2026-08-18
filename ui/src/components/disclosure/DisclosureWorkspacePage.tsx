import { useParams } from "react-router-dom";
import { useWorkspaceDisclosureQuery } from "../../api/hooks";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { DisclosureWorkspacePanel } from "./DisclosureWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function DisclosureWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? "BIYA";
  const disclosureQuery = useWorkspaceDisclosureQuery(instrumentId);

  return (
    <section className="page disclosure-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Disclosure Workspace</h1>
        <p>
          Regulatory disclosure events from admitted SEC EDGAR fixture. Delayed filings remain
          delayed — not live positions.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="disclosure" />
      </header>
      <DisclosureWorkspacePanel
        instrumentId={instrumentId}
        disclosure={disclosureQuery.data ?? null}
        loading={disclosureQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
