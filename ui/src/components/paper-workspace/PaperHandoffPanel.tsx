import type { PaperHandoffModel } from "./buildPaperHandoffModel";

type Props = {
  handoff: PaperHandoffModel;
  evidenceAsOf?: string | null;
};

function handoffHeading(handoff: PaperHandoffModel): string {
  if (handoff.isMalformed) {
    return handoff.isUnknownLane ? "Unknown lane handoff" : "Unknown provenance";
  }
  if (handoff.kind === "unknown") return "Unknown provenance";
  if (handoff.kind === "lane" && handoff.isUnknownLane) return "Unknown lane handoff";
  if (handoff.kind === "lane") {
    return `Handoff from ${handoff.sourceTitle || "workspace lane"}`;
  }
  if (handoff.kind === "attention") {
    return "Attention handoff";
  }
  return "Handoff";
}

export function PaperHandoffPanel({ handoff, evidenceAsOf }: Props) {
  if (!handoff.hasHandoff) return null;

  return (
    <section
      className={`panel paper-cockpit-panel paper-handoff-panel handoff-${handoff.kind}`}
      aria-labelledby="paper-handoff-heading"
    >
      <header>
        <h2 id="paper-handoff-heading">{handoffHeading(handoff)}</h2>
        {handoff.kind === "attention" && handoff.provenanceId ? (
          <span className="paper-handoff-source-badge">Paper Command</span>
        ) : null}
      </header>

      {handoff.isMalformed ? (
        <p className="paper-cockpit-warning" role="status">
          Draft provenance could not be validated. Workspace evidence remains readable; draft a new ticket after review.
        </p>
      ) : null}

      {handoff.warnings.length > 0 ? (
        <ul className="paper-handoff-warnings" role="status">
          {handoff.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}

      <p>{handoff.handoffSummary}</p>

      {handoff.kind === "attention" && handoff.sourceContextSummary ? (
        <div className="paper-handoff-source-context">
          <h3>Source context</h3>
          <p>{handoff.sourceContextSummary}</p>
          {handoff.sourceTier !== null ? <p className="muted">Tier {handoff.sourceTier}</p> : null}
          {handoff.sourceTimeLabel && handoff.sourceTimeFieldLabel ? (
            <p className="muted">
              {handoff.sourceTimeFieldLabel}:{" "}
              <time dateTime={String(handoff.sourceTime ?? "")}>{handoff.sourceTimeLabel}</time>
            </p>
          ) : null}
          {handoff.sourceReasons.length > 0 ? (
            <ul className="reason-codes">
              {handoff.sourceReasons.map((reason) => (
                <li key={reason.code}>
                  <code>{reason.code}</code> {reason.label}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="muted">{handoff.sourceContextNote}</p>
        </div>
      ) : null}

      {handoff.kind === "lane" && handoff.sourceTimeLabel && handoff.sourceTimeFieldLabel ? (
        <p className="muted">
          {handoff.sourceTimeFieldLabel}:{" "}
          <time dateTime={String(handoff.sourceTime ?? "")}>{handoff.sourceTimeLabel}</time>
        </p>
      ) : null}

      <dl className="paper-cockpit-meta">
        <div>
          <dt>Placeholder</dt>
          <dd>
            {handoff.placeholder.side} × {handoff.placeholder.quantity} {handoff.placeholder.orderType}
          </dd>
        </div>
        {handoff.provenanceId ? (
          <div>
            <dt>Provenance</dt>
            <dd>{handoff.provenanceId}</dd>
          </div>
        ) : null}
        {handoff.attentionId ? (
          <div>
            <dt>Attention</dt>
            <dd>{handoff.attentionId}</dd>
          </div>
        ) : null}
      </dl>

      <p className="muted paper-cockpit-note">{handoff.placeholderWarning}</p>
      <p className="muted paper-handoff-current-context">
        {handoff.currentContextNote}
        {evidenceAsOf ? ` Evidence as of ${evidenceAsOf}.` : ""}
      </p>
    </section>
  );
}
