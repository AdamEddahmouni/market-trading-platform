import type { ResearchModelsResponse } from "../../api/schemas";

type Props = {
  payload: ResearchModelsResponse;
};

export function ModelLabPanel({ payload }: Props) {
  const summary = payload.model_summary;
  const spec = payload.strategy_spec;
  const manifest = payload.dataset_manifest;

  return (
    <section className="model-lab-panel">
      <header className="panel-header">
        <h2>Model Lab</h2>
        <p>{payload.disclaimer}</p>
        <p className="research-meta">
          Boundary: {payload.authority_boundary} · Epistemic: {payload.epistemic_class}
        </p>
      </header>

      <dl className="metric-grid">
        <div>
          <dt>Model family</dt>
          <dd>{String(summary.model_family ?? "—")}</dd>
        </div>
        <div>
          <dt>Alignment type</dt>
          <dd>{String(summary.alignment_type ?? spec.alignment_type ?? "—")}</dd>
        </div>
        <div>
          <dt>Strategy identity</dt>
          <dd className="mono">{String(summary.strategy_identity_hash ?? spec.strategy_identity_hash ?? "—")}</dd>
        </div>
        <div>
          <dt>Dataset fingerprint</dt>
          <dd className="mono">{String(summary.dataset_fingerprint ?? manifest.dataset_fingerprint ?? "—")}</dd>
        </div>
        <div>
          <dt>Walk-forward folds</dt>
          <dd>{payload.walk_forward_fold_count}</dd>
        </div>
        <div>
          <dt>Preregistration</dt>
          <dd>{payload.preregistration_status ?? "—"}</dd>
        </div>
      </dl>

      <p className="workspace-hint">
        Signals: {payload.interpretation_summary.signal_count} · Abstentions:{" "}
        {payload.interpretation_summary.abstention_count} · At cutoff:{" "}
        {payload.interpretation_summary.total_at_cutoff}
      </p>

      <table className="data-table">
        <thead>
          <tr>
            <th>Observation time</th>
            <th>Outcome</th>
            <th>Cutoff</th>
            <th>Alignment</th>
          </tr>
        </thead>
        <tbody>
          {payload.interpretations.map((row, index) => (
            <tr key={`${row.observation_time ?? index}-${index}`}>
              <td>{String(row.observation_time ?? "—")}</td>
              <td>{String(row.outcome ?? "—")}</td>
              <td>{String(row.prediction_cutoff ?? "—")}</td>
              <td>{String(row.alignment_decision ?? row.interpretation ?? "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <footer className="research-provenance">Phase 5R — admitted fixture only. No trade authority.</footer>
    </section>
  );
}
