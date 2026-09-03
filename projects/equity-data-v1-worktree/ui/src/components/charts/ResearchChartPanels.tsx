import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartCountPoint } from "../../lib/chartTransforms";
import { hasChartData } from "../../lib/chartTransforms";
import { ChartEmptyState } from "./ChartEmptyState";
import { ChartProvenance } from "./ChartProvenance";
import { CHART_COLORS } from "./chartTheme";

type PanelProps = {
  title: string;
  series: ChartCountPoint[];
  provenance: { source: string; method?: string };
  emptyMessage?: string;
  ariaLabel: string;
};

export function CountBarChartPanel({
  title,
  series,
  provenance,
  emptyMessage = "No data at current replay cutoff.",
  ariaLabel,
}: PanelProps) {
  if (!hasChartData(series)) {
    return (
      <section className="chart-panel" aria-label={ariaLabel}>
        <h3>{title}</h3>
        <ChartEmptyState message={emptyMessage} />
        <ChartProvenance source={provenance.source} method={provenance.method} />
      </section>
    );
  }

  return (
    <section className="chart-panel" aria-label={ariaLabel}>
      <h3>{title}</h3>
      <div className="chart-canvas" role="img" aria-label={ariaLabel}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: CHART_COLORS.text, fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fill: CHART_COLORS.text, fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: "#141820",
                border: "1px solid #2a3142",
                color: "#e8ecf4",
              }}
            />
            <Bar dataKey="count" fill={CHART_COLORS.accent} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="chart-data-table">
        <caption className="chart-data-caption">{title} tabular summary</caption>
        <thead>
          <tr>
            <th>Label</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          {series.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td>{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ChartProvenance source={provenance.source} method={provenance.method} />
    </section>
  );
}

type TimelinePoint = {
  observation_index: number;
  cumulative_signals: number;
  outcome: string;
};

type TimelineProps = {
  title: string;
  timeline: TimelinePoint[];
  provenance: { source: string; method?: string };
  ariaLabel: string;
};

export function SignalTimelineChartPanel({ title, timeline, provenance, ariaLabel }: TimelineProps) {
  if (!timeline.length) {
    return (
      <section className="chart-panel" aria-label={ariaLabel}>
        <h3>{title}</h3>
        <ChartEmptyState message="No walk-forward interpretations at replay cutoff." />
        <ChartProvenance source={provenance.source} method={provenance.method} />
      </section>
    );
  }

  return (
    <section className="chart-panel" aria-label={ariaLabel}>
      <h3>{title}</h3>
      <div className="chart-canvas" role="img" aria-label={ariaLabel}>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={timeline} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" />
            <XAxis
              dataKey="observation_index"
              tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
              label={{ value: "Observation", fill: CHART_COLORS.text, fontSize: 11 }}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
              label={{ value: "Signals", fill: CHART_COLORS.text, fontSize: 11, angle: -90, position: "insideLeft" }}
            />
            <Tooltip
              contentStyle={{
                background: "#141820",
                border: "1px solid #2a3142",
                color: "#e8ecf4",
              }}
            />
            <Line
              type="monotone"
              dataKey="cumulative_signals"
              stroke={CHART_COLORS.long}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ChartProvenance source={provenance.source} method={provenance.method} />
    </section>
  );
}
