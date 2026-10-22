import type { SmaStopAggregate, SmaStopEvaluation } from "../../api/paperRiskControl";

const METHODS: Array<[string, string]> = [
  ["SMA_TRAIL", "SMA trail"],
  ["RAW_PRICE_TRAIL", "Raw-price trail"],
  ["FIXED_INITIAL_STOP", "Fixed initial stop"],
  ["NO_TRAIL", "Existing / no-trail exit"],
];
const CONCLUSION_TEXT: Record<string, string> = {
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
  NO_CLEAR_DIFFERENCE: "No clear difference",
  SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF: "SMA reduced downside with a return tradeoff",
  SMA_UNDERPERFORMED_REFERENCE: "SMA underperformed the reference",
};

const bps = (value: number | null | undefined) => (value === null || value === undefined ? "n/a" : `${value.toFixed(2)} bps`);
const share = (value: number) => `${(value * 100).toFixed(1)}%`;

function MethodTable({ side, primary, rows }: { side: string; primary: boolean; rows: Record<string, SmaStopAggregate> }) {
  return (
    <table className="sma-stop-comparison">
      <caption>
        {side} episodes{primary ? " (primary comparison)" : " (policy math only — Paper short authority is unchanged)"}. Historical replay; not live and not Paper.
      </caption>
      <thead>
        <tr>
          <th scope="col">Method</th>
          <th scope="col">Episodes</th>
          <th scope="col">Stopped</th>
          <th scope="col">Mean adverse excursion</th>
          <th scope="col">Mean max drawdown</th>
          <th scope="col">Worst drawdown</th>
          <th scope="col">Loss severity</th>
          <th scope="col">Mean gross return</th>
          <th scope="col">Mean net return</th>
          <th scope="col">Exited before a better horizon price</th>
          <th scope="col">Mean bars held</th>
        </tr>
      </thead>
      <tbody>
        {METHODS.filter(([id]) => rows[id]).map(([id, label]) => {
          const row = rows[id];
          return (
            <tr key={id}>
              <th scope="row">{label}</th>
              <td>{row.episodes}</td>
              <td>{share(row.stop_frequency)}</td>
              <td>{bps(row.mean_mae_bps)}</td>
              <td>{bps(row.mean_max_drawdown_bps)}</td>
              <td>{bps(row.worst_drawdown_bps)}</td>
              <td>{bps(row.loss_severity_bps)}</td>
              <td>{bps(row.mean_gross_return_bps)}</td>
              <td>{bps(row.mean_net_return_bps)}</td>
              <td>{share(row.premature_exit_frequency)}</td>
              <td>{row.mean_holding_bars ?? "n/a"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function SmaStopEvaluationTable({ evaluation }: { evaluation: SmaStopEvaluation }) {
  if (evaluation.result_status === "NOT_EXECUTED") {
    return (
      <p role="status">
        Insufficient evidence — the replay comparison has not been executed ({evaluation.reason_codes.join(", ")}). No method comparison is available.
      </p>
    );
  }
  const { conclusion, counts, policy, provenance } = evaluation;
  const sides = [evaluation.primary_side, ...Object.keys(evaluation.aggregates).filter((side) => side !== evaluation.primary_side)];
  return (
    <section aria-label="Method comparison">
      <h3>Method comparison</h3>
      <p>
        Evidence class: HISTORICAL REPLAY · Status: REPLAY EVALUATED · Calibration: NOT CALIBRATED. Policy under test: SMA {policy.sma_window_bars} on completed{" "}
        {policy.bar_interval} bars ({policy.config_label === "REFERENCE_TEST_CONFIG" ? "reference test configuration — not optimized" : policy.config_label}).
      </p>
      <p>
        {counts.episodes} episodes, {counts.evaluable} evaluable, {counts.excluded} excluded
        {Object.entries(counts.exclusions).map(([code, count]) => ` (${code}: ${count})`).join("")}. {evaluation.corpus.sessions.length} sessions,{" "}
        {evaluation.corpus.instruments} instrument, {evaluation.corpus.bars} bars. Matched initial risk across the three stop methods.
      </p>
      {sides.filter((side) => evaluation.aggregates[side]).map((side) => (
        <MethodTable key={side} side={side} primary={side === evaluation.primary_side} rows={evaluation.aggregates[side]} />
      ))}
      <p>
        Stop exits fill at the trigger bar&apos;s worst price, never at the stop level. Net return subtracts {evaluation.fill_model.cost_bps_per_side} bps per side.
        Lower adverse excursion and drawdown are better; a stop can lower both and still lower return.
      </p>
      <p role="status">
        <strong>Conclusion: {CONCLUSION_TEXT[conclusion.conclusion]}.</strong> {conclusion.statement} Superiority claim: none.
      </p>
      <p>
        In-sample pattern (description only, not a claim): {CONCLUSION_TEXT[conclusion.in_sample_pattern] ?? conclusion.in_sample_pattern}. {evaluation.sample_size_note}
      </p>
      <details>
        <summary>Provenance and hashes</summary>
        <dl className="paper-cockpit-meta">
          <div><dt>Corpus</dt><dd>{provenance.corpus_path} · {provenance.corpus_evidence_label}</dd></div>
          <div><dt>Sessions</dt><dd>{provenance.session_dates.join(", ")}</dd></div>
          <div><dt>Dataset fingerprint</dt><dd><code>{provenance.dataset_fingerprint}</code></dd></div>
          <div><dt>Corpus file SHA-256</dt><dd><code>{provenance.normalized_sha256}</code></dd></div>
          <div><dt>Corpus unchanged by the run</dt><dd>{evaluation.corpus_unchanged ? "Yes" : "No"}</dd></div>
          <div><dt>Frozen definition hash</dt><dd><code>{evaluation.definition_hash}</code></dd></div>
          <div><dt>Input hash</dt><dd><code>{evaluation.input_hash}</code></dd></div>
          <div><dt>Result hash</dt><dd><code>{evaluation.result_hash}</code></dd></div>
          <div><dt>Policy</dt><dd><code>{policy.policy_id}</code></dd></div>
          <div><dt>Fill model</dt><dd>{evaluation.fill_model.id}</dd></div>
        </dl>
      </details>
    </section>
  );
}
