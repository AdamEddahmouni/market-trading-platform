import type { ProviderHealthResponse } from "./liveDashboardViewModel";
import { liveConnectionMetrics } from "./liveDashboardViewModel";

type Props = {
  health?: ProviderHealthResponse;
  state: "loading" | "ready" | "error";
};

export function LiveProviderRibbon({ health, state }: Props) {
  return (
    <section className="live-provider-ribbon" aria-label="Connection summary">
      <h2>Connection summary</h2>
      {state === "loading" ? <p role="status">Loading provider health…</p> : null}
      {state === "error" ? <p className="unavailable">Provider health unavailable.</p> : null}
      {state === "ready" ? (
        <dl>
          {liveConnectionMetrics(health).map((metric) => (
            <div key={metric.id} className={metric.value === "UNAVAILABLE" ? "unavailable" : undefined}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
              {metric.detail ? <span>{metric.detail}</span> : null}
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}
