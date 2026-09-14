import { CHART_COLORS } from "./chartTheme";
import type { ImpBarRecord } from "./impBarIdentity";
import { impBarOpenMs } from "./impBarIdentity";

/** IMP-owned semantic markers — projected to Vela drawings (not TradingView shapes). */
export type ImpMarkerKind =
  | "opportunity"
  | "catalyst"
  | "options"
  | "paper"
  | "stop"
  | "target";

export type ImpChartMarker = {
  marker_id: string;
  kind: ImpMarkerKind;
  /** References IMP bar_id for time anchoring. */
  bar_id: string;
  price?: number;
  label: string;
};

const KIND_COLOR: Record<ImpMarkerKind, string> = {
  opportunity: "#ff8a00",
  catalyst: CHART_COLORS.warning,
  options: CHART_COLORS.accent,
  paper: CHART_COLORS.long,
  stop: CHART_COLORS.short,
  target: CHART_COLORS.long,
};

export type VelaChartDrawingsHost = {
  drawings: {
    supported: boolean;
    add: (type: string, init: Record<string, unknown>) => { id: string };
    remove: (id: string) => void;
  };
};

export function sampleImpMarkers(bars: ImpBarRecord[]): ImpChartMarker[] {
  if (bars.length === 0) return [];
  const pick = (index: number) => bars[Math.min(index, bars.length - 1)];
  const b20 = pick(20);
  const b45 = pick(45);
  const b70 = pick(70);
  const b90 = pick(90);
  const last = bars[bars.length - 1];
  return [
    {
      marker_id: "opp-1",
      kind: "opportunity",
      bar_id: b20.bar_id,
      label: "Opportunity surfaced",
    },
    {
      marker_id: "cat-1",
      kind: "catalyst",
      bar_id: b45.bar_id,
      label: "Catalyst watch",
    },
    {
      marker_id: "opt-1",
      kind: "options",
      bar_id: b70.bar_id,
      label: "Options flow context",
    },
    {
      marker_id: "paper-1",
      kind: "paper",
      bar_id: b90.bar_id,
      label: "Paper handoff",
    },
    {
      marker_id: "stop-1",
      kind: "stop",
      bar_id: last.bar_id,
      price: last.ohlcv.low - 0.6,
      label: "Stop",
    },
    {
      marker_id: "tgt-1",
      kind: "target",
      bar_id: last.bar_id,
      price: last.ohlcv.high + 0.9,
      label: "Target",
    },
  ];
}

export function applyImpMarkers(
  chart: VelaChartDrawingsHost,
  markers: ImpChartMarker[],
  bars: ImpBarRecord[],
): string[] {
  if (!chart.drawings.supported) return [];
  const byId = new Map(bars.map((b) => [b.bar_id, b]));
  const drawingIds: string[] = [];

  for (const marker of markers) {
    const bar = byId.get(marker.bar_id);
    if (!bar) continue;
    const time = impBarOpenMs(bar);
    const color = KIND_COLOR[marker.kind];

    if (marker.kind === "stop" || marker.kind === "target") {
      if (marker.price == null) continue;
      const line = chart.drawings.add("hline", {
        paneId: "price",
        anchors: [{ time, price: marker.price }],
        style: { lineColor: color, lineWidth: 1 },
      });
      drawingIds.push(line.id);
      const note = chart.drawings.add("text", {
        paneId: "price",
        anchors: [{ time, price: marker.price }],
        text: marker.label,
        style: { color },
      });
      drawingIds.push(note.id);
      continue;
    }

    const callout = chart.drawings.add("callout", {
      paneId: "price",
      anchors: [{ time, price: bar.ohlcv.high }],
      text: `${marker.kind}: ${marker.label}`,
      style: { color, lineColor: color },
    });
    drawingIds.push(callout.id);
  }

  return drawingIds;
}

export function removeImpMarkerDrawings(chart: VelaChartDrawingsHost, drawingIds: string[]): void {
  if (!chart.drawings.supported) return;
  for (const id of drawingIds) chart.drawings.remove(id);
}
