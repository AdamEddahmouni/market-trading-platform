import { Navigate } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../api/client";
import { useContextQuery } from "../api/hooks";
import { LoadingState } from "./shared/LoadingState";
import { InstrumentSelectionEmpty } from "./shared/InstrumentSelectionEmpty";

export function WorkspaceIndex() {
  const contextQuery = useContextQuery();
  const context = contextQuery.data;
  const isLive = context?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  const active = context?.active_instrument ?? null;
  const scoped = context?.scope_symbols?.[0];
  const target = active || scoped || null;

  if (contextQuery.isLoading) {
    return <LoadingState label="Loading workspace…" />;
  }

  if (isLive) {
    if (target) {
      return <Navigate to={`/workspace/${target}`} replace />;
    }
    return <InstrumentSelectionEmpty mode="LIVE" />;
  }

  return <Navigate to={`/workspace/${ADMITTED_REPLAY_INSTRUMENT_ID}`} replace />;
}
