import { useParams } from "react-router-dom";
import { useWorkspaceCatalystQuery } from "../../api/hooks";
import { ADMITTED_CATALYST_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { CatalystWorkspacePanel } from "./CatalystWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function CatalystWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_CATALYST_INSTRUMENT_ID;
  const catalystQuery = useWorkspaceCatalystQuery(instrumentId);

  return (
    <section className="page catalyst-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Catalyst Workspace</h1>
        <p>
          Public catalyst events from the admitted synthetic fixture. Confidence and lean are
          inferred, not trade recommendations.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="catalyst" />
      </header>
      <CatalystWorkspacePanel
        instrumentId={instrumentId}
        catalyst={catalystQuery.data ?? null}
        loading={catalystQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
