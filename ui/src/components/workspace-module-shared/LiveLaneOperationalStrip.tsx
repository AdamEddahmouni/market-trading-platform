import { Link } from "react-router-dom";
import { useLiveCanarySnapshotQuery, useProviderHealthQuery } from "../../api/hooks";
import { formatPaperSourceTimeLabel } from "../paper/paperSourceTimestamp";
import { LoadingState } from "../shared/LoadingState";

type Props = {
  laneId: string;
};

export function LiveLaneOperationalStrip({ laneId }: Props) {
  const providerQuery = useProviderHealthQuery();
  const canaryQuery = useLiveCanarySnapshotQuery(laneId, true);

  const provider = providerQuery.data;
  const canary = canaryQuery.data;
  const providerReady = provider?.available === true;
  const canaryReady = canaryQuery.isSuccess && canary;
  const snapshotTime =
    canary?.as_of_ns !== undefined ? formatPaperSourceTimeLabel(canary.as_of_ns) : null;

  if (canaryQuery.isLoading || providerQuery.isLoading) {
    return (
      <aside className="lane-live-operational-strip loading" role="status" aria-label="Live operational context">
        <LoadingState label="Loading live operational context…" />
      </aside>
    );
  }

  if (canaryQuery.isError && providerQuery.isError) {
    return (
      <aside className="lane-live-operational-strip degraded" aria-label="Live operational context unavailable">
        <strong>Operational context unavailable.</strong>
        <p>Provider health and canary snapshot could not be loaded for lane {laneId}.</p>
        <Link to="/live-canary">Open live canary</Link>
      </aside>
    );
  }

  return (
    <aside className="lane-live-operational-strip" aria-label={`Live operational context for ${laneId}`}>
      <strong>Live operational context</strong>
      <ul>
        <li>
          Provider:{" "}
          {providerReady
            ? String(provider.lifecycle?.connection_state ?? "CONNECTED")
            : provider?.reason ?? "UNAVAILABLE"}
        </li>
        {canaryReady ? (
          <>
            <li>
              Broker health: {canary.broker_health} · Reconciliation: {canary.reconciliation_health}
            </li>
            <li>
              Program {canary.program_state ?? "UNKNOWN"} · Session {canary.session_state ?? "UNKNOWN"}
            </li>
            {snapshotTime ? <li>Broker snapshot as of: {snapshotTime}</li> : <li>Broker snapshot time unavailable</li>}
            {canary.live_blocked ? (
              <li className="lane-live-blocked">Live blocked: {(canary.block_reasons ?? []).join(", ") || "see canary"}</li>
            ) : null}
          </>
        ) : (
          <li>Canary snapshot unavailable — treat lane evidence as lower confidence.</li>
        )}
      </ul>
      <Link to="/live-canary">Open live canary</Link>
      <Link to="/diagnostics/provider">Provider diagnostics</Link>
    </aside>
  );
}
