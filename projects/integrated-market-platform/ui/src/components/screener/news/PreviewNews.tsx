import { useQuery } from "@tanstack/react-query";
import type { ScreenerRow, ScreenerUniverse } from "../../../api/screener";
import { fetchInstrumentNews } from "../../../api/screenerNews";
import { degradedProviders, Headline, newsDayTime, sentimentWord, stateText, StoryTime } from "./newsFormat";
import "./news.css";

type Props = {
  row: ScreenerRow;
  /** The settled selection: arrowing through rows never fetches news for each one. */
  settledId: string | null;
  universe: ScreenerUniverse;
  onOpenNews?: () => void;
};

/** Compact Quick Preview news: newest stories, sentiment line, latest catalyst, provider states. */
export function PreviewNews({ row, settledId, universe, onOpenNews }: Props) {
  const id = row.instrument.instrument_id;
  const query = useQuery({
    queryKey: ["screener-news-instrument", universe, settledId, "compact"],
    queryFn: ({ signal }) => fetchInstrumentNews(universe, settledId!, true, signal),
    enabled: Boolean(settledId) && settledId === id, staleTime: 30_000, refetchInterval: 60_000, retry: 1,
  });
  // Stale-response guard: another instrument's news never renders under this identity.
  const data = query.data && query.data.instrument.instrument_id === id && query.data.universe === universe ? query.data : undefined;
  const catalyst = data ? [...data.catalysts].sort((a, b) => (b.latest_published_at ?? "").localeCompare(a.latest_published_at ?? ""))[0] : undefined;
  const degraded = data ? degradedProviders(data.providers) : [];
  const s = data?.sentiment;
  return <section className="news-preview" aria-label={`News for ${row.symbol}`}>
    {!data ? <p className="screener-preview-note" role={query.isError ? "alert" : "status"}>{query.isError
      ? <>News unavailable for {row.symbol}. <button type="button" onClick={() => void query.refetch()}>Retry</button></> : `Loading ${row.symbol} news…`}</p> : <>
      <p className="screener-preview-meta">{data.instrument.symbol} · {data.instrument.label} · last {data.window.id} · {data.coverage.story_count} stories</p>
      {(data.state === "NOT_CONFIGURED" || data.state === "UNAVAILABLE") && <p className="screener-preview-note">News {data.state === "NOT_CONFIGURED" ? "providers are not configured" : "is unavailable"}{data.reason ? ` · ${data.reason}` : ""}; this is not an absence of news.</p>}
      {data.stories.length ? <ol className="news-preview-list">{data.stories.slice(0, 5).map((story) => <li key={story.story_id}>
        <StoryTime story={story} universe={data.universe} /> · <span className="news-publisher">{story.sources[0]?.publisher ?? "—"}</span>
        {story.source_count > 1 ? <small> · {story.source_count} sources</small> : null}<br /><Headline story={story} /></li>)}</ol>
        : data.state !== "NOT_CONFIGURED" && data.state !== "UNAVAILABLE" && <p className="screener-preview-note">No matched stories in this window from current providers.</p>}
      <p className="screener-preview-meta">Sentiment (language, not a forecast): {!s || s.state === "NOT_CONFIGURED" ? "model not configured"
        : s.state === "UNAVAILABLE" ? "unavailable" : s.state === "INSUFFICIENT_DATA" ? `insufficient data · ${s.scored} scored`
        : `${s.counts.positive} positive · ${s.counts.neutral} neutral · ${s.counts.negative} negative · ${s.unscored} unscored${s.dominant ? ` · dominant ${sentimentWord(s.dominant).toLowerCase()}` : ""}`}</p>
      <p className="screener-preview-meta">Latest catalyst: {catalyst ? `${catalyst.category.label} · ${newsDayTime(catalyst.latest_published_at, data.universe)}` : "none categorized"}</p>
      <p className="screener-preview-meta">Providers: {data.providers.map((item) => `${item.label} ${stateText(item.state)}`).join(" · ")}{degraded.length ? ` (${degraded.length} not current)` : ""}</p>
    </>}
    <button type="button" className="screener-control screener-primary" onClick={() => onOpenNews?.()}>Open News &amp; Analysis</button>
  </section>;
}
