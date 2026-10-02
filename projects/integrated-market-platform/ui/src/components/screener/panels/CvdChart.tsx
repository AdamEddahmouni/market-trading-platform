import { useEffect, useRef, useState } from "react";
import { createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";


type Point = { time_ms: number; cvd: number; delta?: number; segment?: number };
export type FlowViewport = { from: number; to: number; live: boolean };
/** Compatibility for instantaneous callers; temporal buckets arrive pre-aggregated. */
export function perSecond(points: ReadonlyArray<Point>) {
  const byTime = new Map<number, number>();
  for (const point of [...points].sort((a, b) => a.time_ms - b.time_ms)) byTime.set(Math.floor(point.time_ms / 1000), point.cvd);
  return [...byTime].map(([time, value]) => ({ time: time as Time, value }));
}
type Props = { points: ReadonlyArray<Point>; label: string; timeZone?: string;
  formatValue?: (value: number) => string; mode?: "cvd" | "delta"; resetKey?: string;
  onViewport?: (range: FlowViewport) => void };

export default function CvdChart({ points, label, timeZone = "America/New_York", formatValue,
  mode = "cvd", resetKey = "", onViewport }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef(new Map<number, ISeriesApi<"Baseline"> | ISeriesApi<"Histogram">>());
  const latestRef = useRef(0), liveRef = useRef(true), changingRef = useRef(false), fittedRef = useRef(false);
  const firstRef = useRef(0), fitFollowingRef = useRef(true);
  const viewportRef = useRef(onViewport);
  viewportRef.current = onViewport;
  const [live, setLive] = useState(true);
  const publish = () => {
    const range = chartRef.current?.timeScale().getVisibleRange();
    if (range) viewportRef.current?.({ from: Number(range.from) * 1000, to: Number(range.to) * 1000, live: liveRef.current });
  };
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const time = new Intl.DateTimeFormat("en-US", { timeZone, hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
    const chart = createChart(element, {
      autoSize: true,
      layout: { background: { color: "#0f151c" }, textColor: "#8fa1b4", fontSize: 10 },
      grid: { vertLines: { color: "#18212b" }, horzLines: { color: "#18212b" } },
      rightPriceScale: { borderColor: "#27323f" },
      timeScale: { borderColor: "#27323f", timeVisible: true, secondsVisible: true,
        tickMarkFormatter: (value: Time) => time.format(new Date(Number(value) * 1000)) },
      localization: { timeFormatter: (value: Time) => `${time.format(new Date(Number(value) * 1000))} ${timeZone === "UTC" ? "UTC" : "ET"}`,
        ...(formatValue ? { priceFormatter: formatValue } : {}) },
      crosshair: { mode: 0 }, handleScroll: true, handleScale: true,
    });
    chartRef.current = chart; fittedRef.current = false; liveRef.current = true; fitFollowingRef.current = true; setLive(true);
    const changed = (range: { from: Time; to: Time } | null) => {
      if (!range || changingRef.current || !fittedRef.current) return;
      const follows = Number(range.to) >= latestRef.current - 1;
      liveRef.current = follows; setLive(follows);
      fitFollowingRef.current = follows && Number(range.from) <= firstRef.current + 1;
      viewportRef.current?.({ from: Number(range.from) * 1000, to: Number(range.to) * 1000, live: follows });
    };
    chart.timeScale().subscribeVisibleTimeRangeChange(changed);
    return () => {
      chart.timeScale().unsubscribeVisibleTimeRangeChange(changed);
      chart.remove(); chartRef.current = null; seriesRef.current.clear();
    };
  }, [timeZone, formatValue, mode]);
  useEffect(() => { fittedRef.current = false; liveRef.current = true; fitFollowingRef.current = true; setLive(true); }, [resetKey]);
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const scale = chart.timeScale(), previous = scale.getVisibleRange();
    changingRef.current = true;
    latestRef.current = points.length ? points[points.length - 1].time_ms / 1000 : 0;
    firstRef.current = points.length ? points[0].time_ms / 1000 : 0;
    const segments = new Map<number, Point[]>();
    for (const point of points) {
      const segment = point.segment ?? 0;
      if (!segments.has(segment)) segments.set(segment, []);
      segments.get(segment)!.push(point);
    }
    for (const [segment, series] of seriesRef.current) if (!segments.has(segment)) {
      chart.removeSeries(series); seriesRef.current.delete(segment);
    }
    for (const [segment, rows] of segments) {
      let series = seriesRef.current.get(segment);
      if (!series) {
        series = mode === "delta" ? chart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false })
          : chart.addBaselineSeries({ baseValue: { type: "price", price: 0 }, lineWidth: 2, priceLineVisible: false,
            lastValueVisible: false, topLineColor: "#57c79a", topFillColor1: "rgba(87,199,154,0.22)", topFillColor2: "rgba(87,199,154,0.02)",
            bottomLineColor: "#e27d86", bottomFillColor1: "rgba(226,125,134,0.02)", bottomFillColor2: "rgba(226,125,134,0.22)" });
        seriesRef.current.set(segment, series);
      }
      series.setData(rows.map(p => ({ time: Math.floor(p.time_ms / 1000) as Time,
        value: mode === "delta" ? p.delta ?? 0 : p.cvd, ...(mode === "delta" ? { color: (p.delta ?? 0) >= 0 ? "#57c79a" : "#e27d86" } : {}) })));
    }
    if (points.length && !fittedRef.current) { scale.fitContent(); fittedRef.current = true; }
    else if (previous) {
      if (liveRef.current) {
        const span = Number(previous.to) - Number(previous.from);
        scale.setVisibleRange({ from: (fitFollowingRef.current ? Math.min(firstRef.current, latestRef.current - 1) : latestRef.current - span) as Time, to: latestRef.current as Time });
      } else scale.setVisibleRange(previous);
    }
    changingRef.current = false;
  }, [points, resetKey, timeZone, formatValue, mode]);
  const zoom = (factor: number) => {
    const scale = chartRef.current?.timeScale(), range = scale?.getVisibleLogicalRange();
    if (!range) return;
    const middle = (range.from + range.to) / 2, half = Math.max(1, (range.to - range.from) * factor / 2);
    scale?.setVisibleLogicalRange({ from: middle - half, to: middle + half });
  };
  return <>
    <div className="screener-flow-actions" role="group" aria-label="Chart navigation">
      <span role="status">{live ? "LIVE" : "Historical view"}</span>
      <button type="button" onClick={() => zoom(0.5)} aria-label="Zoom in">+</button>
      <button type="button" onClick={() => zoom(2)} aria-label="Zoom out">−</button>
      <button type="button" onClick={() => { fitFollowingRef.current = true; chartRef.current?.timeScale().fitContent(); liveRef.current = true; setLive(true); publish(); }}>Fit</button>
      <button type="button" onClick={() => { liveRef.current = true; setLive(true); chartRef.current?.timeScale().scrollToRealTime(); publish(); }}>Go Live</button>
    </div>
    <div className="screener-cvd-chart" ref={containerRef} role="img" aria-label={label} />
  </>;
}
