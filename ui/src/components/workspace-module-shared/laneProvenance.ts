import { epochToMillis, formatPaperSourceTimeLabel } from "../paper/paperSourceTimestamp";

export type LaneSourceKind = "lane_payload" | "context_as_of" | "retrieved_at" | "unknown";

export type LaneProvenance = {
  lane_id: string;
  source_kind: LaneSourceKind;
  source_time?: number;
  retrieved_at: number;
};

const SOURCE_KIND_LABEL: Record<LaneSourceKind, string> = {
  lane_payload: "Lane data time",
  context_as_of: "Session as-of time",
  retrieved_at: "Retrieved at",
  unknown: "Source time unavailable",
};

export function isLaneProvenance(value: unknown): value is LaneProvenance {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return typeof row.lane_id === "string" && typeof row.source_kind === "string" && typeof row.retrieved_at === "number";
}

/** Extract server-attached lane provenance from a workspace/explore payload. */
export function extractLaneProvenance(data: unknown): LaneProvenance | null {
  if (!data || typeof data !== "object") return null;
  const row = (data as Record<string, unknown>).lane_provenance;
  if (!isLaneProvenance(row)) return null;
  return row;
}

/** Best-effort client-side extraction when server envelope is absent (legacy fixtures). */
export function extractLaneProvenanceFallback(data: unknown, laneId: string): LaneProvenance | null {
  const attached = extractLaneProvenance(data);
  if (attached) return attached;
  if (!data || typeof data !== "object") return null;
  const payload = data as Record<string, unknown>;
  const asOfContext = payload.as_of_context;
  const contextAsOf =
    asOfContext && typeof asOfContext === "object"
      ? (asOfContext as Record<string, unknown>).as_of_time
      : undefined;
  const candidates = [
    payload.observation_time,
    payload.source_time,
    payload.as_of_time,
    payload.as_of,
    payload.as_of_ns,
    contextAsOf,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "number" && Number.isFinite(candidate) && candidate > 0) {
      return {
        lane_id: laneId,
        source_kind: "lane_payload",
        source_time: Math.trunc(candidate),
        retrieved_at: Date.now() * 1_000_000,
      };
    }
    if (typeof candidate === "string" && candidate.trim()) {
      const millis = Date.parse(candidate);
      if (!Number.isNaN(millis)) {
        return {
          lane_id: laneId,
          source_kind: typeof contextAsOf === "string" && candidate === contextAsOf ? "context_as_of" : "lane_payload",
          source_time: millis * 1_000_000,
          retrieved_at: Date.now() * 1_000_000,
        };
      }
    }
  }
  return {
    lane_id: laneId,
    source_kind: "unknown",
    retrieved_at: Date.now() * 1_000_000,
  };
}

export function formatLaneSourceTimeLabel(provenance: LaneProvenance | null | undefined): string | null {
  if (!provenance?.source_time) return null;
  return formatPaperSourceTimeLabel(provenance.source_time);
}

export function laneSourceKindLabel(kind: LaneSourceKind): string {
  return SOURCE_KIND_LABEL[kind] ?? SOURCE_KIND_LABEL.unknown;
}

/** Stale when source time is materially older than retrieval (5 minutes). */
export function isLaneDataStale(provenance: LaneProvenance | null | undefined, staleThresholdMs = 5 * 60 * 1000): boolean {
  if (!provenance?.source_time) return false;
  const sourceMs = epochToMillis(provenance.source_time);
  const retrievedMs = epochToMillis(provenance.retrieved_at);
  if (sourceMs === null || retrievedMs === null) return false;
  return retrievedMs - sourceMs > staleThresholdMs;
}

export function laneProvenanceSummary(provenance: LaneProvenance | null | undefined): string | null {
  if (!provenance) return null;
  const label = formatLaneSourceTimeLabel(provenance);
  if (!label) {
    return provenance.source_kind === "unknown"
      ? "Source time unavailable for this lane payload."
      : null;
  }
  const kind = laneSourceKindLabel(provenance.source_kind);
  const stale = isLaneDataStale(provenance);
  return stale ? `${kind}: ${label} (may be stale)` : `${kind}: ${label}`;
}
