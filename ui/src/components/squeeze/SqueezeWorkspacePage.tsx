import { Link, useParams } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../../api/client";
import { useWorkspaceSqueezeQuery } from "../../api/hooks";
import { SqueezeWorkspacePanel } from "./SqueezeWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
  onOpenHistory?: (symbol: string) => void;
};

export function SqueezeWorkspacePage({ onExplain, onInspect, onOpenHistory }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_REPLAY_INSTRUMENT_ID;
  const squeezeQuery = useWorkspaceSqueezeQuery(instrumentId);

  return (
    <section className="page squeeze-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Short Squeeze Workspace</h1>
        <p>
          Ignition state machine, evidence cards, and Phase 3A rules from the read-only donor bridge.
          No opaque squeeze score.
        </p>
        <nav className="workspace-module-nav" aria-label="Workspace modules">
          <Link to={`/workspace/${instrumentId}`}>Overview</Link>
          <Link className="active" to={`/workspace/${instrumentId}/squeeze`}>Short Squeeze</Link>
        </nav>
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
