import type { WorkspaceEvidenceLane } from "../../api/schemas";
import type { ImpBarRecord } from "./impBarIdentity";
import type { ImpChartMarker, ImpMarkerKind } from "./impSemanticAnnotations";

function laneToMarkerKind(lane: WorkspaceEvidenceLane): ImpMarkerKind | null {
  const haystack = `${lane.lane} ${lane.evidence_type} ${lane.summary}`.toUpperCase();
  if (haystack.includes("OPPORTUNITY")) return "opportunity";
  if (haystack.includes("SEC") || haystack.includes("FILING") || haystack.includes("PUBLIC")) {
    return "sec_public_record";
  }
  if (haystack.includes("CATALYST") || haystack.includes("NEWS")) return "catalyst";
  if (haystack.includes("AGENT") || haystack.includes("VERIF")) return "agent_verification";
  if (haystack.includes("CONTRAD") || haystack.includes("CONFLICT")) return "contradiction";
  if (haystack.includes("PAPER") || haystack.includes("FILL")) return "paper";
  return null;
}

function anchorBarId(bars: ImpBarRecord[], availableTimeNs: number | null): string | null {
  if (bars.length === 0 || availableTimeNs == null) {
    return bars.length > 0 ? bars[bars.length - 1].bar_id : null;
  }
  let best = bars[0];
  let bestDelta = Math.abs(best.available_time_ns - availableTimeNs);
  for (const bar of bars) {
    const delta = Math.abs(bar.available_time_ns - availableTimeNs);
    if (delta < bestDelta) {
      best = bar;
      bestDelta = delta;
    }
  }
  return best.bar_id;
}

function parseLaneAvailableNs(lane: WorkspaceEvidenceLane): number | null {
  if (!lane.available_time) return null;
  const ms = Date.parse(lane.available_time);
  if (!Number.isFinite(ms)) return null;
  return ms * 1_000_000;
}

/** Project workspace evidence lanes to IMP semantic markers (identity owned by IMP). */
export function projectWorkspaceEvidenceMarkers(
  lanes: WorkspaceEvidenceLane[],
  bars: ImpBarRecord[],
): ImpChartMarker[] {
  const markers: ImpChartMarker[] = [];
  for (const lane of lanes) {
    const kind = laneToMarkerKind(lane);
    if (!kind) continue;
    const barId = anchorBarId(bars, parseLaneAvailableNs(lane));
    if (!barId) continue;
    const markerId = `ws-${lane.lane}-${lane.evidence_type}-${barId}`;
    markers.push({
      marker_id: markerId,
      kind,
      bar_id: barId,
      label: lane.summary.slice(0, 120),
    });
  }
  return markers;
}

export function projectPaperStopTargetMarkers(
  bars: ImpBarRecord[],
  stopPrice?: number,
  targetPrice?: number,
): ImpChartMarker[] {
  const last = bars.length > 0 ? bars[bars.length - 1] : undefined;
  if (!last) return [];
  const markers: ImpChartMarker[] = [];
  if (stopPrice != null) {
    markers.push({
      marker_id: `paper-stop-${last.bar_id}`,
      kind: "stop",
      bar_id: last.bar_id,
      price: stopPrice,
      label: "Paper stop",
    });
  }
  if (targetPrice != null) {
    markers.push({
      marker_id: `paper-target-${last.bar_id}`,
      kind: "target",
      bar_id: last.bar_id,
      price: targetPrice,
      label: "Paper target",
    });
  }
  return markers;
}
