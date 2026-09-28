import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";

const et = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

/** One value per second (the last cumulative value in that second); chart times must be unique. */
export function perSecond(points: ReadonlyArray<{ time_ms: number; cvd: number }>) {
  const byTime = new Map<number, number>();
  for (const point of points) byTime.set(Math.floor(point.time_ms / 1000), point.cvd);
  return [...byTime].sort((a, b) => a[0] - b[0]).map(([time, value]) => ({ time: time as Time, value }));
}

type Props = { points: ReadonlyArray<{ time_ms: number; cvd: number }>; label: string; timeZone?: "UTC" | "America/New_York";
  /** Axis/crosshair value format; omitted keeps the chart default (US share volume). */
  formatValue?: (value: number) => string };

export default function CvdChart({ points, label, timeZone = "America/New_York", formatValue }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const utc = timeZone === "UTC";
    const time = utc ? new Intl.DateTimeFormat("en-US", { timeZone: "UTC", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : et;
    const chart = createChart(element, {
      autoSize: true,
      layout: { background: { color: "#0f151c" }, textColor: "#8fa1b4", fontSize: 10 },
      grid: { vertLines: { color: "#18212b" }, horzLines: { color: "#18212b" } },
      rightPriceScale: { borderColor: "#27323f" },
      timeScale: { borderColor: "#27323f", timeVisible: true, secondsVisible: true,
        tickMarkFormatter: (value: Time) => time.format(new Date(Number(value) * 1000)) },
      localization: { timeFormatter: (value: Time) => `${time.format(new Date(Number(value) * 1000))} ${utc ? "UTC" : "ET"}`,
        ...(formatValue ? { priceFormatter: formatValue } : {}) },
      crosshair: { mode: 0 }, handleScroll: false, handleScale: false,
    });
    seriesRef.current = chart.addBaselineSeries({
      baseValue: { type: "price", price: 0 }, lineWidth: 2, priceLineVisible: false,
      topLineColor: "#57c79a", topFillColor1: "rgba(87,199,154,0.22)", topFillColor2: "rgba(87,199,154,0.02)",
      bottomLineColor: "#e27d86", bottomFillColor1: "rgba(226,125,134,0.02)", bottomFillColor2: "rgba(226,125,134,0.22)",
    });
    chartRef.current = chart;
    return () => { chart.remove(); chartRef.current = null; seriesRef.current = null; };
  }, [timeZone, formatValue]);
  useEffect(() => {
    seriesRef.current?.setData(perSecond(points));
    chartRef.current?.timeScale().fitContent();
  }, [points, timeZone]);
  return <div className="screener-cvd-chart" ref={containerRef} role="img" aria-label={label} />;
}
