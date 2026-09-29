import { useQuery } from "@tanstack/react-query";
import type { ScreenerUniverse } from "../../../api/screener";
import { fetchParticipantInstrument, type ParticipantLens } from "../../../api/screenerParticipants";

/** Disclosures change on filing cadence: a slow refresh is enough and never polls per row. */
export const PARTICIPANT_REFRESH_MS = 5 * 60_000;

/**
 * One instrument's lens, for the settled selection only. A response for another
 * instrument, universe, or lens never renders under this identity.
 */
export function useParticipantInstrument({ universe, instrumentId, settledId, lens, compact, enabled = true }: {
  universe: ScreenerUniverse; instrumentId: string | null; settledId: string | null; lens: ParticipantLens; compact: boolean; enabled?: boolean;
}) {
  const ready = Boolean(instrumentId) && settledId === instrumentId;
  const query = useQuery({
    queryKey: ["screener-participants-instrument", universe, settledId, lens, compact ? "compact" : "full"],
    queryFn: ({ signal }) => fetchParticipantInstrument(universe, settledId!, lens, compact, signal),
    enabled: ready && enabled, staleTime: 60_000, retry: 1,
    // Sections still loading from an official source are re-read shortly; settled ones on the slow cadence.
    refetchInterval: (current) => !enabled ? false : current.state.data && ["PENDING", "PARTIAL"].includes(current.state.data.state) ? 15_000 : PARTICIPANT_REFRESH_MS,
  });
  const data = query.data && ready && query.data.instrument.instrument_id === instrumentId && query.data.universe === universe
    && query.data.lens === lens ? query.data : undefined;
  return { query, data, ready };
}
