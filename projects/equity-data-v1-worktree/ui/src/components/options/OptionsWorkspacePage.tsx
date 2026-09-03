import { Link, useParams } from "react-router-dom";
import { useWorkspaceOptionsQuery } from "../../api/hooks";
import {
  ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID,
  ADMITTED_REPLAY_INSTRUMENT_ID,
} from "../../api/schemas";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { OptionsWorkspacePanel } from "./OptionsWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OptionsWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_REPLAY_INSTRUMENT_ID;
  const optionsQuery = useWorkspaceOptionsQuery(instrumentId);
  const isWhaleDefault = instrumentId === ADMITTED_REPLAY_INSTRUMENT_ID;

  return (
    <section className="page options-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Options Workspace</h1>
        <p>
          {isWhaleDefault
            ? `Unusual options activity from the admitted ${ADMITTED_REPLAY_INSTRUMENT_ID} whale fixture. Cooperative O6–O9 + SHARED P4 research uses ${ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID}.`
            : "Cooperative options research snapshots (O6–O9) and cross-lane opportunity fusion (SHARED P4)."}
        </p>
        {isWhaleDefault ? (
          <p className="workspace-hint">
            <Link to={`/workspace/${ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID}/options`}>
              Open {ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID} cooperative research path
            </Link>
          </p>
        ) : null}
        <WorkspaceModuleNav instrumentId={instrumentId} active="options" />
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
