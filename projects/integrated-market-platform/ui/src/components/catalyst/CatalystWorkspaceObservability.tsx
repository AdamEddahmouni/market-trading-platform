import { useWorkspaceCatalystQuery } from "../../api/hooks";
import { ADMITTED_CATALYST_INSTRUMENT_ID } from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { CatalystWorkspacePanel } from "./CatalystWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function CatalystWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_CATALYST_INSTRUMENT_ID);
  const catalystQuery = useWorkspaceCatalystQuery(instrumentId);
  const queryState = deriveLaneQueryState(catalystQuery, "catalyst");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="catalyst"
      instrumentId={instrumentId}
      queryState={queryState}
      data={catalystQuery.data}
    >
      <CatalystWorkspacePanel
        instrumentId={instrumentId}
        catalyst={catalystQuery.data ?? null}
        loading={catalystQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const CATALYST_MODULE_DESCRIPTION =
  "Public catalyst events from the admitted synthetic fixture. Confidence and lean are inferred, not trade recommendations.";
