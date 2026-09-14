import type { OverviewKpiCell, OverviewKpiState } from "./impOverviewMetrics";

type Props = {
  cells: OverviewKpiCell[];
  state: OverviewKpiState;
};

export function ImpOverviewKpiStrip({ cells, state }: Props) {
  return (
    <section className="imp-overview-kpi-strip" aria-label="Overview KPIs">
      {state === "error" ? (
        <p className="imp-overview-kpi-banner" role="alert">
          Portfolio and session metrics are unavailable. Remaining overview panels degrade safely.
        </p>
      ) : null}
      <ul className="imp-overview-kpi-grid">
        {cells.map((cell) => (
          <li key={cell.id} className={`imp-overview-kpi-card tone-${cell.tone ?? "neutral"}`}>
            <span className="imp-overview-kpi-label">{cell.label}</span>
            <span className="imp-overview-kpi-value">{cell.value}</span>
            {cell.detail ? <span className="imp-overview-kpi-detail">{cell.detail}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
