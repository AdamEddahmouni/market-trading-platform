import { useWorkspaceLargeTransactionsQuery } from "../../api/hooks";
import { ADMITTED_ORDER_FLOW_INSTRUMENT_ID } from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { LargeTransactionsWorkspacePanel } from "./LargeTransactionsWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function LargeTransactionsWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_ORDER_FLOW_INSTRUMENT_ID);
  const largeTransactionsQuery = useWorkspaceLargeTransactionsQuery(instrumentId);
  const queryState = deriveLaneQueryState(largeTransactionsQuery, "large-transactions");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="large-transactions"
      instrumentId={instrumentId}
      queryState={queryState}
      data={largeTransactionsQuery.data}
    >
      <LargeTransactionsWorkspacePanel
        instrumentId={instrumentId}
        largeTransactions={largeTransactionsQuery.data ?? null}
        loading={largeTransactionsQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const LARGE_TRANSACTIONS_MODULE_DESCRIPTION =
  "Size-anomaly prints from the admitted NVDA fixture. Large prints are not directional intent.";
