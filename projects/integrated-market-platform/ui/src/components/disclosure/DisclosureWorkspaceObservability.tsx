import { useWorkspaceDisclosureQuery } from "../../api/hooks";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { DisclosureWorkspacePanel } from "./DisclosureWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function DisclosureWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId();
  const disclosureQuery = useWorkspaceDisclosureQuery(instrumentId);
  const queryState = deriveLaneQueryState(disclosureQuery, "disclosure");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="disclosure"
      instrumentId={instrumentId}
      queryState={queryState}
      data={disclosureQuery.data}
    >
      <DisclosureWorkspacePanel
        instrumentId={instrumentId}
        disclosure={disclosureQuery.data ?? null}
        loading={disclosureQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const DISCLOSURE_MODULE_DESCRIPTION =
  "Regulatory disclosure events from admitted SEC EDGAR fixture. Delayed filings remain delayed — not live positions.";
