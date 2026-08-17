import { Link, useParams } from "react-router-dom";
import { useWorkspaceOptionsQuery } from "../../api/hooks";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../../api/schemas";
import { OptionsWorkspacePanel } from "./OptionsWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OptionsWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_REPLAY_INSTRUMENT_ID;
  const optionsQuery = useWorkspaceOptionsQuery(instrumentId);

  return (
    <section className="page options-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Options Workspace</h1>
        <p>
          Unusual options activity from the admitted BIYA fixture. Unusual volume is not
          directional intent.
        </p>
        <nav className="workspace-module-nav" aria-label="Workspace modules">
          <Link to={`/workspace/${instrumentId}`}>Overview</Link>
          <Link to={`/workspace/${instrumentId}/squeeze`}>Short Squeeze</Link>
          <Link to={`/workspace/${instrumentId}/order-flow`}>Order Flow</Link>
          <Link className="active" to={`/workspace/${instrumentId}/options`}>Options</Link>
        </nav>
      </header>
      <OptionsWorkspacePanel
        instrumentId={instrumentId}
        options={optionsQuery.data ?? null}
        loading={optionsQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
