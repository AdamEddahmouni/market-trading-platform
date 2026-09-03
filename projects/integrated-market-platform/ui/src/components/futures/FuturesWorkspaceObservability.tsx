import { useWorkspaceFuturesQuery } from "../../api/hooks";
import { ADMITTED_FUTURES_INSTRUMENT_ID } from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { FuturesWorkspacePanel } from "./FuturesWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function FuturesWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_FUTURES_INSTRUMENT_ID);
  const futuresQuery = useWorkspaceFuturesQuery(instrumentId);
  const queryState = deriveLaneQueryState(futuresQuery, "futures");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="futures"
      instrumentId={instrumentId}
      queryState={queryState}
      data={futuresQuery.data}
    >
      <FuturesWorkspacePanel
        instrumentId={instrumentId}
        futures={futuresQuery.data ?? null}
        loading={futuresQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const FUTURES_MODULE_DESCRIPTION =
  "ES CME depth snapshots from the admitted synthetic fixture. Imbalance signals are depth-derived, not CFTC positioning.";
