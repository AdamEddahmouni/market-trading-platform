import { Link } from "react-router-dom";
import { useExploreSqueezeQuery } from "../api/hooks";
import { CountBarChartPanel } from "./charts/ResearchChartPanels";

type Props = {
  onExplain?: (ref: string) => void;
};

function formatProvenanceValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) return value.map((item) => formatProvenanceValue(item)).join(", ");
  return JSON.stringify(value);
}

export function ExplorePage({ onExplain }: Props) {
  const squeezeQuery = useExploreSqueezeQuery();

  if (squeezeQuery.isLoading) {
    return <div className="app-loading">Loading donor screener bridge…</div>;
  }

  const payload = squeezeQuery.data;
  if (!payload) {
    return <section className="page gated-page"><h1>EXPLORE</h1><p>Bridge unavailable.</p></section>;
  }

  return (
    <section className="page explore-page">
      <h1>EXPLORE — Short Squeeze Screener (read-only bridge)</h1>
      <p className="explore-disclaimer">{payload.disclaimer ?? "Research only."}</p>
      {!payload.available ? (
        <div className="capability-panel unavailable">
          <p>{payload.reason ?? "Donor server unavailable."}</p>
        </div>
      ) : (
        <>
          <p className="explore-meta">
            Source: {payload.source} · Rows: {payload.row_count} · Mode: {payload.bridge_mode}
          </p>
          {payload.manifest ? (
            <dl className="explore-provenance-grid">
              <div>
                <dt>Donor API</dt>
                <dd>{formatProvenanceValue(payload.manifest.api_version)}</dd>
              </div>
              <div>
                <dt>Schema</dt>
                <dd>{formatProvenanceValue(payload.manifest.schema_version)}</dd>
              </div>
              <div>
                <dt>Prohibited capabilities</dt>
                <dd>{formatProvenanceValue(payload.manifest.prohibited_capabilities)}</dd>
              </div>
            </dl>
          ) : null}
          {payload.header ? (
            <p className="explore-header-note">
              Aggregate header: {formatProvenanceValue(payload.header)}
            </p>
          ) : null}
          {payload.outcome_summary && payload.outcome_summary.length > 0 ? (
            <div className="chart-grid chart-grid-inline">
              <CountBarChartPanel
                title="Squeeze outcome distribution"
                series={payload.outcome_summary}
                provenance={{
                  source: payload.source,
                  method: "donor frozen screener aggregation",
                }}
                ariaLabel="Squeeze outcome distribution chart"
              />
            </div>
          ) : null}
          <table className="explore-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Outcome</th>
                <th>Evidence</th>
                <th>Detection</th>
                <th>Freshness</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {payload.rows.map((row) => (
                <tr key={row.screener_id}>
                  <td>
                    <Link className="explore-symbol-link" to={`/workspace/${row.symbol}/squeeze`}>
                      {row.symbol}
                    </Link>
                  </td>
                  <td>{row.outcome_status}</td>
                  <td>{row.evidence_coverage}</td>
                  <td>{row.research_detection}</td>
                  <td>{row.freshness}</td>
                  <td>
                    {row.explanation_ref && onExplain ? (
                      <button type="button" className="explore-explain-link" onClick={() => onExplain(row.explanation_ref!)}>
                        Explain
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
