import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import type { ScreenerUniverse } from "../../../api/screener";
import { fetchInstrumentNews, postNewsSynthesis, type InstrumentNews, type NewsAnalysisItem, type NewsStory, type NewsSynthesis,
  type SynthesisRefItem } from "../../../api/screenerNews";
import { degradedProviders, Headline, humanize, newsDayTime, ProviderStrip, SentimentCell, sentimentWord, stateText, StorySources,
  StoryTime, TypeBadge } from "../news/newsFormat";
import { PanelFrame, PanelMessage, selectionGate, usePanelVisible, useSelection } from "./shared";
import "../news/news.css";

const REFRESH_MS = 60_000;

function Section({ title, children, derived = false }: { title: string; children: React.ReactNode; derived?: boolean }) {
  return <section className="news-panel-section" aria-label={title}>
    <h3>{title}{derived ? <span className="news-class">DERIVED</span> : null}</h3>{children}</section>;
}

function Headlines({ data }: { data: InstrumentNews }) {
  if (!data.stories.length) return <p className="screener-panel-note">No stories matched {data.instrument.symbol} in the last {data.window.id} from current providers.</p>;
  return <ol className="news-panel-feed" aria-label={`Latest headlines for ${data.instrument.symbol}`}>{data.stories.map((story) =>
    <li key={story.story_id}><StoryTime story={story} universe={data.universe} /><Headline story={story} /><TypeBadge type={story.source_type} />
      <StorySources story={story} universe={data.universe} /><SentimentCell sentiment={story.sentiment} /></li>)}</ol>;
}

function Sentiment({ data }: { data: InstrumentNews }) {
  const s = data.sentiment;
  const note = <p className="screener-panel-note">Describes the language of matched headlines; it is not a forecast of price direction. Method: {s.method.replace(/\.$/, "")}.</p>;
  if (s.state === "NOT_CONFIGURED") return <><p className="screener-panel-note">Sentiment model not configured{s.reason ? ` · ${s.reason}` : ""}. Headlines are not scored.</p>{note}</>;
  if (s.state === "UNAVAILABLE") return <><p className="screener-panel-note">Sentiment unavailable{s.reason ? ` · ${s.reason}` : ""}.</p>{note}</>;
  return <>
    {s.state === "INSUFFICIENT_DATA" && <p className="screener-panel-note">Insufficient data: too few scored headlines to summarize{s.reason ? ` · ${s.reason}` : ""}.</p>}
    {s.state === "PARTIAL" && <p className="screener-panel-note">Partial: some headlines are not scored{s.reason ? ` · ${s.reason}` : ""}.</p>}
    <dl className="news-panel-list">
      <div><dt>Positive</dt><dd>{s.counts.positive}</dd></div>
      <div><dt>Neutral</dt><dd>{s.counts.neutral}</dd></div>
      <div><dt>Negative</dt><dd>{s.counts.negative}</dd></div>
      <div><dt>Scored / unscored</dt><dd>{s.scored} / {s.unscored}</dd></div>
      <div><dt>Dominant language</dt><dd>{s.dominant ? sentimentWord(s.dominant) : "—"}</dd></div>
      <div><dt>Latest scored</dt><dd>{s.latest ? `${sentimentWord(s.latest.label)} · ${newsDayTime(s.latest.published_at, data.universe)}` : "—"}</dd></div>
      <div><dt>Model</dt><dd>{s.model_id ?? "—"}</dd></div>
    </dl>{note}</>;
}

function Catalysts({ data }: { data: InstrumentNews }) {
  if (!data.catalysts.length) return <p className="screener-panel-note">No categorized events among matched stories.</p>;
  return <table className="news-table-plain"><thead><tr><th scope="col">Category</th><th scope="col">Stories</th><th scope="col">Latest</th></tr></thead>
    <tbody>{data.catalysts.map((item) => <tr key={item.category.id}><th scope="row">{item.category.label}</th><td>{item.story_count}</td>
      <td>{newsDayTime(item.latest_published_at, data.universe)}</td></tr>)}</tbody></table>;
}

function Attention({ data }: { data: InstrumentNews }) {
  const a = data.attention;
  return <>
    {a.state !== "CURRENT" && <p className="screener-panel-note">Attention {stateText(a.state)}{a.reason ? ` · ${a.reason}` : ""}.</p>}
    {a.windows.length > 0 && <table className="news-table-plain"><thead><tr><th scope="col">Window</th><th scope="col">Headlines</th>
      <th scope="col">Stories</th><th scope="col">Prior window headlines</th></tr></thead>
      <tbody>{a.windows.map((item) => <tr key={item.id}><th scope="row">{item.id}</th><td>{item.headline_count}</td><td>{item.story_count}</td>
        <td title={item.prior_headline_count == null ? "Prior window not observed" : undefined}>{item.prior_headline_count ?? "unknown"}</td></tr>)}</tbody></table>}
    <p className="screener-panel-note">Independent sources {a.independent_sources} · latest {newsDayTime(a.latest_published_at, data.universe)} · method: {a.method}</p>
  </>;
}

function Reaction({ data }: { data: InstrumentNews }) {
  const r = data.reaction;
  const headline = (id: string) => data.stories.find((story) => story.story_id === id)?.headline ?? id;
  return <>
    <p className="screener-panel-note">{r.note}</p>
    {r.state === "NOT_SUPPORTED" ? <p className="screener-panel-note">Not supported for this instrument{r.reason ? ` · ${r.reason}` : ""}.</p>
      : r.state === "UNAVAILABLE" ? <p className="screener-panel-note">Unavailable{r.reason ? ` · ${r.reason}` : ""}.</p>
      : !r.items.length ? <p className="screener-panel-note">No timed headlines to measure.</p>
      : <table className="news-table-plain"><caption className="sr-only">Price change after each headline ({r.basis.replace(/\.$/, "")}{r.timeframe ? `, ${r.timeframe} bars` : ""})</caption>
        <thead><tr><th scope="col">Headline</th><th scope="col">Published</th><th scope="col">Reference</th>
          {["+5m", "+15m", "+1h"].map((id) => <th key={id} scope="col">{id}</th>)}</tr></thead>
        <tbody>{r.items.map((item) => <tr key={item.story_id}><th scope="row" className="news-ellipsis" title={headline(item.story_id)}>{headline(item.story_id)}</th>
          <td>{newsDayTime(item.published_at, data.universe)}</td><td>{item.reference ? item.reference.price : "—"}</td>
          {["+5m", "+15m", "+1h"].map((id) => {
            const horizon = item.horizons.find((entry) => entry.id === id);
            const text = !horizon ? "—" : horizon.state === "PENDING" ? "pending" : horizon.state === "UNAVAILABLE" || horizon.change_pct == null ? "—"
              : `${horizon.change_pct > 0 ? "+" : ""}${horizon.change_pct.toFixed(2)}%`;
            return <td key={id} title={horizon ? `${humanize(horizon.state)}${horizon.bar_end ? ` · bar end ${horizon.bar_end}` : ""}` : "Not measured"}>{text}</td>;
          })}</tr>)}</tbody></table>}
  </>;
}

function AnalysisGroup({ title, items }: { title: string; items: NewsAnalysisItem[] }) {
  return <div className={`news-analysis-group ${title.toLowerCase().replace(/\s+/g, "-")}`}>
    <h4>{title}</h4>
    {items.length ? <ul>{items.map((item, index) => <li key={`${item.source}-${index}`} title={`${item.source}${item.as_of ? ` · ${item.as_of}` : ""}`}>{item.text}</li>)}</ul>
      : <p className="screener-panel-note">None.</p>}
  </div>;
}

function Refs({ refs, stories }: { refs: string[]; stories: NewsStory[] }) {
  if (!refs.length) return null;
  return <span className="news-refs">Sources: {refs.map((ref, index) => {
    const story = stories.find((item) => item.story_id === ref);
    return <span key={ref}>{index ? "; " : ""}{story ? story.url ? <a href={story.url} target="_blank" rel="noopener noreferrer">{story.headline}</a> : story.headline
      : <span className="news-muted">story {ref} not in the loaded feed</span>}</span>;
  })}</span>;
}

function SynthesisBlock({ result, stories, universe }: { result: NewsSynthesis; stories: NewsStory[]; universe: ScreenerUniverse }) {
  const label = `AI synthesis · model ${result.model_id ?? "unknown"} · generated ${newsDayTime(result.generated_at, universe)}`;
  if (result.state !== "CURRENT" || !result.synthesis) {
    return <p className="screener-panel-note" role="status">{label} · {humanize(result.state)}{result.reason ? ` · ${result.reason}` : ""}.</p>;
  }
  const s = result.synthesis;
  const refList = (title: string, items: SynthesisRefItem[]) => <div className="news-ai-block">
    <p className="news-ai-label">{label}</p><h4>{title}</h4>
    {items.length ? <ul>{items.map((item, index) => <li key={index}>{item.text} <Refs refs={item.refs} stories={stories} /></li>)}</ul>
      : <p className="screener-panel-note">None stated.</p>}</div>;
  return <div className="news-ai" aria-label="AI synthesis result">
    <div className="news-ai-block"><p className="news-ai-label">{label}</p><h4>Summary</h4><p>{s.summary}</p></div>
    {refList("Observed facts", s.observed_facts)}
    {refList("Derived context", s.derived_context)}
    <div className="news-ai-block"><p className="news-ai-label">{label}</p><h4>Uncertainties</h4>
      {s.uncertainties.length ? <ul>{s.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="screener-panel-note">None stated.</p>}</div>
    {refList("Conflicting evidence", s.conflicting_evidence)}
    {refList("Potential market relevance", s.potential_market_relevance)}
    <p className="screener-panel-note">Coverage: {result.coverage.story_count} stories · {result.coverage.source_count} sources{result.coverage.missing_providers.length ? ` · missing ${result.coverage.missing_providers.join(", ")}` : ""} · prompt {result.prompt_id} v{result.prompt_version}{result.cache ? ` · cache ${result.cache.toLowerCase()}` : ""}. AI output is a synthesis of the listed headlines, not verified fact or advice.</p>
  </div>;
}

function Synthesis({ data }: { data: InstrumentNews }) {
  const key = `${data.universe}|${data.instrument.instrument_id}`;
  const current = useRef(key);
  current.current = key;
  const [result, setResult] = useState<{ key: string; value: NewsSynthesis } | null>(null);
  const [status, setStatus] = useState<{ key: string; state: "running" | "error" } | null>(null);
  useEffect(() => { setResult(null); setStatus(null); }, [key]);
  useEffect(() => { current.current = key; return () => { current.current = ""; }; }, [key]);
  if (data.ai.state !== "AVAILABLE") {
    return <p className="screener-panel-note">AI synthesis {data.ai.state === "NOT_CONFIGURED" ? "not configured" : "unavailable"}{data.ai.reason ? ` · ${data.ai.reason}` : ""}. Nothing is generated.</p>;
  }
  const generate = async () => {
    const requested = key;
    setStatus({ key: requested, state: "running" });
    try {
      const value = await postNewsSynthesis({ universe: data.universe, scope: "INSTRUMENT", instrument: data.instrument.instrument_id, window: "24h" });
      // A result for a selection that has since changed is discarded.
      if (current.current !== requested) return;
      setResult({ key: requested, value }); setStatus(null);
    } catch {
      if (current.current === requested) setStatus({ key: requested, state: "error" });
    }
  };
  const running = status?.key === key && status.state === "running";
  return <>
    <button type="button" className="screener-control" disabled={running} onClick={() => void generate()}>{running ? "Generating…" : "Generate AI synthesis"}</button>
    <span className="screener-panel-note"> {data.ai.model_id ? `Model ${data.ai.model_id}. ` : ""}Runs only when requested.</span>
    {status?.key === key && status.state === "error" && <p className="screener-panel-note" role="alert">AI synthesis request failed.</p>}
    {result?.key === key && <SynthesisBlock result={result.value} stories={data.stories} universe={data.universe} />}
  </>;
}

function Provenance({ data }: { data: InstrumentNews }) {
  return <>
    <ul className="news-provenance">{data.providers.map((provider) => <li key={provider.id}>
      <span>{provider.label}</span> <strong>{stateText(provider.state)}</strong>
      <small>{provider.reason ? ` · ${provider.reason}` : ""} · {provider.fetched_at ? `fetched ${newsDayTime(provider.fetched_at, data.universe)}` : "not fetched"}
        {provider.item_count != null ? ` · ${provider.item_count} items` : ""} · {provider.scope.toLowerCase()} scope</small></li>)}</ul>
    <p className="screener-panel-note">Matching capability {stateText(data.capability.state === "SUPPORTED" ? "CURRENT" : data.capability.state)}{data.capability.reason ? ` · ${data.capability.reason}` : ""}.
      Bases: {data.capability.match_bases.map(humanize).join(", ") || "none"}. Terms: {data.capability.terms.join(", ") || "none"}.</p>
  </>;
}

export default function NewsAnalysisPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  const ready = Boolean(row) && settledId === row?.instrument.instrument_id;
  const query = useQuery({
    queryKey: ["screener-news-instrument", universe, settledId, "full"],
    queryFn: ({ signal }) => fetchInstrumentNews(universe, settledId!, false, signal),
    enabled: ready && visible, staleTime: 30_000, refetchInterval: visible ? REFRESH_MS : false, retry: 1,
  });
  // Stale-response guard: a payload for another instrument or universe never labels this selection.
  const data = query.data && query.data.instrument.instrument_id === settledId && query.data.universe === universe && ready ? query.data : undefined;
  const gate = selectionGate("news", row, settledId);
  const current = data ? data.providers.filter((item) => item.state === "CURRENT").length : 0;
  const degraded = data ? degradedProviders(data.providers) : [];
  return <PanelFrame id="news" state={data?.state ?? null} clock={data ? `updated ${newsDayTime(data.generated_at, data.universe)}` : null}
    detail={data ? `${data.instrument.label} · ${data.window.id} · ${data.coverage.story_count} stories · ${current}/${data.providers.length} providers current` : null}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">News &amp; Analysis request failed. <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row?.symbol} news…</PanelMessage>
      : <div className="news-panel">
        {(data.state === "NOT_CONFIGURED" || data.state === "UNAVAILABLE") && <PanelMessage tone="warn">News {data.state === "NOT_CONFIGURED" ? "providers are not configured" : "is unavailable"}{data.reason ? ` · ${data.reason}` : ""}. This is a provider state, not an absence of news.{degraded.length ? ` Missing: ${degraded.map((item) => `${item.label} (${stateText(item.state)})`).join(", ")}.` : ""}</PanelMessage>}
        {data.state === "PARTIAL" && degraded.length > 0 && <PanelMessage tone="warn">Partial coverage · not current: {degraded.map((item) => `${item.label} (${stateText(item.state)}${item.reason ? ` · ${item.reason}` : ""})`).join("; ")}.</PanelMessage>}
        <ProviderStrip providers={data.providers} label="News & Analysis providers" />
        <Section title="Latest headlines"><Headlines data={data} /></Section>
        <Section title="Sentiment" derived><Sentiment data={data} /></Section>
        <Section title="Catalysts / Events" derived><Catalysts data={data} /></Section>
        <Section title="Attention" derived><Attention data={data} /></Section>
        <Section title="Post-headline price reaction"><Reaction data={data} /></Section>
        <Section title="Analysis">
          <AnalysisGroup title="Observed" items={data.analysis.observed} />
          <AnalysisGroup title="Derived" items={data.analysis.derived} />
          <AnalysisGroup title="Insufficient evidence" items={data.analysis.insufficient} />
        </Section>
        <Section title="AI synthesis"><Synthesis key={`${data.universe}|${data.instrument.instrument_id}`} data={data} /></Section>
        <Section title="Provenance"><Provenance data={data} /></Section>
      </div>)}
  </PanelFrame>;
}
