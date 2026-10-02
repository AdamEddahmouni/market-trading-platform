/** Fetch whole overlapping coarse buckets so replacing them cannot drop edge prints. */
export function flowDetailWindow(from: number, to: number, points: readonly { time_ms: number; end_ms: number }[]) {
  const overlapping = points.filter(p => p.end_ms > from && p.time_ms < to);
  return {
    start: Math.min(from, ...overlapping.map(p => p.time_ms)),
    end: Math.max(to, ...overlapping.map(p => p.end_ms)),
  };
}
