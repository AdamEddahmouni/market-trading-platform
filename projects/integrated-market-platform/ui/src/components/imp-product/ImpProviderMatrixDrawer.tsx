import { Link } from "react-router-dom";
import { useOperatorReadinessQuery } from "../../api/hooks";
import type { CapabilityState } from "../../api/schemas";
import { presentCapabilityStates } from "./capabilityPresentation";

type Props = {
  open: boolean;
  onClose: () => void;
  capabilityStates: CapabilityState[];
};

export function ImpProviderMatrixDrawer({ open, onClose, capabilityStates }: Props) {
  const readinessQuery = useOperatorReadinessQuery(open);
  if (!open) return null;
  const readinessState = readinessQuery.isLoading
    ? "loading"
    : readinessQuery.error
      ? "error"
      : "ready";
  const readiness = readinessQuery.data;
  const capabilities = presentCapabilityStates(capabilityStates);

  return (
    <aside className="drawer imp-provider-matrix-drawer" aria-label="Provider matrix">
      <header>
        <h2>Provider matrix</h2>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </header>
      <div className="drawer-body imp-provider-matrix-body">
        <p className="imp-section-eyebrow">Read-only aggregation</p>
        <p className="muted">
          Context capabilities, operator readiness, and discovery health — use linked surfaces for
          actions.
        </p>

        <section aria-labelledby="imp-matrix-capabilities-heading">
          <h3 id="imp-matrix-capabilities-heading">Context capabilities</h3>
          <ul className="imp-provider-matrix-list">
            {capabilities.map(({ capability, tone, label }) => (
              <li key={capability.capability_id} className={`imp-capability-chip imp-capability-${tone}`}>
                <span className="imp-capability-name">{label}</span>
                <span className="imp-capability-state">{capability.state}</span>
                {capability.reason ? <span className="imp-capability-reason">{capability.reason}</span> : null}
              </li>
            ))}
            {!capabilities.length ? <li className="muted">No capability_states on context.</li> : null}
          </ul>
        </section>

        <section aria-labelledby="imp-matrix-readiness-heading">
          <h3 id="imp-matrix-readiness-heading">Control readiness</h3>
          {readinessState === "loading" ? <p className="muted">Loading readiness…</p> : null}
          {readinessState === "error" ? (
            <p className="muted">Readiness unavailable — open Risk control for detail.</p>
          ) : null}
          {readiness ? (
            <>
              <p>
                Overall status: <strong>{readiness.status}</strong>
              </p>
              <ul className="imp-provider-matrix-list">
                {readiness.providers.map((provider) => (
                  <li key={provider.provider} className="imp-provider-matrix-row">
                    <strong>{provider.label ?? provider.provider}</strong>
                    <span>{provider.transport_state}</span>
                    <span className="muted">{provider.gate_state}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <p>
            <Link to="/control" onClick={onClose}>Open Risk control</Link>
          </p>
        </section>

        <section aria-labelledby="imp-matrix-links-heading">
          <h3 id="imp-matrix-links-heading">Related surfaces</h3>
          <ul className="imp-provider-matrix-links">
            <li>
              <Link to="/diagnostics/provider" onClick={onClose}>Provider diagnostics</Link>
            </li>
            <li>
              <Link to="/discover" onClick={onClose}>Opportunity Radar (discovery provider strip)</Link>
            </li>
          </ul>
        </section>
      </div>
    </aside>
  );
}
