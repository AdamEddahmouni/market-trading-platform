import { useParams } from "react-router-dom";
import { useWorkspaceFundEtfQuery } from "../../api/hooks";
import { ADMITTED_FUND_ETF_INSTRUMENT_ID } from "../../api/schemas";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { FundEtfWorkspacePanel } from "./FundEtfWorkspacePanel";

type Props = {
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function FundEtfWorkspacePage({ onExplain, onInspect }: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_FUND_ETF_INSTRUMENT_ID;
  const fundEtfQuery = useWorkspaceFundEtfQuery(instrumentId);

  return (
    <section className="page fund-etf-workspace-page">
      <header className="page-header">
        <h1>{instrumentId} — Fund / ETF Workspace</h1>
        <p>
          ETF flow proxies and cross-asset context from the admitted synthetic fixture. Not live
          fund-flow data.
        </p>
        <WorkspaceModuleNav instrumentId={instrumentId} active="fund-etf" />
      </header>
      <FundEtfWorkspacePanel
        instrumentId={instrumentId}
        fundEtf={fundEtfQuery.data ?? null}
        loading={fundEtfQuery.isLoading}
        onExplain={onExplain}
        onInspect={onInspect}
      />
    </section>
  );
}
