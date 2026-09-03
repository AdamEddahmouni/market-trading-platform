import type { PaperPersistedSourceContext } from "../paper/paperDecisionSourceSnapshot";

type Props = {
  persisted: PaperPersistedSourceContext;
  compact?: boolean;
};

export function PaperPersistedSourceContextPanel({ persisted, compact = false }: Props) {
  if (persisted.snapshotMismatch) {
    return (
      <div className="paper-source-context-panel">
        <p className="muted">Saved source context conflicts with decision correlation and is not shown.</p>
      </div>
    );
  }
  if (!persisted.snapshotAvailable) {
    if (compact) return null;
    return (
      <div className="paper-source-context-panel">
        <p className="muted">No saved source context for this order.</p>
      </div>
    );
  }

  return (
    <div className="paper-source-context-panel">
      <h4>{persisted.historicalLabel}</h4>
      <p className="muted paper-source-context-note">
        Historical source-time context — not current market or workspace evidence.
      </p>
      <dl className="metric-list paper-source-context-grid">
        {persisted.headline ? (
          <div>
            <dt>Source snapshot</dt>
            <dd>{persisted.headline}</dd>
          </div>
        ) : null}
        {persisted.tier !== null ? (
          <div>
            <dt>Tier</dt>
            <dd>{persisted.tier}</dd>
          </div>
        ) : null}
        {persisted.sourceTimeLabel && persisted.sourceTimeFieldLabel ? (
          <div>
            <dt>{persisted.sourceTimeFieldLabel}</dt>
            <dd>
              <time dateTime={String(persisted.sourceTime ?? "")}>{persisted.sourceTimeLabel}</time>
            </dd>
          </div>
        ) : null}
      </dl>
      {persisted.reasons.length > 0 ? (
        <div className="paper-source-context-reasons">
          <h5>Reasons</h5>
          <ul>
            {persisted.reasons.map((reason) => (
              <li key={reason.code}>
                <span className="paper-source-reason-code">{reason.code}</span> — {reason.label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
