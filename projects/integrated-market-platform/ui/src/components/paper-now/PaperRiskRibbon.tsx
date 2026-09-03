import type { PaperPortfolioResponse } from "../../api/client";
import { paperRiskMetrics } from "./paperDashboardViewModel";

type Props = { portfolio?: PaperPortfolioResponse; state: "loading" | "ready" | "error" };

export function PaperRiskRibbon({ portfolio, state }: Props) {
  return (
    <section className="paper-risk-ribbon" aria-label="Risk summary">
      <h2>Risk summary</h2>
      {state === "loading" ? <p role="status">Loading portfolio risk…</p> : null}
      {state === "error" || !portfolio ? <p className="unavailable">Portfolio risk: Unavailable.</p> : null}
      {state === "ready" && portfolio ? (
        <dl>
          {paperRiskMetrics(portfolio).map((metric) => (
            <div key={metric.id} className={metric.available ? "" : "unavailable"}>
              <dt>{metric.label}</dt><dd>{metric.value}</dd>
              {metric.detail ? <span>{metric.detail}</span> : null}
              {metric.percent !== undefined ? (
                <div className="paper-risk-meter" role="meter" aria-label={`${metric.label} utilization`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(metric.percent)} aria-valuetext={metric.value}>
                  <span style={{ width: `${metric.percent}%` }} />
                </div>
              ) : null}
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}
