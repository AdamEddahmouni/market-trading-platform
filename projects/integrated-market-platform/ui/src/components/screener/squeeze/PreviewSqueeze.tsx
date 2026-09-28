import { useQuery } from "@tanstack/react-query";
import type { ScreenerFilter, ScreenerRow } from "../../../api/screener";
import { fetchScreenerSqueeze, type SqueezeMetric } from "../../../api/screenerSqueeze";
import { Coverage, MetricList, StateSummary, WhyListed } from "./SqueezeEvidence";

const select = (items: SqueezeMetric[], ids: string[]) => items.filter((item) => ids.includes(item.id));

export function PreviewSqueeze({ row, settledId, filters, onOpenPanel }:
  { row: ScreenerRow; settledId: string | null; filters: ScreenerFilter[]; onOpenPanel: () => void }) {
  const id = row.instrument.instrument_id;
  const query = useQuery({
    queryKey: ["screener-squeeze", "US_EQUITIES", settledId, "summary", JSON.stringify(filters)],
    queryFn: ({ signal }) => fetchScreenerSqueeze(settledId!, { universe: "US_EQUITIES", view: "summary", filters, signal }),
    enabled: Boolean(settledId) && settledId === id, staleTime: 30_000, retry: 1,
  });
  const data = query.data?.instrument_id === id ? query.data : undefined;
  return <div className="screener-squeeze-preview">
    {!data ? <p className="screener-preview-note">{query.isError ? "Squeeze evidence unavailable." : `Loading ${row.symbol} squeeze evidence…`}</p> : <>
      <StateSummary data={data} />
      <Coverage data={data} />
      <MetricList title="Structural pressure" items={select(data.sections.structural_pressure, ["short_float_pct", "short_ratio", "official_days_to_cover", "borrow_fee", "borrow_available"])} compactMode />
      <MetricList title="Ignition" items={select(data.sections.ignition, ["change_pct", "rel_volume"])} compactMode />
      <MetricList title="Confirmation" items={[...select(data.sections.live_confirmation, ["order_flow_net", "options_call_put_volume"]),
        ...select(data.sections.ignition, ["catalyst"])]} compactMode />
      <WhyListed data={data} />
    </>}
    <button type="button" className="screener-control screener-primary" onClick={onOpenPanel}>Open Short Squeeze Panel</button>
  </div>;
}
