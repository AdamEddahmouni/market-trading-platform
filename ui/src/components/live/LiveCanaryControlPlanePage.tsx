import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";

type SnapshotPayload = {
  snapshot: {
    live_blocked: boolean;
    block_reasons: string[];
    execution_mode_label: string;
    program_state: string | null;
    session_state: string | null;
    broker: string | null;
    account_environment: string | null;
    account_fingerprint: string | null;
    broker_health: string;
    reconciliation_health: string;
    kill_switch_global: string;
    kill_switch_program: string;
    kill_switch_session: string;
    authorization_status: string | null;
    authorization_expires_at_ns: number | null;
    program_cap_remaining: Record<string, number>;
    incident_summary: Record<string, number>;
    unresolved_critical_incidents: string[];
    allowed_next_actions: string[];
    action_queue: Array<Record<string, unknown>>;
    snapshot_id: string;
    as_of_ns: number;
  };
  real_money_warning: string;
};

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function LiveCanaryControlPlanePage() {
  const { data, refetch, isLoading, error } = useQuery({
    queryKey: ["canary-snapshot"],
    queryFn: () => fetchJson<SnapshotPayload>("/canary/snapshot"),
    refetchInterval: 15000,
  });
  const [commandStatus, setCommandStatus] = useState<string | null>(null);
  const [authPreview, setAuthPreview] = useState<Record<string, unknown> | null>(null);

  const activateKillSwitch = useCallback(async () => {
    await postJson("/canary/command", {
      command: "activate_kill_switch",
      scope: "PROGRAM",
      reason: "OPERATOR_ACTIVATED",
      request_id: `ks-${Date.now()}`,
    });
    setCommandStatus("Kill switch activated — blocks new submissions; does not liquidate.");
    void refetch();
  }, [refetch]);

  const loadAuthorizationPreview = useCallback(async () => {
    const payload = await fetchJson<Record<string, unknown>>("/canary/authorization/preview");
    setAuthPreview(payload);
    setCommandStatus("Authorization preview loaded — review required before authorize.");
  }, []);

  if (isLoading) {
    return <p className="loading">Loading live canary control plane…</p>;
  }
  if (error || !data) {
    return <p className="error">Failed to load operator control plane.</p>;
  }

  const snap = data.snapshot;

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
          <dd>{snap.as_of_ns}</dd>
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
        <button type="button" onClick={() => void activateKillSwitch()}>
          Activate program kill switch
        </button>
        <p className="hint">Blocks new submissions. Does not automatically close existing positions.</p>
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
          <dd>{snap.program_cap_remaining.sessions ?? 0}</dd>
          <dt>Remaining orders</dt>
          <dd>{snap.program_cap_remaining.orders ?? 0}</dd>
          <dt>Remaining notional (minor)</dt>
          <dd>{snap.program_cap_remaining.notional_minor ?? 0}</dd>
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

      <section className="control-section">
        <h2>Action Queue</h2>
        {snap.action_queue.length === 0 ? (
          <p>No pending operator decisions.</p>
        ) : (
          <ul>
            {snap.action_queue.map((item, index) => (
              <li key={`${item.item_type}-${index}`}>
                {String(item.item_type)} — requires explicit review
              </li>
            ))}
          </ul>
        )}
        <p className="hint">No generic ENABLE LIVE button. Authorization and confirmation remain separate.</p>
      </section>

      <section className="control-section">
        <h2>Authorization Review</h2>
        <button type="button" onClick={() => void loadAuthorizationPreview()}>
          Prepare session authorization preview
        </button>
        {authPreview?.authorization_review ? (
          <pre className="review-panel">{JSON.stringify(authPreview.authorization_review, null, 2)}</pre>
        ) : null}
      </section>

      {commandStatus ? <p className="command-status">{commandStatus}</p> : null}
    </div>
  );
}
