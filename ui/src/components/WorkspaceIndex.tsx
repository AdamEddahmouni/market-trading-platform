import { Link, Navigate } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../api/client";
import { useContextQuery } from "../api/hooks";

export function WorkspaceIndex() {
  const contextQuery = useContextQuery();
  const context = contextQuery.data;
  const isLive = context?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  const active = context?.active_instrument ?? null;
  const scoped = context?.scope_symbols?.[0];
  const target = active || scoped || null;

  if (contextQuery.isLoading) {
    return <div className="app-loading">Loading workspace…</div>;
  }

  if (isLive) {
    if (target) {
      return <Navigate to={`/workspace/${target}`} replace />;
    }
    return (
      <section className="page">
        <h1>SELECT AN INSTRUMENT</h1>
        <p>Live observational mode does not default to a replay fixture. Search and subscribe from Explore.</p>
        <Link to="/explore">Go to Explore</Link>
      </section>
    );
  }

  return <Navigate to={`/workspace/${ADMITTED_REPLAY_INSTRUMENT_ID}`} replace />;
}
