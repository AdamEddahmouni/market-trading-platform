import { Link } from "react-router-dom";
import type { LiveCanarySnapshot } from "./liveCanarySnapshot";
import { liveSafetyAlerts, liveSafetySummary } from "./liveDashboardViewModel";

type Props = {
  snapshot?: LiveCanarySnapshot;
  state: "loading" | "ready" | "error";
};

export function LiveSafetySnapshot({ snapshot, state }: Props) {
  const alerts = liveSafetyAlerts(snapshot);

  return (
    <section className="live-panel live-safety-panel" aria-label="Operational safety">
      <header className="live-panel-heading">
        <div>
          <p className="live-eyebrow">Read-only safety state</p>
          <h2>Operational safety</h2>
        </div>
        <Link to="/live-canary">Open live canary</Link>
      </header>

      {state === "loading" ? <p role="status">Loading safety snapshot…</p> : null}
      {state === "error" ? <p className="unavailable">Safety snapshot unavailable.</p> : null}

      {state === "ready" && snapshot ? (
        <>
          <dl className="live-safety-grid">
            {liveSafetySummary(snapshot).map((metric) => (
              <div key={metric.id}>
                <dt>{metric.label}</dt>
                <dd>{metric.value}</dd>
              </div>
            ))}
          </dl>
          {alerts.length ? (
            <ul className="live-safety-alerts">
              {alerts.map((alert) => (
                <li key={`${alert.title}-${alert.detail}`} data-severity={alert.severity}>
                  <strong>{alert.title}</strong>
                  <span>{alert.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No active safety exceptions reported.</p>
          )}
          <p className="live-safety-hint">
            Reported state only. Execution controls remain unavailable in the Live workstation.
          </p>
        </>
      ) : null}
    </section>
  );
}
