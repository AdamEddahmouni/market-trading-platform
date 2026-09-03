import type { WorkspaceEvidenceLane } from "../../api/schemas";

type Props = {
  instrumentId: string;
  lanes: WorkspaceEvidenceLane[];
  mixSummary: string;
  dataLabel?: string;
  onSelectLane: (lane: WorkspaceEvidenceLane) => void;
};

function relevanceClass(relevance: string): string {
  if (relevance === "HIGH") return "relevance-high";
  if (relevance === "MEDIUM") return "relevance-medium";
  return "relevance-low";
}

export function WhatMattersNowPanel({
  instrumentId,
  lanes,
  mixSummary,
  dataLabel,
  onSelectLane,
}: Props) {
  return (
    <section className="panel what-matters-panel">
      <header className="what-matters-header">
        <h2>What matters now</h2>
        <p className="muted">
          {instrumentId}
          {dataLabel ? ` · ${dataLabel}` : ""}
          {mixSummary && mixSummary !== "UNKNOWN" ? ` · evidence ${mixSummary.replace(/_/g, " ")}` : ""}
        </p>
      </header>
      <table className="data-table what-matters-table">
        <thead>
          <tr>
            <th>Lane</th>
            <th>Relevance</th>
            <th>State</th>
            <th>Freshness</th>
          </tr>
        </thead>
        <tbody>
          {lanes.map((lane) => (
            <tr key={lane.lane}>
              <td>
                <button type="button" className="link-button" onClick={() => onSelectLane(lane)}>
                  {lane.lane.replace(/_/g, " ")}
                </button>
              </td>
              <td>
                <span className={relevanceClass(String(lane.relevance))}>{lane.relevance}</span>
              </td>
              <td>{lane.summary}</td>
              <td className="muted">{lane.freshness_label}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {lanes.length === 0 ? <p className="muted">No lane evidence available for this instrument.</p> : null}
    </section>
  );
}