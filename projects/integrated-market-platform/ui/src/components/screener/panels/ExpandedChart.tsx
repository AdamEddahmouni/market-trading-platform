import { useEffect, useRef } from "react";
import { createChart, LineStyle, type IChartApi, type IPriceLine, type ISeriesApi, type Time } from "lightweight-charts";
import type { ChartPayload } from "../../../api/screenerPanels";
import type { ClassifiedZone } from "../srClassify";

const et = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false });
const etDay = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric" });
const SUPPORT = "#4fbf8f";
const RESISTANCE = "#e0707b";
const LIVE = "#8fb8ff";

type Bar = ChartPayload["bars"]["bars"][number];
export type ExpandedChartProps = {
  bars: Bar[];
  forming: Bar | null;
  support: ClassifiedZone | null;
  resistance: ClassifiedZone | null;
  /** Only a live L1 price; a bar close is never drawn as the current price. */
  livePrice: number | null;
  label: string;
  timeZone?: "UTC" | "America/New_York";
  /** Decimal places for the price axis (sub-cent crypto pairs need more than two). */
  precision?: number;
};

/** Expanded candles + volume for the Charts panel; same bars and zones as the Quick Preview. */
export default function ExpandedChart({ bars, forming, support, resistance, livePrice, label, timeZone = "America/New_York", precision = 2 }: ExpandedChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const linesRef = useRef<IPriceLine[]>([]);
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const utc = timeZone === "UTC";
    const time = utc ? new Intl.DateTimeFormat("en-US", { timeZone: "UTC", hour: "2-digit", minute: "2-digit", hour12: false }) : et;
    const day = utc ? new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric" }) : etDay;
    const chart = createChart(element, {
      autoSize: true,
      layout: { background: { color: "#0f151c" }, textColor: "#8fa1b4", fontSize: 10 },
      grid: { vertLines: { color: "#18212b" }, horzLines: { color: "#18212b" } },
      rightPriceScale: { borderColor: "#27323f", scaleMargins: { top: 0.08, bottom: 0.24 } },
      timeScale: { borderColor: "#27323f", timeVisible: true, secondsVisible: false, rightOffset: 3,
        tickMarkFormatter: (value: Time) => time.format(new Date(Number(value) * 1000)) },
      localization: { timeFormatter: (value: Time) => `${day.format(new Date(Number(value) * 1000))} ${time.format(new Date(Number(value) * 1000))} ${utc ? "UTC" : "ET"}` },
      crosshair: { mode: 0 },
    });
    candlesRef.current = chart.addCandlestickSeries({ upColor: "#57c79a", downColor: "#e27d86", borderVisible: false,
      wickUpColor: "#57c79a", wickDownColor: "#e27d86", priceLineVisible: false, lastValueVisible: false,
      priceFormat: { type: "price", precision, minMove: 10 ** -precision } });
    volumeRef.current = chart.addHistogramSeries({ priceScaleId: "volume", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    chartRef.current = chart;
    return () => { chart.remove(); chartRef.current = null; candlesRef.current = null; volumeRef.current = null; linesRef.current = []; };
  }, [timeZone, precision]);
  useEffect(() => {
    const all = [...bars, ...(forming ? [forming] : [])];
    candlesRef.current?.setData(all.map((bar) => ({ time: bar.time as Time, open: bar.open, high: bar.high, low: bar.low, close: bar.close })));
    volumeRef.current?.setData(all.map((bar) => ({ time: bar.time as Time, value: bar.volume ?? 0,
      color: bar === forming ? "#3a4a5c" : bar.close >= bar.open ? "#2f6a55" : "#7a3f47" })));
    chartRef.current?.timeScale().fitContent();
  }, [bars, forming, timeZone, precision]);
  useEffect(() => {
    const series = candlesRef.current;
    if (!series) return;
    for (const line of linesRef.current) series.removePriceLine?.(line);
    linesRef.current = [];
    const add = (price: number, color: string, title: string, style = LineStyle.Dashed) => {
      const line = series.createPriceLine?.({ price, color, lineWidth: 1, lineStyle: style, axisLabelVisible: Boolean(title), title });
      if (line) linesRef.current.push(line);
    };
    if (support) { add(support.upper, SUPPORT, "S"); add(support.lower, SUPPORT, ""); }
    if (resistance) { add(resistance.lower, RESISTANCE, "R"); add(resistance.upper, RESISTANCE, ""); }
    if (livePrice != null) add(livePrice, LIVE, "L1", LineStyle.Solid);
  }, [support?.lower, support?.upper, resistance?.lower, resistance?.upper, livePrice, timeZone, precision]);
  return <div className="screener-expanded-chart" ref={containerRef} role="img" aria-label={label} />;
}
