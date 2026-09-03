export type ChartCountPoint = {
  label: string;
  count: number;
};

export function countByLabel(items: Array<{ label: string }>): ChartCountPoint[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const label = item.label || "UNKNOWN";
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([label, count]) => ({ label, count }));
}

export function hasChartData(series: ChartCountPoint[] | undefined): boolean {
  return Boolean(series?.some((row) => row.count > 0));
}
