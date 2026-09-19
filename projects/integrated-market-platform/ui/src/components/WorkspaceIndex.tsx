import { Navigate } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../api/client";
import { workspacePathForInstrument } from "../api/instrumentIdentity";
import { useContextQuery } from "../api/hooks";
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

  if (isLive) {
    if (target) {
      return <Navigate to={workspacePathForInstrument(target)} replace />;
    }
    return <InstrumentSelectionEmpty mode="LIVE" />;
  }

  return <Navigate to={workspacePathForInstrument(ADMITTED_REPLAY_INSTRUMENT_ID)} replace />;
}
