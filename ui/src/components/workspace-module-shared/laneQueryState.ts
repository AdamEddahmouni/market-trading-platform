import type { LaneQueryPhase, LaneQueryState } from "./laneModeContentTypes";
import { extractLaneProvenance, extractLaneProvenanceFallback, isLaneDataStale } from "./laneProvenance";

type QueryLike = {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  data?: unknown;
};

export function deriveLaneQueryState(query: QueryLike, laneId?: string): LaneQueryState {
  if (query.isLoading) {
    return { phase: "loading", message: "Loading lane evidence…" };
  }
  if (query.isError) {
    const message =
      query.error instanceof Error ? query.error.message : "Lane evidence request failed.";
    return { phase: "error", message };
  }
  if (!query.data) {
    return { phase: "empty", message: "No lane payload returned." };
  }
  const payload = query.data as { available?: boolean; reason?: string | null };
  const provenance =
    extractLaneProvenance(query.data) ??
    (laneId ? extractLaneProvenanceFallback(query.data, laneId) : null);
  const stale = provenance ? isLaneDataStale(provenance) : false;
  if (payload.available === false) {
    return {
      phase: "ready",
      message: payload.reason ?? "Lane bridge unavailable for this instrument.",
      degraded: true,
      stale,
      provenance: provenance ?? undefined,
    };
  }
  return { phase: "ready", stale, provenance: provenance ?? undefined };
}

export function modeSpecificEmptyMessage(mode: import("../mode-session/types").Mode, phase: LaneQueryPhase): string | undefined {
  if (phase === "loading") return undefined;
  if (mode === "DEMO") return "Replay or fixture evidence is absent — this is not a broker outage.";
  if (mode === "PAPER") return "Simulation can continue read-only; lane evidence is not actionable until data returns.";
  return "Broker-observed lane evidence is unavailable or empty.";
}
