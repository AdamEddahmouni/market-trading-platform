import { useParams, useSearchParams } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../../api/client";
import { useWorkspaceSqueezeQuery } from "../../api/hooks";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { SqueezeWorkspacePanel } from "./SqueezeWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
  onOpenHistory?: (symbol: string) => void;
};

export function SqueezeWorkspacePage({ onExplain, onInspect, onOpenHistory }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const [searchParams] = useSearchParams();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_REPLAY_INSTRUMENT_ID;
  const dataMode = searchParams.get("data_mode") === "current" ? "current" : "frozen";
  const squeezeQuery = useWorkspaceSqueezeQuery(instrumentId, dataMode);

  return (
    <section className="page squeeze-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Short Squeeze Workspace</h1>
        <p>
          Ignition state machine, evidence cards, and Phase 3A rules from the read-only donor bridge.
          {dataMode === "current"
            ? " Viewing ephemeral scanner evidence (not the frozen research cohort)."
            : " Viewing frozen research cohort evidence."}
        </p>
        <WorkspaceModuleNav
          instrumentId={instrumentId}
          active="squeeze"
          squeezeQuery={dataMode === "current" ? "?data_mode=current" : ""}
        />
      </header>
      <SqueezeWorkspacePanel
        instrumentId={instrumentId}
        squeeze={squeezeQuery.data ?? null}
        loading={squeezeQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenHistory={onOpenHistory}
      />
    </section>
  );
}
