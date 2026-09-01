import { useQuery } from "@tanstack/react-query";
import { useLiveCanarySnapshotQuery } from "../../api/hooks";
import type { Mode } from "../mode-session/types";
import { LoadingState } from "../shared/LoadingState";

type ReliabilityPayload = {
  observability_state: string;
  as_of_ns: number;
  health_matrix: {
    entries: Array<{
      component: string;
      state: string;
      freshness_ns: number | null;
      blocking_live: boolean;
      current_issue: string | null;
    }>;
    blocking_dependencies: string[];
  };
  slo_summary: {
    overall_status: string;
    objectives: Array<{ objective_id: string; status: string }>;
  };
  persistence_health: { disposition: string; blocking_live: boolean };
  backup_status: { integrity_status: string; last_backup_id: string };
  alert_delivery_configured: boolean;
};

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

type Props = {
  mode: Mode;
};

export function LiveCanaryControlPlanePage({ mode }: Props) {
  const { data: snap, isLoading, error } = useLiveCanarySnapshotQuery("canary-plane");
  const { data: reliability } = useQuery({
    queryKey: ["canary-reliability"],
    queryFn: () => fetchJson<ReliabilityPayload>("/canary/reliability"),
    refetchInterval: 15000,
  });
  if (isLoading) {
    return <LoadingState label="Loading live canary control plane…" />;
  }
  if (error || !snap) {
    return <p className="error">Failed to load operator control plane.</p>;
  }

  const programCapRemaining = snap.program_cap_remaining ?? {};
  const actionQueue = (snap as { action_queue?: Array<Record<string, unknown>> }).action_queue ?? [];

  return (
    <div className="live-canary-control-plane" data-testid="live-canary-control-plane">
      <header className="live-safety-header" role="banner">
        <div className="live-banner-critical">
          <strong>LIVE CANARY — REAL MONEY — HUMAN CONFIRMATION REQUIRED</strong>
        </div>
        <div className="live-mode-row">
          <span className="mode-label">EXECUTION MODE:</span>
          <strong className="mode-live">{snap.execution_mode_label}</strong>
          <span className="mode-separator">|</span>
          <span className="mode-label">PAPER TERMINAL:</span>
          <strong className="mode-paper">PAPER — INTERNAL SIMULATION ONLY</strong>
        </div>
        <p className="live-observability-boundary">
          {mode} workstation · Read-only operational observability
        </p>
      </header>

      <section className="control-section">
        <h2>Safety State</h2>
        <p>
          Live blocked: <strong>{snap.live_blocked ? "YES" : "NO"}</strong>
        </p>
        {snap.block_reasons.length > 0 ? (
          <ul>
            {snap.block_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
        <dl className="status-grid">
          <dt>Broker</dt>
          <dd>{snap.broker ?? "—"}</dd>
          <dt>Environment</dt>
          <dd>{snap.account_environment ?? "—"}</dd>
          <dt>Account fingerprint</dt>
          <dd>{snap.account_fingerprint ?? "—"}</dd>
          <dt>Broker health</dt>
          <dd>{snap.broker_health}</dd>
          <dt>Reconciliation</dt>
          <dd>{snap.reconciliation_health}</dd>
          <dt>As of</dt>
          <dd>{snap.as_of_ns ?? "—"}</dd>
        </dl>
      </section>

      <section className="control-section">
        <h2>Kill Switches</h2>
        <dl className="status-grid">
          <dt>Global</dt>
          <dd>{snap.kill_switch_global}</dd>
          <dt>Program</dt>
          <dd>{snap.kill_switch_program}</dd>
          <dt>Session</dt>
          <dd>{snap.kill_switch_session}</dd>
        </dl>
        <p className="hint">
          Reported state only. Execution controls are unavailable in the mode-aware workstation.
        </p>
      </section>

      <section className="control-section">
        <h2>Program / Session</h2>
        <dl className="status-grid">
          <dt>Program state</dt>
          <dd>{snap.program_state ?? "—"}</dd>
          <dt>Session state</dt>
          <dd>{snap.session_state ?? "—"}</dd>
          <dt>Authorization</dt>
          <dd>{snap.authorization_status ?? "NONE"}</dd>
          <dt>Remaining sessions</dt>
          <dd>{programCapRemaining.sessions ?? 0}</dd>
          <dt>Remaining orders</dt>
          <dd>{programCapRemaining.orders ?? 0}</dd>
          <dt>Remaining notional (minor)</dt>
          <dd>{programCapRemaining.notional_minor ?? 0}</dd>
        </dl>
      </section>

      <section className="control-section">
        <h2>Incidents</h2>
        <p>
          Open: {snap.incident_summary.open ?? 0} | Critical open:{" "}
          {snap.incident_summary.critical_open ?? 0}
        </p>
        {snap.unresolved_critical_incidents.length > 0 ? (
          <ul>
            {snap.unresolved_critical_incidents.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        ) : (
          <p>No unresolved critical incidents.</p>
        )}
      </section>

      <section className="control-section" data-testid="operational-reliability">
        <h2>Operational Reliability (BUILD 32)</h2>
        {reliability ? (
          <>
            <p>
              Observability: <strong>{reliability.observability_state}</strong> | SLO:{" "}
              <strong>{reliability.slo_summary.overall_status}</strong> | Persistence:{" "}
              <strong>{reliability.persistence_health.disposition}</strong>
            </p>
            <p>As of: {reliability.as_of_ns}</p>
            <p>Backup integrity: {reliability.backup_status.integrity_status}</p>
            <p>
              Alert delivery configured: {reliability.alert_delivery_configured ? "yes (console)" : "no"}
            </p>
            <table className="health-matrix-table">
              <thead>
                <tr>
                  <th>Component</th>
                  <th>State</th>
                  <th>Blocking live?</th>
                </tr>
              </thead>
              <tbody>
                {reliability.health_matrix.entries.map((entry) => (
                  <tr key={entry.component}>
                    <td>{entry.component}</td>
                    <td>{entry.state}</td>
                    <td>{entry.blocking_live ? "YES" : "NO"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="loading">Loading operational reliability state…</p>
        )}
        <p className="hint">
          Operational health does not authorize trading. Session authorization and per-order confirmation
          remain required.
        </p>
      </section>

      <section className="control-section">
        <h2>Action Queue</h2>
        {actionQueue.length === 0 ? (
          <p>No pending operator decisions.</p>
        ) : (
          <ul>
            {actionQueue.map((item, index) => (
              <li key={`${item.item_type}-${index}`}>
                {String(item.item_type)} — requires explicit review
              </li>
            ))}
          </ul>
        )}
        <p className="hint">No generic ENABLE LIVE button. Authorization and confirmation remain separate.</p>
      </section>

    </div>
  );
}
