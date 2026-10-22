import { useCallback, useMemo } from "react";
import type { ScreenerConfig, ScreenerFilter } from "../../api/screener";

type FieldLabels = Record<string, { label?: string; unit?: string }> | undefined;

export function useAvailableFilters(catalog: ScreenerConfig["catalog"] | undefined, universe: string, fields: FieldLabels) {
  return useMemo(() => (catalog ?? [])
    .filter((item) => (item.universes ?? ["US_EQUITIES"]).includes(universe))
    .map((item) => {
      const entry = catalog?.find((candidate) => candidate.field === item.field);
      const own = fields?.[item.field];
      return entry && own?.label ? { ...entry, label: own.label, unit: own.unit ?? entry.unit } : (entry ?? item);
    }), [catalog, universe, fields]);
}

export type ScreenSnapshotInput = {
  filters: ScreenerFilter[]; view: string; sort: string; descending: boolean;
  keys: readonly string[]; visibility: Record<string, boolean>; order: string[];
  sizing: Record<string, number>; pinning: { left?: string[] };
};

export function useScreenSnapshot({ filters, view, sort, descending, keys, visibility, order, sizing, pinning }: ScreenSnapshotInput) {
  const snapshot = useCallback(() => ({ filters, view, sort: { field: sort, descending },
    columns: { visible: keys.filter((key) => visibility[key] !== false), order: order.filter((key) => keys.includes(key)),
      widths: Object.fromEntries(Object.entries(sizing).filter(([key]) => keys.includes(key))),
      pinned: (pinning.left ?? []).filter((key) => keys.includes(key)) } }),
    [filters, view, sort, descending, keys, visibility, order, sizing, pinning]);
  const serialized = useMemo(() => JSON.stringify(snapshot()), [snapshot]);
  return { snapshot, serialized };
}
