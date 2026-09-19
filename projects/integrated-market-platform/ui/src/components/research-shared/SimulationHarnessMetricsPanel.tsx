import type { ResearchSimulationResponse } from "../../api/schemas";
import { StatePill } from "../imp-ui/StatePill";
import { resolveSemanticState } from "../../state/semanticState";
import { extractSimulationHarnessMetrics } from "./simulationHarnessMetrics";

type Props = {
  payload: ResearchSimulationResponse;
  headingId: string;
};

export function SimulationHarnessMetricsPanel({ payload, headingId }: Props) {
  const metrics = extractSimulationHarnessMetrics(payload);
  return (
    <section className="research-panel" aria-labelledby={headingId}>
      <div className="research-panel-heading">
        <div>
          <div className="research-panel-kicker">Simulator integrity</div>
          <h2 id={headingId}>Drawdown, cost sensitivity, fill realism</h2>
        </div>
      </div>
      <p className="research-muted">
        Historical replay and simulation evidence only. These metrics do not certify production
        trading performance, Item 9 calibration, or live execution readiness.
      </p>
      <dl className="research-fact-grid">
        {metrics.map((metric) => {
          const tone =
            metric.value === "UNAVAILABLE"
              ? "neutral"
              : resolveSemanticState("research", metric.evidenceClass).tone;
          return (
            <div key={metric.id}>
              <dt>{metric.label}</dt>
              <dd>
                <StatePill tone={tone} label={metric.value} raw={metric.value} size="sm" />
                {metric.detail ? <p className="research-muted">{metric.detail}</p> : null}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
