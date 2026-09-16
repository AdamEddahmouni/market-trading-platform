import { SEMANTIC_TONE_ICON } from "../../state/semanticState";
import type { OverviewKpiCell } from "./impOverviewMetrics";

type Props = {
  cells: OverviewKpiCell[];
};

/**
 * The Command decision-metric strip. Tones come from the semantic design
 * system (`data-tone` + icon + text — never color alone); neutral cells stay
 * unaccented so caution/critical cells carry the visual weight. Cells are
 * non-interactive orientation — actions live on the queue and cards.
 */
export function ImpOverviewKpiStrip({ cells }: Props) {
  return (
    <section className="imp-overview-kpi-strip" aria-label="Decision metrics">
      <ul className="imp-overview-kpi-grid">
        {cells.map((cell) => {
          const tone = cell.tone ?? "neutral";
          return (
            <li key={cell.id} className="imp-overview-kpi-card" data-tone={tone}>
              <span className="imp-overview-kpi-label">{cell.label}</span>
              <span className="imp-overview-kpi-value">
                <span className="imp-overview-kpi-icon" aria-hidden="true">
                  {SEMANTIC_TONE_ICON[tone]}
                </span>
                {cell.value}
              </span>
              {cell.detail ? <span className="imp-overview-kpi-detail">{cell.detail}</span> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
