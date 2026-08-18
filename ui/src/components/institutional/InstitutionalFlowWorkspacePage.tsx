import { useParams } from "react-router-dom";
import { useWorkspaceInstitutionalFlowQuery } from "../../api/hooks";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { InstitutionalFlowWorkspacePanel } from "./InstitutionalFlowWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function InstitutionalFlowWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? "BIYA";
  const flowQuery = useWorkspaceInstitutionalFlowQuery(instrumentId);

  return (
    <section className="page institutional-flow-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Institutional Flow</h1>
        <p>
          Eight separately inspectable whale evidence families per Swim With the Whales doctrine.
          Unknown aggressor remains unknown.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="institutional-flow" />
      </header>
      <InstitutionalFlowWorkspacePanel
        instrumentId={instrumentId}
        payload={flowQuery.data ?? null}
        loading={flowQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
