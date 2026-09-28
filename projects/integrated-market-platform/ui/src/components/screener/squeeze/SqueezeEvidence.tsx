import type { SqueezeMetric, SqueezePayload } from "../../../api/screenerSqueeze";
import { squeezeStateLabel } from "../../squeeze/SqueezeLifecycle";

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });
const date = (value: string | null) => {
  if (!value) return "No source time";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${new Date(`${value}T12:00:00Z`).toLocaleDateString("en-US", { timeZone: "UTC", dateStyle: "medium" })} trade date`;
  return `${new Date(value).toLocaleString("en-US", { timeZone: "America/New_York", dateStyle: "medium", timeStyle: "short" })} ET`;
};
export function metricValue(metric: SqueezeMetric) {
  if (metric.value == null) return ({ NO_RECORD: "No record", NOT_CONFIGURED: "Not configured", NOT_REQUESTED: "Not requested",
    NOT_SUBSCRIBED: "Not subscribed", PENDING: "Pending", STALE: "Stale" } as Record<string, string>)[metric.quality] ?? "Unavailable";
  if (typeof metric.value === "boolean") return metric.value ? "On list" : "Not on list";
  if (typeof metric.value === "string") return metric.value;
  if (metric.unit === "percent") return `${metric.value > 0 && ["change_pct", "short_interest_change_pct"].includes(metric.id) ? "+" : ""}${metric.value.toFixed(2)}%`;
  if (metric.unit === "ratio") return `${metric.value.toFixed(2)}×`;
  if (metric.unit === "days") return `${metric.value.toFixed(2)} days`;
  if (metric.unit === "shares" || metric.unit === "count") return compact.format(metric.value);
  if (metric.unit === "USD") return `$${metric.value.toFixed(2)}`;
  return metric.value.toFixed(2);
}
export function MetricList({ title, items, compactMode = false }: { title: string; items: SqueezeMetric[]; compactMode?: boolean }) {
  return <section className="screener-squeeze-section" aria-label={title}><h3>{title}</h3>
    <dl>{items.map((item) => <div key={item.id} className={item.value == null ? "unavailable" : undefined}>
      <dt>{item.label}</dt><dd><strong>{metricValue(item)}</strong>
        {!compactMode && <small>{item.source_label} · {item.clock.kind.toLowerCase().replace(/_/g, " ")} · {item.quality.toLowerCase().replace(/_/g, " ")} · {date(item.clock.as_of)}{item.reason ? ` · ${item.reason.replace(/_/g, " ").toLowerCase()}` : ""}</small>}
      </dd></div>)}</dl></section>;
}
export function Coverage({ data }: { data: SqueezePayload }) {
  return <div className="screener-squeeze-coverage" aria-label="Evidence coverage">
    <span>Supporting <strong>{data.coverage.supporting}</strong></span>
    <span>Conflicting <strong>{data.coverage.conflicting}</strong></span>
    <span>Unavailable <strong>{data.coverage.unavailable}</strong></span>
    {data.coverage.stale > 0 && <span>Stale <strong>{data.coverage.stale}</strong></span>}
  </div>;
}
export function WhyListed({ data }: { data: SqueezePayload }) {
  return <section className="screener-squeeze-section" aria-label="Why Listed"><h3>Why Listed</h3>
    {data.why_listed.state === "NO_ACTIVE_FILTERS" ? <p>No active filter; this row is listed by the current Screener universe.</p> :
      <ul>{data.why_listed.items.map((item) => <li key={item.filter_id}>{item.text}</li>)}</ul>}
    <p className="screener-panel-note">A discovery match does not establish a squeeze.</p>
  </section>;
}
export function StateSummary({ data }: { data: SqueezePayload }) {
  return <div className="screener-squeeze-state"><strong>{squeezeStateLabel(data.assessment.state)}</strong>
    <span>{data.source_state.replace(/_/g, " ").toLowerCase()} · {data.assessment.state_basis.replace(/_/g, " ").toLowerCase()}</span></div>;
}
