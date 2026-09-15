import { useEffect, useRef, useState } from "react";
import { applyImpVelaHostTokens } from "./impVelaTheme";
import {
  assertMonotonicBarIdentity,
  type ImpBarRecord,
  toVelaSeries,
  velaTimeframeFromImp,
} from "./impBarIdentity";
import {
  applyImpMarkers,
  removeImpMarkerDrawings,
  type ImpChartMarker,
} from "./impSemanticAnnotations";
import { impBarSeriesFingerprint } from "./workspaceImpBarFeed";
import { loadVelaConstructor, type ImpVelaChartInstance } from "./velaDynamicLoader";

export type ImpVelaChartAdapterProps = {
  bars: ImpBarRecord[];
  markers?: ImpChartMarker[];
  theme?: "dark" | "light";
  className?: string;
  "aria-label"?: string;
};

export function ImpVelaChartAdapter({
  bars,
  markers = [],
  theme = "dark",
  className,
  "aria-label": ariaLabel = "IMP Vela chart",
}: ImpVelaChartAdapterProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ImpVelaChartInstance | null>(null);
  const markerDrawingIdsRef = useRef<string[]>([]);
  const marketFingerprintRef = useRef<string | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    applyImpVelaHostTokens(host);
    let cancelled = false;
    let resizeObserver: ResizeObserver | undefined;
    const initialBars = bars;
    const initialMarkers = markers;
    const timeframe = velaTimeframeFromImp(
      initialBars[0]?.timeframe ?? ("5m" as const),
    );

    void (async () => {
      try {
        assertMonotonicBarIdentity(initialBars);
        const Vela = await loadVelaConstructor();
        if (cancelled) return;

        const chart = new Vela(host, {
          data: toVelaSeries(initialBars),
          timeframe,
          theme,
          live: false,
        });
        await chart.ready();
        if (cancelled) {
          chart.destroy();
          return;
        }

        chartRef.current = chart;
        markerDrawingIdsRef.current = applyImpMarkers(chart, initialMarkers, initialBars);

        resizeObserver = new ResizeObserver(() => {
          chart.resize();
        });
        resizeObserver.observe(host);
        setLoadState("ready");
      } catch {
        if (!cancelled) setLoadState("error");
      }
    })();

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      const chart = chartRef.current;
      if (chart) {
        removeImpMarkerDrawings(chart, markerDrawingIdsRef.current);
        markerDrawingIdsRef.current = [];
        chart.destroy();
        chartRef.current = null;
      }
      setLoadState("loading");
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || loadState !== "ready") return;
    try {
      assertMonotonicBarIdentity(bars);
      const fingerprint = impBarSeriesFingerprint(bars);
      if (marketFingerprintRef.current === fingerprint) return;
      marketFingerprintRef.current = fingerprint;
      // Vela offline host feed: lawful update path is setMarket({ data }) — no per-bar patch API.
      void chart.setMarket({ data: toVelaSeries(bars) });
    } catch {
      setLoadState("error");
    }
  }, [bars, loadState]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || loadState !== "ready") return;
    removeImpMarkerDrawings(chart, markerDrawingIdsRef.current);
    markerDrawingIdsRef.current = applyImpMarkers(chart, markers, bars);
  }, [bars, markers, loadState]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || loadState !== "ready") return;
    chart.setTheme(theme);
  }, [theme, loadState]);

  return (
    <div
      className={className ?? "imp-vela-chart-host"}
      data-imp-vela-state={loadState}
      role="img"
      aria-label={ariaLabel}
    >
      <div ref={hostRef} className="imp-vela-chart-canvas" />
      {loadState === "loading" ? (
        <p className="imp-vela-chart-status" role="status">
          Loading chart engine…
        </p>
      ) : null}
      {loadState === "error" ? (
        <p className="imp-vela-chart-status imp-vela-chart-status-error" role="alert">
          Chart engine failed to load.
        </p>
      ) : null}
    </div>
  );
}
