import type { WorkspaceEvidenceLane } from "../../api/schemas";

type Props = {
  instrumentId: string;
  lanes: WorkspaceEvidenceLane[];
  mixSummary?: string;
  dataLabel?: string;
  evidenceAsOf?: string | null;
  phase: "loading" | "error" | "empty" | "ready";
  phaseMessage?: string;
};

export function PaperWhatMattersNow({
  instrumentId,
  lanes,
  mixSummary,
  dataLabel,
  evidenceAsOf,
  phase,
  phaseMessage,
}: Props) {
  const highlights = lanes.slice(0, 5);

  return (
    <section className="panel paper-cockpit-panel" aria-labelledby="what-matters-heading">
      <h2 id="what-matters-heading">What matters now</h2>
      <p className="muted">
        {instrumentId}
        {dataLabel ? ` · ${dataLabel}` : ""}
        {mixSummary && mixSummary !== "UNKNOWN" ? ` · evidence ${mixSummary.replace(/_/g, " ")}` : ""}
        {evidenceAsOf ? ` · as of ${evidenceAsOf}` : ""}
      </p>
      {phase === "loading" ? <p role="status">Loading cross-lane evidence…</p> : null}
      {phase === "error" ? (
        <p className="paper-cockpit-warning" role="status">
          {phaseMessage ?? "Cross-lane evidence unavailable."}
        </p>
      ) : null}
      {phase === "ready" && highlights.length > 0 ? (
        <ul className="what-matters-bullets">
          {highlights.map((lane) => (
            <li key={lane.lane}>
              <strong>{lane.lane.replace(/_/g, " ")}</strong> · {lane.relevance} · {lane.summary}
              {lane.direction && lane.direction !== "UNKNOWN"
                ? ` · observational direction ${lane.direction.toLowerCase()}`
                : " · no directional conclusion"}
              {lane.freshness_label ? ` · ${lane.freshness_label}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {phase === "empty" || (phase === "ready" && highlights.length === 0) ? (
        <p className="muted">No cross-lane evidence highlights available.</p>
      ) : null}
      <p className="muted">Full lane table remains in workspace observability below.</p>
    </section>
  );
}
