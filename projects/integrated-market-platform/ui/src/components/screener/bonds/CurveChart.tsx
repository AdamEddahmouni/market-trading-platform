import { useMemo, useState } from "react";
import type { CurvePayload } from "../../../api/screenerBonds";
import "./bonds.css";

/**
 * Maturity → yield chart for Treasury par curves. Not a time series: the x
 * axis is maturity on a square-root scale (so the bill end stays readable),
 * the y axis is yield in percent. Only published points are drawn as markers;
 * straight segments join neighbouring published points and no value is
 * interpolated or read off a segment.
 */
type Series = { id: string; label: string; className: string; dashed?: boolean;
  points: { tenor: string; years: number; value: number }[] };
type Marker = { years: number; value: number | null; label: string };

const WIDTH = 520;
const HEIGHT = 210;
const PAD = { left: 40, right: 64, top: 12, bottom: 30 };
const TICKS = ["1M", "6M", "1Y", "2Y", "5Y", "10Y", "20Y", "30Y"];
const TICK_YEARS: Record<string, number> = { "1M": 1 / 12, "6M": 0.5, "1Y": 1, "2Y": 2, "5Y": 5, "10Y": 10, "20Y": 20, "30Y": 30 };

export function CurveChart({ nominal, real, marker }: { nominal: CurvePayload; real: CurvePayload; marker?: Marker | null }) {
  const [hover, setHover] = useState<string | null>(null);
  const series = useMemo<Series[]>(() => [
    nominal.previous ? { id: "previous", label: `Nominal · prior ${nominal.previous.publication_date}`, className: "nominal", dashed: true, points: nominal.previous.points } : null,
    nominal.points.length ? { id: "nominal", label: `Nominal par · ${nominal.publication_date}`, className: "nominal", points: nominal.points } : null,
    real.points.length ? { id: "real", label: `Real par (TIPS) · ${real.publication_date}`, className: "real", points: real.points } : null,
  ].filter((item): item is Series => item !== null), [nominal, real]);
  const values = series.flatMap((item) => item.points.map((point) => point.value));
  if (!values.length) return null;
  // Fitted to the published points in half-percent steps; negative real yields stay on the axis.
  const low = Math.floor(Math.min(...values) * 2) / 2 - 0.5;
  const high = Math.ceil(Math.max(...values) * 2) / 2 + 0.25;
  const x = (years: number) => PAD.left + Math.sqrt(years / 30) * (WIDTH - PAD.left - PAD.right);
  const y = (value: number) => PAD.top + (high - value) / (high - low || 1) * (HEIGHT - PAD.top - PAD.bottom);
  const step = high - low > 4 ? 1 : 0.5;
  const yTicks = Array.from({ length: Math.floor((high - low) / step) + 1 }, (_, index) => low + index * step).filter((value) => value <= high);
  const path = (points: Series["points"]) => points.map((point, index) => `${index ? "L" : "M"}${x(point.years).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
  const tenors = [...new Set(series.flatMap((item) => item.points.map((point) => point.tenor)))];
  const hovered = hover ? series.map((item) => ({ item, point: item.points.find((point) => point.tenor === hover) })).filter((entry) => entry.point) : [];
  const hoverYears = hovered[0]?.point?.years;
  const latest = series.filter((item) => !item.dashed);
  const summary = latest.map((item) => `${item.label}: ${item.points.map((point) => `${point.tenor} ${point.value.toFixed(2)}%`).join(", ")}`).join(". ");
  return <figure className="bond-curve">
    <div className="bond-curve-legend" aria-hidden="true">{series.map((item) =>
      <span key={item.id} className={`bond-curve-key ${item.className}${item.dashed ? " dashed" : ""}`}><i />{item.label}</span>)}</div>
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`Treasury yield curve by maturity. ${summary}`}
      onMouseLeave={() => setHover(null)}>
      {yTicks.map((value) => <g key={value} className="bond-curve-grid">
        <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(value)} y2={y(value)} />
        <text x={PAD.left - 6} y={y(value) + 3} textAnchor="end">{value.toFixed(step < 1 ? 1 : 0)}%</text></g>)}
      {TICKS.map((tenor) => <text key={tenor} className="bond-curve-axis" x={x(TICK_YEARS[tenor])} y={HEIGHT - PAD.bottom + 14} textAnchor="middle">{tenor}</text>)}
      <text className="bond-curve-axis" x={(WIDTH - PAD.right + PAD.left) / 2} y={HEIGHT - 3} textAnchor="middle">Maturity (square-root scale)</text>
      {hoverYears != null && <line className="bond-curve-crosshair" x1={x(hoverYears)} x2={x(hoverYears)} y1={PAD.top} y2={HEIGHT - PAD.bottom} />}
      {marker && <g className="bond-curve-marker">
        <line x1={x(Math.min(30, marker.years))} x2={x(Math.min(30, marker.years))} y1={PAD.top} y2={HEIGHT - PAD.bottom} />
        {marker.value != null && <circle cx={x(Math.min(30, marker.years))} cy={y(marker.value)} r={5} />}
        <text x={x(Math.min(30, marker.years)) + 4} y={PAD.top + 9}>{marker.label}</text></g>}
      {series.map((item) => <g key={item.id} className={`bond-curve-series ${item.className}${item.dashed ? " dashed" : ""}`}>
        <path d={path(item.points)} />
        {!item.dashed && item.points.map((point) => <circle key={point.tenor} cx={x(point.years)} cy={y(point.value)} r={hover === point.tenor ? 5 : 4} />)}
        {!item.dashed && <text className="bond-curve-end" x={x(item.points[item.points.length - 1].years) + 6}
          y={y(item.points[item.points.length - 1].value) + 3}>{item.className === "real" ? "Real" : "Nominal"}</text>}
      </g>)}
      {tenors.map((tenor) => {
        const years = series.flatMap((item) => item.points).find((point) => point.tenor === tenor)!.years;
        return <rect key={tenor} className="bond-curve-hit" x={x(years) - 10} y={PAD.top} width={20} height={HEIGHT - PAD.top - PAD.bottom}
          onMouseEnter={() => setHover(tenor)} />;
      })}
    </svg>
    {hovered.length > 0 && <div className="bond-curve-tooltip" role="status">
      <strong>{hover}</strong>{hovered.map(({ item, point }) => <span key={item.id}>{item.label}: {point!.value.toFixed(2)}%</span>)}</div>}
    <figcaption className="screener-panel-note">Markers are published points; segments only join them — no value is interpolated.</figcaption>
    <table className="sr-only"><caption>Published par yields by tenor</caption>
      <thead><tr><th scope="col">Tenor</th>{series.map((item) => <th key={item.id} scope="col">{item.label}</th>)}</tr></thead>
      <tbody>{tenors.map((tenor) => <tr key={tenor}><th scope="row">{tenor}</th>{series.map((item) => {
        const point = item.points.find((entry) => entry.tenor === tenor);
        return <td key={item.id}>{point ? `${point.value.toFixed(2)}%` : "—"}</td>;
      })}</tr>)}</tbody></table>
  </figure>;
}
