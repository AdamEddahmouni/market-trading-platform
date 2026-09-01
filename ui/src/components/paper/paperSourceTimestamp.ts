/** Nanosecond threshold — values above this are epoch nanoseconds (backend convention). */
export const EPOCH_NS_THRESHOLD = 1_000_000_000_000_000;

/** Convert persisted epoch (nanoseconds or milliseconds) to JavaScript milliseconds. */
export function epochToMillis(epoch: number | null | undefined): number | null {
  if (epoch === null || epoch === undefined || !Number.isFinite(epoch) || epoch <= 0) {
    return null;
  }
  const truncated = Math.trunc(epoch);
  return truncated > EPOCH_NS_THRESHOLD ? Math.floor(truncated / 1_000_000) : truncated;
}

/** Wall-clock milliseconds to epoch nanoseconds (Paper backend `created_time` convention). */
export function millisToEpochNs(millis: number): number {
  return Math.trunc(millis) * 1_000_000;
}

/**
 * Audit-friendly absolute timestamp in the operator locale/timezone.
 * `source_time` is stored as epoch ns (backend) or epoch ms (legacy fixtures).
 */
export function formatPaperSourceTimeLabel(sourceTime: number | null | undefined): string | null {
  const millis = epochToMillis(sourceTime);
  if (millis === null) return null;
  const date = new Date(millis);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(date);
}
