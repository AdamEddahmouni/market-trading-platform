import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { workspacePathForInstrument } from "../api/instrumentIdentity";
import { queryKeys, useContextQuery } from "../api/hooks";
import { fetchJson } from "../api/fetchJson";
import { InvestigationList } from "../api/workspaceInvestigations";
import { ErrorState } from "./imp-ui/FeedbackStates";
import { LoadingState } from "./shared/LoadingState";

export function WorkspaceIndex() {
  const contextQuery = useContextQuery();
  const context = contextQuery.data;
  const investigations = useQuery({
    queryKey: queryKeys.investigations,
    queryFn: () => fetchJson("/operator/investigations", InvestigationList),
  });

  if (contextQuery.isLoading) {
    return <LoadingState label="Loading workspace…" />;
  }

  if (contextQuery.isError || !context) {
    return (
      <ErrorState
        title="Workspace context is unavailable."
        affects="The overview cannot choose an instrument until /context succeeds. Demo replay is not assumed."
        onRetry={() => {
          void contextQuery.refetch();
        }}
      />
    );
  }

  return <section className="workspace-resume" aria-labelledby="workspace-resume-title">
    <header className="workspace-resume-header">
      <div>
        <p className="imp-section-eyebrow">Your work</p>
        <h1 id="workspace-resume-title">Workspace</h1>
        <p>Resume an investigation, or find an instrument through Radar or search.</p>
      </div>
      <Link className="workspace-resume-primary" to="/radar">Explore Radar</Link>
    </header>
    <div className="workspace-resume-section-head">
      <h2>Recent investigations</h2>
      <Link to="/radar">Open Radar</Link>
    </div>
    {investigations.isLoading && <p role="status">Loading investigations…</p>}
    {investigations.isError && <p role="alert">Saved investigations could not load. <button type="button" onClick={() => void investigations.refetch()}>Retry</button></p>}
    {investigations.data?.investigations.length === 0 && <div className="workspace-resume-empty"><p>No saved investigations yet.</p><p>Select an opportunity in Radar to begin an investigation, or use search to open an instrument.</p></div>}
    {investigations.data && investigations.data.investigations.length > 0 && <ul className="workspace-resume-list">{investigations.data.investigations.slice(0, 10).map((item) => <li key={item.workspace_id}>
      <div className="workspace-resume-item-main"><strong>{item.title}</strong> · {item.instrument_id} · {item.source_kind === "radar_attention" ? "Radar" : "Instrument"}{item.opportunity_id ? ` · Opportunity ${item.opportunity_id}` : ""}</div>
      <div className="workspace-resume-item-meta">Updated {new Date(item.updated_at / 1_000_000).toLocaleString()} · {item.status}</div>
      <Link to={`${workspacePathForInstrument(item.instrument_id)}?work=${encodeURIComponent(item.workspace_id)}`}>Resume</Link>
    </li>)}</ul>}
  </section>;
}
