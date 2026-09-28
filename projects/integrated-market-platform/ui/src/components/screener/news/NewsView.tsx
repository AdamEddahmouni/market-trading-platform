import { useEffect, useMemo, useRef } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { ScreenerUniverse } from "../../../api/screener";
import { fetchScreenerNews, NEWS_PAGE_LIMIT, NEWS_SORTS, NEWS_WINDOWS, type NewsBrief, type NewsFeed, type NewsMatch,
  type NewsStory, type NewsWindowId, type ProviderStatus } from "../../../api/screenerNews";
import { degradedProviders, Headline, humanize, MatchChip, newsDayTime, ProviderStrip, SentimentCell, stateText, StorySources,
  StoryTime, TypeBadge } from "./newsFormat";
import "./news.css";

const WINDOW_LABELS: Record<NewsWindowId, string> = { "1h": "Last 1h", "4h": "Last 4h", "24h": "Last 24h", "72h": "Last 72h" };
const SENTIMENTS = [{ id: "POSITIVE", label: "Positive" }, { id: "NEUTRAL", label: "Neutral" }, { id: "NEGATIVE", label: "Negative" }];
const PREFETCH_ROWS = 30;
const REFRESH_MS = 60_000;
// Dense rows: further matches stay available on hover and in the instrument filter.
const MAX_CHIPS = 3;

type Props = {
  universe: ScreenerUniverse;
  universeLabel: string;
  /** The current location.search; News state lives in the URL. */
  search: string;
  onUpdate: (updates: Record<string, string | null>) => void;
};

function parse(search: string) {
  const params = new URLSearchParams(search);
  const win = params.get("nwin");
  const sort = params.get("nsort");
  return {
    window: (NEWS_WINDOWS as readonly string[]).includes(win ?? "") ? win as NewsWindowId : "24h" as NewsWindowId,
    sort: (NEWS_SORTS as readonly string[]).includes(sort ?? "") ? sort : null,
    source: params.get("nsrc"), category: params.get("ncat"), sentiment: params.get("nsent"), instrument: params.get("ninst"),
    brief: params.get("nbrief") === "1",
  };
}

function Notice({ feed, universeLabel }: { feed: NewsFeed; universeLabel: string }) {
  const degraded = degradedProviders(feed.providers);
  const list = (items: ProviderStatus[]) => items.map((item) => `${item.label} (${stateText(item.state)}${item.reason ? ` · ${item.reason}` : ""})`).join("; ");
  if (feed.state === "NOT_CONFIGURED" || feed.state === "UNAVAILABLE") {
    return <div className="news-notice error" role="alert">
      <strong>{feed.state === "NOT_CONFIGURED" ? `News providers are not configured for ${universeLabel}` : `News is unavailable for ${universeLabel}`}</strong>
      <span>{feed.reason ? `${humanize(feed.reason)}. ` : ""}This is a provider state, not an absence of news. {degraded.length ? `Missing: ${list(degraded)}.` : ""}</span>
    </div>;
  }
  if (feed.state === "PARTIAL" && degraded.length) {
    return <div className="news-notice warn" role="status"><strong>Partial coverage</strong>
      <span>Stories below come only from current providers. Not current: {list(degraded)}.</span></div>;
  }
  if (feed.state === "PENDING") return <div className="news-notice" role="status"><strong>Providers pending</strong><span>Some providers have not reported yet; the feed will refresh.</span></div>;
  return null;
}

function Brief({ brief, providers, universe }: { brief: NewsBrief; providers: ProviderStatus[]; universe: ScreenerUniverse }) {
  const label = (id: string) => providers.find((item) => item.id === id)?.label ?? id;
  return <section className="news-brief" aria-label="News brief">
    <h2>Brief <span className="news-class">DERIVED</span></h2>
    <p className="news-meta">{brief.story_count} stories · {brief.headline_count} headlines · {brief.source_count} sources · {WINDOW_LABELS[brief.window.id]} · generated {newsDayTime(brief.generated_at, universe)}</p>
    <p className="news-meta">{brief.coverage_note}</p>
    {brief.missing_providers.length > 0 && <p className="news-meta">Missing providers: {brief.missing_providers.map(label).join(", ")}</p>}
    {brief.groups.length ? <table className="news-table-plain"><caption className="sr-only">Stories by category</caption>
      <thead><tr><th scope="col">Category</th><th scope="col">Group</th><th scope="col">Stories</th><th scope="col">Sources</th><th scope="col">Latest</th></tr></thead>
      <tbody>{brief.groups.map((group) => <tr key={group.category.id}><th scope="row">{group.category.label}</th><td>{humanize(group.category.group)}</td>
        <td>{group.story_count}</td><td>{group.source_count}</td><td>{newsDayTime(group.latest_published_at, universe)}</td></tr>)}</tbody></table>
      : <p className="news-meta">No categorized stories in this window.</p>}
    <p className="news-meta">Uncategorized stories: {brief.uncategorized_count}</p>
    <p className="news-meta">Method: {brief.method.replace(/\.$/, "")}. Deterministic grouping of headlines; not a forecast.</p>
  </section>;
}

export default function NewsView({ universe, universeLabel, search, onUpdate }: Props) {
  const state = parse(search);
  const scrollRef = useRef<HTMLDivElement>(null);
  const view = state.brief ? "brief" as const : "feed" as const;
  const query = useInfiniteQuery({
    queryKey: ["screener-news", universe, state.window, state.sort, state.source, state.category, state.sentiment, state.instrument, view],
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => fetchScreenerNews({ universe, window: state.window, sort: state.sort, source: state.source,
      category: state.category, sentiment: state.sentiment, instrument: state.instrument, offset: pageParam, limit: NEWS_PAGE_LIMIT, view }, signal),
    getNextPageParam: (last) => last.has_more ? last.offset + last.stories.length : undefined,
    staleTime: 30_000, refetchInterval: REFRESH_MS,
    // Controls stay stable while a filter change loads; another universe's stories are never shown.
    placeholderData: (previous) => previous && previous.pages[0]?.universe === universe ? previous : undefined,
  });
  const first = query.data?.pages[0];
  const stories = useMemo(() => {
    const seen = new Set<string>();
    const merged: NewsStory[] = [];
    for (const page of query.data?.pages ?? []) for (const story of page.stories) {
      if (seen.has(story.story_id)) continue;
      seen.add(story.story_id); merged.push(story);
    }
    return merged;
  }, [query.data]);
  const loaderRow = query.hasNextPage ? 1 : 0;
  const virtualizer = useVirtualizer({ count: view === "feed" ? stories.length + loaderRow : 0, getScrollElement: () => scrollRef.current,
    estimateSize: () => 30, overscan: 8 });
  const virtualRows = virtualizer.getVirtualItems();
  const lastVirtual = virtualRows.length ? virtualRows[virtualRows.length - 1].index : -1;
  useEffect(() => {
    if (!query.hasNextPage || query.isFetchingNextPage || query.isFetchNextPageError || query.isRefetching) return;
    if (lastVirtual >= stories.length - PREFETCH_ROWS) void query.fetchNextPage();
  }, [lastVirtual, stories.length, query.hasNextPage, query.isFetchingNextPage, query.isFetchNextPageError, query.isRefetching]);

  const instrumentSymbol = useMemo(() => {
    if (!state.instrument) return null;
    for (const story of stories) for (const match of story.matches) if (match.instrument_id === state.instrument) return match.symbol;
    return state.instrument;
  }, [state.instrument, stories]);
  const filterInstrument = (match: NewsMatch) => { if (match.instrument_id) onUpdate({ ninst: match.instrument_id }); };
  const filters = first?.filters;
  const sentimentEnabled = filters?.sentiment.enabled ?? false;
  const sentimentReason = filters && !filters.sentiment.enabled
    ? `Sentiment filter unavailable${filters.sentiment.reason ? ` · ${humanize(filters.sentiment.reason)}` : ""}` : undefined;

  return <div className="news-view" aria-label={`${universeLabel} news`} role="region">
    <div className="news-controls">
      <label>Window <select aria-label="News window" value={state.window} onChange={(event) => onUpdate({ nwin: event.target.value === "24h" ? null : event.target.value })}>
        {NEWS_WINDOWS.map((id) => <option key={id} value={id}>{WINDOW_LABELS[id]}</option>)}</select></label>
      <label>Sort <select aria-label="News sort" value={first?.sort ?? state.sort ?? ""} disabled={!first}
        onChange={(event) => onUpdate({ nsort: event.target.value })}>
        {!first && <option value={state.sort ?? ""}>{state.sort ?? "—"}</option>}
        {first?.sorts.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <label>Source <select aria-label="News source" value={state.source ?? ""} disabled={!filters} onChange={(event) => onUpdate({ nsrc: event.target.value || null })}>
        <option value="">All sources</option>
        {filters?.sources.map((item) => <option key={item.id} value={item.id}>{item.label} ({item.count})</option>)}</select></label>
      <label>Category <select aria-label="News category" value={state.category ?? ""} disabled={!filters} onChange={(event) => onUpdate({ ncat: event.target.value || null })}>
        <option value="">All categories</option>
        {filters?.categories.map((item) => <option key={item.id} value={item.id}>{item.label} ({item.count})</option>)}</select></label>
      <label title={sentimentReason}>Sentiment <select aria-label="News sentiment" value={sentimentEnabled ? state.sentiment ?? "" : ""} disabled={!sentimentEnabled}
        aria-describedby={sentimentReason ? "news-sentiment-reason" : undefined} onChange={(event) => onUpdate({ nsent: event.target.value || null })}>
        <option value="">Any language</option>
        {SENTIMENTS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      {sentimentReason && <span id="news-sentiment-reason" className="news-meta">{sentimentReason}</span>}
      <button type="button" className="screener-control" aria-pressed={state.brief} onClick={() => onUpdate({ nbrief: state.brief ? null : "1" })}>Brief</button>
      {state.instrument && <span className="screener-chip news-instrument-filter"><span className="news-chip-label">Instrument: {instrumentSymbol}</span>
        <button type="button" aria-label={`Remove instrument filter ${instrumentSymbol}`} onClick={() => onUpdate({ ninst: null })}>×</button></span>}
    </div>
    {first && <div className="news-status-strip">
      <ProviderStrip providers={first.providers} />
      <span className={`news-provider state-${first.sentiment_model.state.toLowerCase()}`}
        title={[first.sentiment_model.reason ? `Reason: ${first.sentiment_model.reason}` : null, first.sentiment_model.model_id,
          first.sentiment_model.model_revision ? `rev ${first.sentiment_model.model_revision}` : null].filter(Boolean).join(" · ") || undefined}>
        <span>Sentiment model</span> <strong>{stateText(first.sentiment_model.state)}</strong>{first.sentiment_model.model_id ? <small> · {first.sentiment_model.model_id}</small> : null}</span>
    </div>}
    {first && <Notice feed={first} universeLabel={universeLabel} />}
    {query.isPlaceholderData && <div className="news-notice" role="status">Updating for the new window or filters…</div>}
    {query.isPending ? <div className="news-message" role="status">Loading {universeLabel} news…</div>
      : query.isError && !first ? <div className="news-message error" role="alert"><strong>News request failed.</strong>
        <button type="button" className="screener-control" onClick={() => void query.refetch()}>Retry</button></div>
      : !first ? null
      : view === "brief" ? (first.brief ? <Brief brief={first.brief} providers={first.providers} universe={universe} />
        : query.isPlaceholderData ? null : <div className="news-message" role="status">Brief unavailable for this window.</div>)
      : stories.length === 0 ? (first.state === "NOT_CONFIGURED" || first.state === "UNAVAILABLE" ? null
        : <div className="news-message" role="status">No stories in this window from current providers.</div>)
      : <div className="news-feed" role="table" aria-label={`${universeLabel} news feed`} aria-rowcount={first.result_count + 1} ref={scrollRef} tabIndex={0}>
        <div className="news-row news-head" role="row">
          {["Time", "Instruments", "Headline", "Source", "Category", "Sentiment", "Type"].map((name) => <span key={name} role="columnheader">{name}</span>)}
        </div>
        <div className="news-virtual" style={{ height: virtualizer.getTotalSize() }}>
          {virtualRows.map((virtual) => {
            if (virtual.index === stories.length) {
              return <div key="news-more" role="row" className="news-row news-more" style={{ transform: `translateY(${virtual.start}px)` }}>
                <span role="cell">{query.isFetchNextPageError ? <>Could not load more stories <button type="button" onClick={() => void query.fetchNextPage()}>Retry</button></>
                  : <span role="status">Loading more stories…</span>}</span></div>;
            }
            const story = stories[virtual.index];
            if (!story) return null;
            return <div key={story.story_id} role="row" data-index={virtual.index} ref={virtualizer.measureElement} aria-rowindex={virtual.index + 2}
              className="news-row" style={{ transform: `translateY(${virtual.start}px)` }}>
              <span role="cell"><StoryTime story={story} universe={universe} /></span>
              <span role="cell" className="news-matches">{story.matches.length ? <>{story.matches.slice(0, MAX_CHIPS).map((match, index) =>
                <MatchChip key={`${match.symbol}-${index}`} match={match} onFilter={filterInstrument} />)}
                {story.matches.length > MAX_CHIPS && <span className="news-chip more" title={story.matches.slice(MAX_CHIPS).map((match) => `${match.symbol} (${match.confidence.toLowerCase()})`).join(", ")}>
                  +{story.matches.length - MAX_CHIPS}</span>}</> : <span className="news-muted">—</span>}</span>
              <span role="cell" className="news-headline-cell"><Headline story={story} /></span>
              <span role="cell"><StorySources story={story} universe={universe} /></span>
              <span role="cell" className="news-categories" title={story.categories.map((item) => item.label).join(", ") || "Uncategorized"}>
                {story.categories.length ? story.categories.map((item) => item.label).join(", ") : "—"}</span>
              <span role="cell"><SentimentCell sentiment={story.sentiment} /></span>
              <span role="cell"><TypeBadge type={story.source_type} /></span>
            </div>;
          })}
        </div>
      </div>}
    {first && <footer className="news-footer" aria-label="News counts">
      <span>{first.result_count.toLocaleString()} stories · {first.headline_count.toLocaleString()} headlines · {stories.length.toLocaleString()} loaded</span>
      <span>{WINDOW_LABELS[first.window.id]} · refreshed {newsDayTime(first.generated_at, universe)}</span>
      <span>Categories, instrument matches, and sentiment are derived; sentiment describes headline language, not a forecast.</span>
    </footer>}
  </div>;
}
