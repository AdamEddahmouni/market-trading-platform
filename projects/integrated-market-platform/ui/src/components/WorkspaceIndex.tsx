import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../api/client";
import { workspacePathForInstrument } from "../api/instrumentIdentity";
import { queryKeys, useContextQuery } from "../api/hooks";
import { fetchJson } from "../api/fetchJson";
import { InvestigationList } from "../api/workspaceInvestigations";
import { ErrorState } from "./imp-ui/FeedbackStates";
import { LoadingState } from "./shared/LoadingState";
import { InstrumentSelectionEmpty } from "./shared/InstrumentSelectionEmpty";

export function WorkspaceIndex() {
  const contextQuery = useContextQuery();
  const context = contextQuery.data;
  const isLive = context?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  const active = context?.active_instrument ?? null;
  const scoped = context?.scope_symbols?.[0];
  const target = active || scoped || null;
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

  const defaultInstrument = isLive ? target : ADMITTED_REPLAY_INSTRUMENT_ID;
  return <section className="workspace-resume panel" aria-labelledby="workspace-resume-title">
    <h1 id="workspace-resume-title">Workspace</h1>
    <p>Resume an investigation or open an instrument workspace.</p>
    {defaultInstrument ? <Link to={workspacePathForInstrument(defaultInstrument)}>Open {defaultInstrument} workspace</Link> : <InstrumentSelectionEmpty mode="LIVE" />}
    <h2>Recent investigations</h2>
    {investigations.isLoading && <p role="status">Loading investigations…</p>}
    {investigations.isError && <p role="alert">Saved investigations could not load. <button type="button" onClick={() => void investigations.refetch()}>Retry</button></p>}
    {investigations.data?.investigations.length === 0 && <p>No saved investigations yet.</p>}
    {investigations.data && <ul className="workspace-resume-list">{investigations.data.investigations.slice(0, 10).map((item) => <li key={item.workspace_id}>
      <div><strong>{item.title}</strong> · {item.instrument_id} · {item.source_kind === "radar_attention" ? "Radar" : "Instrument"}{item.opportunity_id ? ` · Opportunity ${item.opportunity_id}` : ""}</div>
      <div>Updated {new Date(item.updated_at / 1_000_000).toLocaleString()} · {item.status}</div>
      <Link to={`${workspacePathForInstrument(item.instrument_id)}?work=${encodeURIComponent(item.workspace_id)}`}>Resume</Link>
    </li>)}</ul>}
  </section>;
}
