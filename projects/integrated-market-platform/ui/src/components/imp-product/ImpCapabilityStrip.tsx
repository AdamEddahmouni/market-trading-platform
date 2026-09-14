import type { CapabilityState } from "../../api/schemas";
import { presentCapabilityStates } from "./capabilityPresentation";

type Props = {
  capabilityStates: CapabilityState[];
  onOpenProviderMatrix?: () => void;
};

export function ImpCapabilityStrip({ capabilityStates, onOpenProviderMatrix }: Props) {
  if (!capabilityStates.length && !onOpenProviderMatrix) {
    return null;
  }

  const items = presentCapabilityStates(capabilityStates);

  return (
    <div className="imp-capability-strip" role="region" aria-label="Platform capabilities">
      <span className="imp-capability-strip-label">Capabilities</span>
      <ul className="imp-capability-strip-list">
        {items.map(({ capability, tone, label }) => (
          <li key={capability.capability_id} className={`imp-capability-chip imp-capability-${tone}`}>
            <span className="imp-capability-icon" aria-hidden="true">
              {tone === "ok" ? "●" : tone === "warn" ? "◐" : "○"}
            </span>
            <span className="imp-capability-name">{label}</span>
            <span className="imp-capability-state">{capability.state}</span>
            {capability.reason ? (
              <span className="imp-capability-reason">{capability.reason}</span>
            ) : null}
          </li>
        ))}
        {!items.length ? (
          <li className="imp-capability-chip imp-capability-muted">
            <span className="imp-capability-name">No capability rows on context</span>
          </li>
        ) : null}
      </ul>
      {onOpenProviderMatrix ? (
        <button type="button" className="imp-capability-matrix-trigger" onClick={onOpenProviderMatrix}>
          Provider matrix
        </button>
      ) : null}
    </div>
  );
}
