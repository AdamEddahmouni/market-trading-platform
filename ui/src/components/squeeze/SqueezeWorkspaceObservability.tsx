import { useSearchParams } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../../api/client";
import { useWorkspaceSqueezeQuery } from "../../api/hooks";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { SqueezeWorkspacePanel } from "./SqueezeWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
  onOpenHistory?: (symbol: string) => void;
};

export function SqueezeWorkspaceObservability({ mode, onExplain, onInspect, onOpenHistory }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_REPLAY_INSTRUMENT_ID);
  const [searchParams] = useSearchParams();
  const dataMode = searchParams.get("data_mode") === "current" ? "current" : "frozen";
  const squeezeQuery = useWorkspaceSqueezeQuery(instrumentId, dataMode);
  const queryState = deriveLaneQueryState(squeezeQuery, "squeeze");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="squeeze"
      instrumentId={instrumentId}
      queryState={queryState}
      data={squeezeQuery.data}
      dataMode={dataMode}
    >
      <SqueezeWorkspacePanel
        instrumentId={instrumentId}
        squeeze={squeezeQuery.data ?? null}
        loading={squeezeQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenHistory={onOpenHistory}
      />
    </ModeAwareWorkspaceLane>
  );
}

export function squeezeModuleDescription(dataMode: "current" | "frozen") {
  const base =
    "Ignition state machine, evidence cards, and Phase 3A rules from the read-only donor bridge.";
  if (dataMode === "current") {
    return `${base} Viewing ephemeral scanner evidence (not the frozen research cohort).`;
  }
  return `${base} Viewing frozen research cohort evidence.`;
}
