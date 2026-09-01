import { useWorkspaceFundEtfQuery } from "../../api/hooks";
import { ADMITTED_FUND_ETF_INSTRUMENT_ID } from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import { deriveLaneQueryState } from "../workspace-module-shared/laneQueryState";
import { ModeAwareWorkspaceLane } from "../workspace-module-shared/ModeAwareWorkspaceLane";
import { useWorkspaceInstrumentId } from "../workspace-module-shared/useWorkspaceInstrumentId";
import { FundEtfWorkspacePanel } from "./FundEtfWorkspacePanel";

type Props = {
  mode: Mode;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function FundEtfWorkspaceObservability({ mode, onExplain, onInspect }: Props) {
  const instrumentId = useWorkspaceInstrumentId(ADMITTED_FUND_ETF_INSTRUMENT_ID);
  const fundEtfQuery = useWorkspaceFundEtfQuery(instrumentId);
  const queryState = deriveLaneQueryState(fundEtfQuery, "fund-etf");

  return (
    <ModeAwareWorkspaceLane
      mode={mode}
      moduleId="fund-etf"
      instrumentId={instrumentId}
      queryState={queryState}
      data={fundEtfQuery.data}
    >
      <FundEtfWorkspacePanel
        instrumentId={instrumentId}
        fundEtf={fundEtfQuery.data ?? null}
        loading={fundEtfQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </ModeAwareWorkspaceLane>
  );
}

export const FUND_ETF_MODULE_DESCRIPTION =
  "ETF flow proxies and cross-asset context from the admitted synthetic fixture. Not live fund-flow data.";
