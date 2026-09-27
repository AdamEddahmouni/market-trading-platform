import { useEffect, useRef } from "react";
import { createChart, LineStyle, type IChartApi, type IPriceLine, type ISeriesApi, type Time } from "lightweight-charts";
import type { PreviewBar } from "../../api/screener";
import type { ClassifiedZone } from "./srClassify";

const et = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false });
const etDay = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric" });
const SUPPORT = "#4fbf8f";
const RESISTANCE = "#e0707b";
const VISIBLE_BARS = 150;

export type PreviewChartProps = {
  bars: PreviewBar[];
  forming: PreviewBar | null;
  support: ClassifiedZone | null;
  resistance: ClassifiedZone | null;
  label: string;
};

/** Compact current candles with the nearest structure zones as dashed bounds. */
export default function PreviewChart({ bars, forming, support, resistance, label }: PreviewChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const linesRef = useRef<IPriceLine[]>([]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const chart = createChart(element, {
      width: element.clientWidth || 360, height: 188,
      layout: { background: { color: "#0f151c" }, textColor: "#8fa1b4", fontSize: 10 },
      grid: { vertLines: { color: "#18212b" }, horzLines: { color: "#18212b" } },
      rightPriceScale: { borderColor: "#27323f" },
      timeScale: { borderColor: "#27323f", timeVisible: true, secondsVisible: false, rightOffset: 2,
        tickMarkFormatter: (time: Time) => et.format(new Date(Number(time) * 1000)) },
      localization: { timeFormatter: (time: Time) => `${etDay.format(new Date(Number(time) * 1000))} ${et.format(new Date(Number(time) * 1000))} ET` },
      crosshair: { mode: 0 },
      handleScroll: false, handleScale: false,
    });
    seriesRef.current = chart.addCandlestickSeries({ upColor: "#57c79a", downColor: "#e27d86", borderVisible: false,
      wickUpColor: "#57c79a", wickDownColor: "#e27d86", priceLineVisible: false,
      // Green/red axis labels are reserved for support/resistance bounds.
      lastValueVisible: false });
    chartRef.current = chart;
    const observer = typeof ResizeObserver === "undefined" ? null
      : new ResizeObserver(() => chart.applyOptions({ width: element.clientWidth }));
    observer?.observe(element);
    return () => { observer?.disconnect(); chart.remove(); chartRef.current = null; seriesRef.current = null; linesRef.current = []; };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const data = [...bars, ...(forming ? [forming] : [])].map((bar) => ({ time: bar.time as Time, open: bar.open, high: bar.high, low: bar.low, close: bar.close }));
    series.setData(data);
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: Math.max(0, data.length - VISIBLE_BARS), to: data.length + 1 });
  }, [bars, forming]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    for (const line of linesRef.current) series.removePriceLine?.(line);
    linesRef.current = [];
    const add = (price: number, color: string, title: string) => {
      const line = series.createPriceLine?.({ price, color, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: Boolean(title), title });
      if (line) linesRef.current.push(line);
    };
    if (support) { add(support.upper, SUPPORT, "S"); add(support.lower, SUPPORT, ""); }
    if (resistance) { add(resistance.lower, RESISTANCE, "R"); add(resistance.upper, RESISTANCE, ""); }
  }, [support?.lower, support?.upper, resistance?.lower, resistance?.upper]);

  return <div className="screener-preview-chart" ref={containerRef} role="img" aria-label={label} />;
}
