import { useQuery } from "@tanstack/react-query";
import { fetchAiScreenerPreview, type AiScreenerPreview, type AiScreenerScope } from "../../../api/screenerAi";
import type { EngineFit } from "./EngineSwitch";

/**
 * The AI Screener preview for one Screener scope: matched count, cost estimate and whether the packet fits each
 * engine. The strip and the panel read the same cache entry, so they always agree on whether a run can start.
 */
export function useAiScreenerPreview(scope: AiScreenerScope, enabled: boolean) {
  return useQuery({ queryKey: ["screener-ai-screener-preview", JSON.stringify(scope)], queryFn: ({ signal }) => fetchAiScreenerPreview(scope, signal),
    enabled: enabled && scope.settled !== false, staleTime: 30_000, retry: false });
}

/** The selected engine's fit when the server reports that the packet does not fit it, else undefined (fits or unknown). */
export function blockingFit(preview: AiScreenerPreview | undefined, engine?: string | null): EngineFit | undefined {
  const selected = engine ?? preview?.ai?.engine;
  return preview?.engine_fit?.find((fit) => fit.engine === selected && fit.fits === false);
}
