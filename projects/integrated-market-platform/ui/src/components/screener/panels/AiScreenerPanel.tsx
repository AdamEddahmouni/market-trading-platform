import ActionDecisionPanel from "./ActionDecisionPanel";
import ReevaluationPanel from "./ReevaluationPanel";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { AiScreenerResult, AiScreenerScope } from "../../../api/screenerAi";
import { fetchAiScreenerPreview, postAiScreener } from "../../../api/screenerAi";
import { postSynthesisEngine, type AiStatus } from "../../../api/screenerNews";
import { compactTokens } from "../news/SynthesisControl";
import { tradeLifecycles } from "../../../api/screenerLifecycle";
import LifecycleCard from "../lifecycle/LifecycleCard";
import TradeLifecycleGroups, { LifecycleBoundary } from "../lifecycle/TradeLifecycleGroups";
import { age, ErrorDetail, PanelFrame, PanelMessage, useNow, usePanelVisible, useSelection } from "./shared";

const keyFor = (scope: AiScreenerScope) => JSON.stringify(scope);

function EvidenceCard({ title, evidence }: { title: string; evidence: Record<string, any> }) {
  if (evidence.capability === "NEWS") {
    const story = evidence.facts;
    return <details className="ai-screener-evidence"><summary>{story.headline} · NEWS</summary><dl>
      <div><dt>Evidence</dt><dd>{title} · story {story.story_id}</dd></div>
      <div><dt>Source / publisher</dt><dd>{story.sources?.map((source: Record<string, any>) => `${source.provider_id}: ${source.publisher}`).join(" · ")} · {story.source_count} sources / {story.provider_count} providers (syndication)</dd></div>
      <div><dt>Published</dt><dd>{story.published_at ? `${story.published_at} · ${age(story.published_at)} ago` : `Publication time unknown · retrieval proxy ${story.first_retrieved_at}`}; latest publication {story.latest_published_at ?? "unknown"}</dd></div>
      <div><dt>Component clocks</dt><dd>{story.sources?.map((source: Record<string, any>) => `${source.provider_id}: available ${source.available_at ?? "unknown"}, retrieved ${source.retrieved_at ?? "unknown"}, ingested ${source.ingested_at ?? "unknown"}`).join(" · ")}</dd></div>
      <div><dt>Relevance</dt><dd>{story.match_confidence} · {story.match_basis} · {story.categories?.map((category: Record<string, any>) => category.label ?? category.id).join(", ") || "Uncategorized"} · window {story.window}</dd></div>
      <div><dt>Sentiment</dt><dd>{story.sentiment?.label ?? "NOT_SCORED"} · state {story.sentiment?.state} · {story.sentiment?.model_id ?? "FinBERT unavailable"} · revision {story.sentiment?.model_revision ?? "unknown"} · {story.sentiment?.sentiment_version} · {story.sentiment?.basis}; probabilities {JSON.stringify(story.sentiment?.probabilities)}</dd></div>
      <div><dt>Freshness</dt><dd>{story.coverage_state} · {evidence.freshness_status} · {evidence.role} · valid until {evidence.valid_until}</dd></div>
    </dl></details>;
  }
  return <details className="ai-screener-evidence"><summary>{title} · {evidence.capability}</summary>
    <dl>{evidence.capability === "QUOTE" && <div><dt>Price</dt><dd>{typeof evidence.facts?.price === "number" ? `$${evidence.facts.price.toFixed(2)}` : "unavailable"}</dd></div>}<div><dt>Facts</dt><dd><code>{JSON.stringify(evidence.facts)}</code></dd></div>
      <div><dt>Source</dt><dd>{evidence.source ?? "unavailable"}</dd></div>
      <div><dt>Observed</dt><dd>{evidence.as_of ?? "unknown"}</dd></div>
      <div><dt>Received</dt><dd>{evidence.received_at ?? "unknown"}</dd></div>
      <div><dt>Freshness</dt><dd>{evidence.freshness_status} · {evidence.decision_admissibility} · {evidence.role}</dd></div>
    </dl></details>;
}

function EngineChoice({ ai, onChanged }: { ai: AiStatus; onChanged: (next: AiStatus) => void }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const selected = ai.engines?.find((engine) => engine.id === ai.engine);
  if (!ai.engines?.length) return <span className="ai-screener-meta">Engine {ai.provider_id ?? "unconfigured"}</span>;
  const value = `${ai.engine ?? "auto"}|${ai.engine_model ?? selected?.default_model ?? ""}`;
  return <label className="ai-screener-engine">Engine/model <select value={value} disabled={busy} onChange={(event) => {
    const separator = event.target.value.indexOf("|");
    setBusy(true); setFailed(false);
    void postSynthesisEngine(event.target.value.slice(0, separator), event.target.value.slice(separator + 1) || null)
      .then(onChanged).catch(() => setFailed(true)).finally(() => setBusy(false));
  }}>
    {ai.engines.map((engine) => engine.models.map((model) => <option key={`${engine.id}|${model}`} value={`${engine.id}|${model}`} disabled={engine.state !== "AVAILABLE"}>
      {engine.label} · {model} · {engine.runtime === "LOCAL_MODEL" ? "local" : "paid"}
    </option>))}
  </select>{failed && <span role="alert"> Could not switch engine.</span>}</label>;
}

function refsFor(selection: { supporting_refs: string[]; conflicting_refs: string[]; weak_refs: string[] }, name: keyof typeof selection) {
  return selection[name];
}

export default function AiScreenerPanel({ api }: { api: any }) {
  const visible = usePanelVisible(api);
  const { screenerScope, openInstrument, openNews, actions } = useSelection();
  const scopeKey = keyFor(screenerScope);
  const current = useRef(scopeKey); current.current = scopeKey;
  const abort = useRef<AbortController | null>(null);
  const [aiOverride, setAiOverride] = useState<AiStatus | null>(null);
  const [result, setResult] = useState<{ key: string; value: AiScreenerResult } | null>(null);
  const [running, setRunning] = useState(false);
  const [runFailed, setRunFailed] = useState(false);
  const preview = useQuery({ queryKey: ["screener-ai-screener-preview", scopeKey], queryFn: ({ signal }) => fetchAiScreenerPreview(screenerScope, signal), enabled: visible && screenerScope.settled !== false,
    staleTime: 30_000, retry: false });
  const ai = aiOverride ?? preview.data?.ai;
  const now = useNow(1_000, Boolean(result));
  const expired = result?.key === scopeKey && Date.parse(result.value.valid_until) <= now;
  useEffect(() => { setResult(null); setAiOverride(null); setRunFailed(false); abort.current?.abort(); setRunning(false); }, [scopeKey]);
  useEffect(() => () => { abort.current?.abort(); }, []);
  // OCT1-10: one server projection joins candidate, decision, Paper position, stop and P&L. The run id is part of the
  // cache identity, so a previous run's lifecycles are never drawn under a new rank list.
  const runId = result?.key === scopeKey ? result.value.run_id : null;
  const lifecycles = useQuery({ queryKey: ["screener-trade-lifecycles", runId], queryFn: ({ signal }) => tradeLifecycles(runId, signal),
    enabled: visible, refetchInterval: visible ? 15_000 : false, staleTime: 5_000, retry: false });
  const estimate = preview.data?.estimate;
  const status = ai?.state ?? "UNAVAILABLE";
  const evidence = useMemo(() => new Map((result?.value.evidence ?? []).flatMap((candidate) => [
    ...candidate.current_market_evidence, ...candidate.reference_evidence,
  ].map((item) => [item.evidence_id, item] as const))), [result]);
  const run = () => {
    const requested = scopeKey;
    abort.current?.abort(); const controller = new AbortController(); abort.current = controller; setRunning(true); setRunFailed(false);
    void postAiScreener(screenerScope, controller.signal).then((value) => {
      if (current.current === requested) setResult({ key: requested, value });
    }).catch(() => { if (current.current === requested && !controller.signal.aborted) setRunFailed(true); }).finally(() => { if (current.current === requested) setRunning(false); });
  };
  return <PanelFrame id="ai_screener" instrumentScoped={false} detail="internal evidence only">
    <div className="ai-screener-toolbar">
      <div><strong>AI Screener</strong><p className="ai-screener-meta">Scope: {screenerScope.universe} · {preview.data ? `${preview.data.matched_count.toLocaleString()} matched` : "checking scope"} · intake capped at {preview.data?.max_intake ?? 20}</p></div>
      {ai && <EngineChoice ai={ai} onChanged={(next) => { setAiOverride(next); void preview.refetch(); }} />}
    </div>
    <p className="ai-screener-meta">View {screenerScope.view ?? "Overview"} · screen {screenerScope.screen || "Unsaved"} · search {screenerScope.search || "all"} · sort {screenerScope.sort} {screenerScope.descending ? "descending" : "ascending"} · result set {screenerScope.result_set ?? "unavailable"} · filters {JSON.stringify(screenerScope.filters)}</p>
    {runFailed && <PanelMessage tone="error" role="alert">AI Screener run failed. Retry explicitly.</PanelMessage>}
    {preview.isPending && <PanelMessage>Preparing the bounded internal evidence scope…</PanelMessage>}
    {preview.isError && <PanelMessage tone="error" role="alert">AI Screener status unavailable. Retry by reopening the panel.</PanelMessage>}
    {ai && <p className="ai-screener-meta">Provider {ai.provider_id ?? "none"} · model {ai.model_id ?? "none"} · runtime {ai.runtime ?? "not configured"} · {ai.runtime === "PAID_API" ? "shared paid budget" : "no API cost"}.</p>}
    {ai?.budget && <p className="ai-screener-meta">Daily shared budget: {ai.budget.requests}/{ai.budget.max_requests} requests · {ai.budget.tokens}/{ai.budget.max_tokens} tokens · UTC day {ai.budget.day}.</p>}
    {estimate && <p className="ai-screener-meta">Server intake {estimate.intake_count} · {estimate.sufficient_count} sufficiently grounded · packet {estimate.packet_bytes.toLocaleString()} bytes · {estimate.cached ? "cached, no model cost" : estimate.tokens != null ? `worst-case ≈ ${compactTokens(estimate.tokens)} tokens` : "cost estimate unavailable"}.</p>}
    {preview.data?.news_coverage && <details><summary>News coverage · cached preview · no acquisition or scoring</summary>
      {preview.data.news_coverage.map((item) => <p key={item.instrument_id}>{item.instrument_id} · {item.state} · {item.story_count} stories · {item.window} · sentiment {item.sentiment.state} · {item.providers.map((p) => `${p.id}: ${p.state}`).join(" · ")}</p>)}
    </details>}
    {status !== "AVAILABLE" && ai && <PanelMessage>{status === "NOT_CONFIGURED" ? "AI Screener is not configured; no inference was attempted." : `AI Screener unavailable${ai.reason ? ` · ${ai.reason}` : ""}.`}</PanelMessage>}
    {status === "AVAILABLE" && <button type="button" className="screener-primary ai-screener-run" onClick={run} disabled={running || preview.isPending || preview.isError || screenerScope.settled === false}>
      {running ? "Running AI Screener…" : "Run AI Screener"}
    </button>}
    {screenerScope.settled !== false && <ReevaluationPanel key={scopeKey} scope={screenerScope} />}
    {lifecycles.data && <LifecycleBoundary list={lifecycles.data} />}
    {lifecycles.isError && <PanelMessage tone="error" role="alert">Trade lifecycle is unavailable; positions, fills and P&amp;L are not shown here.<ErrorDetail error={lifecycles.error} /></PanelMessage>}
    {result?.key === scopeKey && <section className="ai-screener-result" aria-label="AI Screener result">
      <p className="ai-screener-meta">Selected {result.value.candidates.length} of {result.value.intake_count} intake candidates · {result.value.simulated ? "SOFTWARE_CONTROLLED fixture" : result.value.runtime} · valid until {result.value.valid_until}</p>
      <p className="ai-screener-meta">{result.value.state} · {result.value.provider_id} · {result.value.model_id} · prompt {result.value.prompt_id} v{result.value.prompt_version} · cutoff {result.value.decision_cutoff} · {result.value.cache === "HIT" ? "cache hit" : `${result.value.latency_ms ?? "—"} ms`}</p>
      {expired ? <PanelMessage tone="warn">Evidence expired — rerun AI Screener.</PanelMessage> : result.value.state !== "CURRENT" && result.value.state !== "NO_GROUNDED_CANDIDATES" ? <PanelMessage tone="error">Result rejected or unavailable{result.value.reason ? ` · ${result.value.reason}` : ""}.</PanelMessage> : <>
        {result.value.candidates.length === 0 && <PanelMessage>No sufficiently grounded candidates were selected. {result.value.limitations.join(" ")}</PanelMessage>}
        {result.value.candidates.map((selection) => {
          const lifecycle = lifecycles.data?.run?.run_id === result.value.run_id ? lifecycles.data.selected.find((item) => item.instrument_id === selection.instrument_id) : undefined;
          const controls = <>
          <ActionDecisionPanel key={`${result.value.run_id}|${selection.instrument_id}`} runId={result.value.run_id} instrumentId={selection.instrument_id} onChanged={() => void lifecycles.refetch()} />
          <button type="button" onClick={() => openInstrument(selection.instrument_id)}>Open in Screener workflow</button>
          <details className="lifecycle-source"><summary>Source evidence and News detail from this run</summary>
          {(() => {
            const candidate = result.value.evidence.find((item) => item.instrument.instrument_id === selection.instrument_id);
            const news = candidate?.news;
            return <section aria-label={`News and sentiment for ${selection.instrument_id}`}>
              <h4>News / Sentiment</h4>
              <p>{news ? `${news.state} · ${news.story_count} stories · ${news.window} · snapshot ${news.snapshot_at}` : "NEWS missing · SENTIMENT unavailable"}</p>
              {news && <><p>Coverage: {news.providers.map((p) => `${p.id}: ${p.state}${p.reason ? ` (${p.reason})` : ""}`).join(" · ")}</p>
                <p>Headline language: {news.sentiment.dominant ?? "NOT_SCORED"} · {news.sentiment.state} · {news.sentiment.reason} · scored {news.sentiment.scored}, unscored {news.sentiment.unscored}</p>
                <details><summary>FinBERT model and aggregation</summary><p>{news.sentiment.model_id ?? "Model unavailable"} · revision {news.sentiment.model_revision ?? "unknown"} · {news.sentiment.sentiment_version} · {news.sentiment.basis}</p><p>{news.sentiment.method}</p><p>{JSON.stringify(news.sentiment.counts)}</p></details>
              </>}
              {candidate?.reference_evidence.filter((item) => item.capability === "NEWS").map((item) => <EvidenceCard key={item.evidence_id} title={item.evidence_id} evidence={item} />)}
              {candidate?.alignments?.map((item) => <details key={item.alignment_id}><summary>Evidence alignment: {item.result} · sentiment vs {item.kind.endsWith("FLOW") ? "observed signed flow" : "observed price direction"}</summary>
                <p>Observed direction {item.observed_direction ?? "UNKNOWN"} · {item.method} · cutoff {item.cutoff}</p>
                <p>News refs {item.news_refs.join(", ")} · sentiment refs {item.sentiment_refs.join(", ")} · comparator {item.comparator_ref ?? "unavailable"}</p><p>{item.limitations.join(" ")}</p>
              </details>)}
              <p>Sentiment describes headline language. It is not a forecast, trading signal, or future-return claim.</p>
              <button type="button" onClick={() => { if (openNews && candidate) openNews(selection.instrument_id, candidate.instrument); else actions.open?.("news"); }}>Open News &amp; Analysis</button>
            </section>;
          })()}
          <p>{selection.rationale}</p>
          {(["supporting_refs", "conflicting_refs", "weak_refs"] as const).map((name) => <div key={name}>
            <h4>{name === "supporting_refs" ? "Supporting evidence" : name === "conflicting_refs" ? "Conflicting evidence" : "Weak evidence"}</h4>
            {refsFor(selection, name).length ? refsFor(selection, name).map((ref) => evidence.get(ref) ? <EvidenceCard key={ref} title={ref} evidence={evidence.get(ref)!} /> : <p key={ref}>Unknown evidence ref rejected by server.</p>) : <p className="ai-screener-empty">None cited.</p>}
          </div>)}
          <h4>Missing evidence</h4><p>{selection.missing_capabilities.length ? selection.missing_capabilities.join(", ") : "None recorded."}</p>
          <h4>Blocked evidence</h4>{(result.value.evidence.find((item) => item.instrument.instrument_id === selection.instrument_id)?.blocked ?? []).map((item, index) =>
            <p key={index}>{String(item.capability)} · {Array.isArray(item.reason_codes) ? item.reason_codes.join(", ") : "Unavailable"}</p>)}
          <h4>Uncertainties</h4><ul>{selection.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul>
          </details></>;
          return lifecycle ? <LifecycleCard key={selection.instrument_id} lifecycle={lifecycle} runId={result.value.run_id}>{controls}</LifecycleCard>
            : <article className="ai-screener-candidate" key={selection.instrument_id}>
              <header><h3>#{selection.rank} {selection.instrument_id}</h3></header>
              {!lifecycles.isError && <p role="status">Loading lifecycle…</p>}
              {controls}
            </article>;
        })}
      </>}
    </section>}
    {lifecycles.data && <TradeLifecycleGroups list={lifecycles.data} runId={runId} />}
  </PanelFrame>;
}
