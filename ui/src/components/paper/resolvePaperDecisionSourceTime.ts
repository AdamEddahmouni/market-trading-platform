import { millisToEpochNs } from "./paperSourceTimestamp";

export type ResolvePaperDecisionSourceTimeInput = {
  /** Canonical timestamp from the attention/lane source contract (epoch ns or ms). */
  canonicalSourceTime?: number | null;
  /** Handoff creation time when no canonical source timestamp exists (epoch ns). */
  handoffTime?: number | null;
};

const MAX_SOURCE_TIME = 10_000_000_000_000_000_000;

function parseFinitePositiveInt(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return undefined;
  const truncated = Math.trunc(value);
  if (truncated > MAX_SOURCE_TIME) return undefined;
  return truncated;
}

/**
 * Choose the strongest available truthful source timestamp for Paper decision provenance.
 * Priority: canonical source time → handoff time → absent.
 */
export function resolvePaperDecisionSourceTime(
  input: ResolvePaperDecisionSourceTimeInput,
): number | undefined {
  const canonical = parseFinitePositiveInt(input.canonicalSourceTime);
  if (canonical !== undefined) return canonical;
  const handoff = parseFinitePositiveInt(input.handoffTime);
  if (handoff !== undefined) return handoff;
  return undefined;
}

/** Build handoff-time epoch ns from an injectable wall clock (tests). */
export function handoffTimeFromNow(now: () => number = Date.now): number {
  return millisToEpochNs(now());
}
