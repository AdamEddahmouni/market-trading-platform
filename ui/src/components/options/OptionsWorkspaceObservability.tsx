import { Link } from "react-router-dom";
import { useWorkspaceOptionsQuery } from "../../api/hooks";
import {
  ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID,
  ADMITTED_REPLAY_INSTRUMENT_ID,
} from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { OptionsWorkspacePanel } from "./OptionsWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OptionsWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_REPLAY_INSTRUMENT_ID);
  const optionsQuery = useWorkspaceOptionsQuery(instrumentId);
  const queryState = deriveLaneQueryState(optionsQuery, "options");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="options"
      instrumentId={instrumentId}
      queryState={queryState}
      data={optionsQuery.data}
    >
      <OptionsWorkspacePanel
        instrumentId={instrumentId}
        options={optionsQuery.data ?? null}
        loading={optionsQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export function optionsModuleDescription(instrumentId: string) {
  if (instrumentId === ADMITTED_REPLAY_INSTRUMENT_ID) {
    return `Unusual options activity from the admitted ${ADMITTED_REPLAY_INSTRUMENT_ID} whale fixture. Cooperative O6–O9 + SHARED P4 research uses ${ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID}.`;
  }
  return "Cooperative options research snapshots (O6–O9) and cross-lane opportunity fusion (SHARED P4).";
}

export function OptionsModuleHeaderExtra({ instrumentId }: { instrumentId: string }) {
  if (instrumentId !== ADMITTED_REPLAY_INSTRUMENT_ID) return null;
  return (
    <p className="workspace-hint">
      <Link to={`/workspace/${ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID}/options`}>
        Open {ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID} cooperative research path
      </Link>
    </p>
  );
}
