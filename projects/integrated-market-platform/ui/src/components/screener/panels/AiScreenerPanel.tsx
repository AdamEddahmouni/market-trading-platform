import ActionDecisionPanel from "./ActionDecisionPanel";
import ReevaluationPanel from "./ReevaluationPanel";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { AiScreenerScope } from "../../../api/screenerAi";
import { aiScopeKey, fetchAiScreenerPreview } from "../../../api/screenerAi";
import { CoverageReceipts, CoverageSummary, ProvisionalFinalists } from "../ai/AiCoverage";
import AiRunProgress, { STAGE_LABEL } from "../ai/AiRunProgress";
import { EngineSwitchConfirm, contractText, engineLockText, fitText, type EngineFit, type PendingEngine } from "../ai/EngineSwitch";
import { useAiScreenerRunResult, useAiScreenerRuns } from "../ai/useAiScreenerRuns";
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

function EngineChoice({ ai, fit, onChanged }: { ai: AiStatus; fit: EngineFit[]; onChanged: (next: AiStatus) => void }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  // Choosing an option only proposes it: the engine is machine-wide, so nothing is sent until it is confirmed.
  const [pending, setPending] = useState<PendingEngine | null>(null);
  const selected = ai.engines?.find((engine) => engine.id === ai.engine);
  if (!ai.engines?.length) return <span className="ai-screener-meta">Engine {ai.provider_id ?? "unconfigured"}</span>;
  const value = `${ai.engine ?? "auto"}|${ai.engine_model ?? selected?.default_model ?? ""}`;
  const locked = engineLockText(ai);
  const fitFor = (id: string) => fit.find((item) => item.engine === id);
  const confirm = () => {
    if (!pending) return;
    setBusy(true); setFailed(false);
    void postSynthesisEngine(pending.engine.id, pending.model).then(onChanged).catch(() => setFailed(true)).finally(() => { setBusy(false); setPending(null); });
  };
  return <div className="ai-screener-engine-box"><label className="ai-screener-engine">Engine/model <select value={value} disabled={busy || Boolean(locked) || Boolean(pending)} onChange={(event) => {
    const separator = event.target.value.indexOf("|");
    const engine = ai.engines!.find((item) => item.id === event.target.value.slice(0, separator));
    if (engine && event.target.value !== value) { setFailed(false); setPending({ engine, model: event.target.value.slice(separator + 1) || null }); }
  }}>
    {ai.engines.map((engine) => engine.models.map((model) => <option key={`${engine.id}|${model}`} value={`${engine.id}|${model}`} disabled={engine.state !== "AVAILABLE"}>
      {engine.label} · {model} · {engine.runtime === "LOCAL_MODEL" ? "local" : "paid"}{fitText(fitFor(engine.id)) ? ` · ${fitText(fitFor(engine.id))}` : ""}{contractText(engine, model) ? ` · ${contractText(engine, model)}` : ""}
    </option>))}
  </select>{failed && <span role="alert"> Could not switch engine.</span>}</label>
    {locked && <p className="ai-screener-meta">{locked}</p>}
    {selected && fitFor(selected.id)?.fits === false && <p className="ai-screener-meta" role="alert">The {fitText(fitFor(selected.id))}. Choose another engine or narrow the Screener scope.</p>}
    {selected && contractText(selected, ai.engine_model) && <p className="ai-screener-meta" role="alert">The selected model {contractText(selected, ai.engine_model)}. Choose another model.</p>}
    {pending && <EngineSwitchConfirm pending={pending} fit={fitFor(pending.engine.id)} busy={busy} onConfirm={confirm} onCancel={() => setPending(null)} />}
  </div>;
}

function refsFor(selection: { supporting_refs: string[]; conflicting_refs: string[]; weak_refs: string[] }, name: keyof typeof selection) {
  return selection[name];
}

export default function AiScreenerPanel({ api }: { api: any }) {
  const visible = usePanelVisible(api);
  const { screenerScope: baseScope, openInstrument, openNews, actions } = useSelection();
  const [method, setMethod] = useState<NonNullable<AiScreenerScope['method']>>('EXHAUSTIVE_EXISTING');
  const experimental = method === 'STAGED_LOCAL_FIRST_EXPERIMENTAL';
  const screenerScope = { ...baseScope, ...(experimental ? { method } : {}) };
  const scopeKey = keyFor(screenerScope);
  const [aiOverride, setAiOverride] = useState<AiStatus | null>(null);
  // The run lives on the server: this panel only reads it, so closing the panel or reloading the page loses nothing.
  const { runs, start, stop } = useAiScreenerRuns(visible);
  const questionKey = aiScopeKey(screenerScope);
  const active = runs.data?.active ?? null;
  const latest = (experimental ? runs.data?.experimental_latest : runs.data?.latest) ?? null;
  // A result is drawn only under the Screener query it answered.
  const mine = latest && aiScopeKey(latest.scope) === questionKey ? latest : null;
  const detail = useAiScreenerRunResult(mine);
  const value = mine?.state === "COMPLETED" ? detail.data?.result ?? null : null;
  const running = Boolean(active) || start.isPending;
  const resetStart = start.reset;
  const preview = useQuery({ queryKey: ["screener-ai-screener-preview", scopeKey], queryFn: ({ signal }) => fetchAiScreenerPreview(screenerScope, signal), enabled: visible && screenerScope.settled !== false,
    staleTime: 30_000, retry: false });
  const ai = aiOverride ?? preview.data?.ai;
  const now = useNow(1_000, Boolean(value));
  const expired = Boolean(value) && Date.parse(value!.valid_until) <= now;
  useEffect(() => { setAiOverride(null); resetStart(); }, [scopeKey, resetStart]);
  // OCT1-10: one server projection joins candidate, decision, Paper position, stop and P&L. The run id is part of the
  // cache identity, so a previous run's lifecycles are never drawn under a new rank list.
  const runId = value?.run_id ?? null;
  const lifecycles = useQuery({ queryKey: ["screener-trade-lifecycles", runId], queryFn: ({ signal }) => tradeLifecycles(runId, signal),
    enabled: visible && !experimental, refetchInterval: visible && !experimental ? 15_000 : false, staleTime: 5_000, retry: false });
  const estimate = preview.data?.estimate;
  const status = ai?.state ?? "UNAVAILABLE";
  const evidence = useMemo(() => new Map((value?.evidence ?? []).flatMap((candidate) => [
    ...candidate.current_market_evidence, ...candidate.reference_evidence,
  ].map((item) => [item.evidence_id, item] as const))), [value]);
  const run = () => start.mutate(screenerScope);
  return <PanelFrame id="ai_screener" instrumentScoped={false} detail="internal evidence only">
    <label>Screener method <select aria-label="Screener method" value={method} disabled={running} onChange={(e) => setMethod(e.target.value as typeof method)}><option value="EXHAUSTIVE_EXISTING">Exhaustive existing</option><option value="STAGED_LOCAL_FIRST_EXPERIMENTAL">Local-first experimental</option></select></label>
    {experimental && <PanelMessage tone="warn">Experimental method unapproved. Local qualification precedes the entire premium pool budget check. Results have no Action Decision or Paper submission authority.</PanelMessage>}
    {experimental && preview.data?.staged && <section aria-label="Local runtime admission">
      <p>Local model {String(preview.data.staged.local_model.model_id ?? "unavailable")} · readiness {String(preview.data.staged.local_model.state)} · profile {String(preview.data.staged.local_model.execution_profile ?? "unavailable")}</p>
      <p>{typeof preview.data.staged.local_model.available_memory_bytes === 'number' ? (preview.data.staged.local_model.available_memory_bytes / 1024 ** 3).toFixed(2) + ' GiB available' : 'Available memory unmeasured'} · {typeof preview.data.staged.local_model.minimum_available_bytes === 'number' ? (preview.data.staged.local_model.minimum_available_bytes / 1024 ** 3).toFixed(2) + ' GiB safety floor' : 'Safety floor unavailable'}</p>
      {Boolean(preview.data.staged.local_model.reason) && <p>Admission refused: {String(preview.data.staged.local_model.reason)}. Retry requires a fresh resource measurement.</p>}
      <p>Local model quality is not proven by readiness. No benchmark results or premium savings are implied.</p>
      <details><summary>Runtime admission measurements</summary><pre>{JSON.stringify(preview.data.staged.local_model, null, 2)}</pre></details>
    </section>}
    <div className="ai-screener-toolbar">
      <div><strong>AI Screener</strong><p className="ai-screener-meta">Scope: {screenerScope.universe} · {preview.data ? `${preview.data.matched_count.toLocaleString()} matched` : "checking scope"} · {experimental ? "every eligible row receives a local assessment; unresolved cases advance to premium review" : "a run assesses every matched row and sends each eligible row to the model in batches of up to " + (preview.data?.max_intake ?? 50)}</p></div>
      {ai && <EngineChoice ai={ai} fit={preview.data?.engine_fit ?? []} onChanged={(next) => { setAiOverride(next); void preview.refetch(); }} />}
    </div>
    <p className="ai-screener-meta">View {screenerScope.view ?? "Overview"} · screen {screenerScope.screen || "Unsaved"} · search {screenerScope.search || "all"} · sort {screenerScope.sort} {screenerScope.descending ? "descending" : "ascending"} · result set {screenerScope.result_set ?? "unavailable"} · filters {JSON.stringify(screenerScope.filters)}</p>
    {start.isError && <PanelMessage tone="error" role="alert">AI Screener run failed. Retry explicitly.<ErrorDetail error={start.error} /></PanelMessage>}
    {runs.isError && <PanelMessage tone="error" role="alert">AI Screener run status is unavailable; a run may still be in progress on the server.<ErrorDetail error={runs.error} /></PanelMessage>}
    {preview.isPending && <PanelMessage>Preparing the bounded internal evidence scope…</PanelMessage>}
    {preview.isError && <PanelMessage tone="error" role="alert">AI Screener status unavailable. Retry by reopening the panel.</PanelMessage>}
    {ai && <p className="ai-screener-meta">Provider {ai.provider_id ?? "none"} · model {ai.model_id ?? "none"} · runtime {ai.runtime ?? "not configured"} · {ai.runtime === "PAID_API" ? "shared paid budget" : "no API cost"}.</p>}
    {ai?.budget && <p className="ai-screener-meta">Daily shared budget: {ai.budget.requests}/{ai.budget.max_requests} requests · {ai.budget.tokens}/{ai.budget.max_tokens} tokens · UTC day {ai.budget.day}.</p>}
    {estimate && <p className="ai-screener-meta">Preview of the first {estimate.intake_count} rows only (about one batch; the run plans every batch before any model call) · {estimate.sufficient_count} sufficiently grounded · packet {estimate.packet_bytes.toLocaleString()} bytes · {estimate.cached ? "cached, no model cost" : estimate.tokens != null ? `worst-case ≈ ${compactTokens(estimate.tokens)} tokens` : "cost estimate unavailable"}.</p>}
    {preview.data?.news_coverage && <details><summary>News coverage · cached preview · no acquisition or scoring</summary>
      {preview.data.news_coverage.map((item) => <p key={item.instrument_id}>{item.instrument_id} · {item.state} · {item.story_count} stories · {item.window} · sentiment {item.sentiment.state} · {item.providers.map((p) => `${p.id}: ${p.state}`).join(" · ")}</p>)}
    </details>}
    {status !== "AVAILABLE" && ai && <PanelMessage>{status === "NOT_CONFIGURED" ? "AI Screener is not configured; no inference was attempted." : `AI Screener unavailable${ai.reason ? ` · ${ai.reason}` : ""}.`}</PanelMessage>}
    {status === "AVAILABLE" && <button type="button" className="screener-primary ai-screener-run" onClick={run} disabled={running || preview.isPending || preview.isError || screenerScope.settled === false}>
      {running ? "Running AI Screener…" : "Run AI Screener"}
    </button>}
    {active && <AiRunProgress run={active} />}
    {active && <button type="button" className="ai-screener-stop" disabled={stop.isPending || active.stop_requested === true} onClick={() => stop.mutate(active.run_id)}
      title="No further model call starts. A call already sent is not cancelled and its tokens stay charged.">{active.stop_requested ? "Stopping after the call in flight…" : "Stop run"}</button>}
    {stop.isError && <PanelMessage tone="error" role="alert">Could not stop the run.<ErrorDetail error={stop.error} /></PanelMessage>}
    {active && start.data?.joined && start.data.run_id === active.run_id && <PanelMessage>Joined the run already in progress; no second run was started.</PanelMessage>}
    {active && aiScopeKey(active.scope) !== questionKey && <PanelMessage tone="warn">This run answers a different Screener scope ({active.scope.universe}, method {active.scope.method ?? "EXHAUSTIVE_EXISTING"}). One run at a time per account.</PanelMessage>}
    {!active && mine?.state === "FAILED" && <PanelMessage tone="error" role="alert">AI Screener run failed{mine.error?.stage ? ` while ${(STAGE_LABEL[mine.error.stage] ?? mine.error.stage).toLowerCase()}` : ""}{mine.error ? ` · ${mine.error.code}` : ""}. No result was recorded. Retry explicitly.</PanelMessage>}
    {!active && latest && !mine && <PanelMessage>The latest run answered a different Screener scope ({latest.scope.universe}). Run AI Screener to answer this one.</PanelMessage>}
    {mine?.state === "COMPLETED" && detail.isError && <PanelMessage tone="error" role="alert">The result of the latest run is no longer held by the server. Rerun AI Screener.<ErrorDetail error={detail.error} /></PanelMessage>}
    {!experimental && screenerScope.settled !== false && <ReevaluationPanel key={scopeKey} scope={screenerScope} />}
    {!experimental && lifecycles.data && <LifecycleBoundary list={lifecycles.data} />}
    {!experimental && lifecycles.isError && <PanelMessage tone="error" role="alert">Trade lifecycle is unavailable; positions, fills and P&amp;L are not shown here.<ErrorDetail error={lifecycles.error} /></PanelMessage>}
    {value && <section className="ai-screener-result" aria-label="AI Screener result">
      {value.universe_coverage && <CoverageSummary coverage={value.universe_coverage} />}
      {value.universe_coverage && mine && <CoverageReceipts runId={mine.run_id} />}
      {value.staged && <section aria-label="Experimental accounting"><p>{value.staged.status} · approval {value.staged.approval_status} · local coverage {value.staged.local_coverage_complete ? "complete" : "incomplete"} · accounting {value.staged.reconciled ? "reconciled" : "incomplete"}</p>{Object.entries(value.staged.counters).map(([name, count]) => <p key={name}>{name.replace(/_/g, " ")}: {count}</p>)}<details><summary>Whole premium pool budget plan and model lineage</summary><pre>{JSON.stringify({ budget: value.staged.premium_plan, local: value.staged.local_model, premium: value.staged.premium_model }, null, 2)}</pre></details></section>}
      <p className="ai-screener-meta">Selected {value.candidates.length} of {value.intake_count} {value.staged ? "local assessments" : "rows sent to the model"}{value.universe_coverage || value.staged ? "" : " (single-request method: only the head of the sorted result was read)"} · {value.simulated ? "SOFTWARE_CONTROLLED fixture" : value.runtime} · valid until {value.valid_until}</p>
      <p className="ai-screener-meta">{value.state} · {value.provider_id} · {value.model_id} · prompt {value.prompt_id} v{value.prompt_version} · cutoff {value.decision_cutoff} · {value.cache === "HIT" ? "cache hit" : `${value.latency_ms ?? "—"} ms`}</p>
      {mine && <p className="ai-screener-meta">Run took {(mine.elapsed_ms / 1000).toFixed(1)}s on the server{value.result_set && screenerScope.result_set && value.result_set !== screenerScope.result_set ? " · the Screener list has refreshed since; this result is as of its cutoff" : ""}.</p>}
      {value.state === "INCOMPLETE" ? <>
        <PanelMessage tone="warn" role="status">This run did not finish, so it is not a selection from the whole universe. {value.limitations.join(" ")}</PanelMessage>
        <ProvisionalFinalists result={value} />
      </> : expired && (value.candidates.length > 0 || (!value.universe_coverage && !value.staged)) ? <PanelMessage tone="warn">Evidence expired — rerun AI Screener.</PanelMessage> : value.state !== "CURRENT" && value.state !== "NO_GROUNDED_CANDIDATES" ? <PanelMessage tone="error">Result rejected or unavailable{value.reason ? ` · ${value.reason}` : ""}.</PanelMessage> : <>
        {value.candidates.length === 0 && <PanelMessage>{value.universe_coverage ? "The run finished and selected no candidate." : "No sufficiently grounded candidates were selected."} {value.limitations.join(" ")}</PanelMessage>}
        {value.candidates.map((selection) => {
          const lifecycle = !experimental && lifecycles.data?.run?.run_id === value.run_id ? lifecycles.data.selected.find((item) => item.instrument_id === selection.instrument_id) : undefined;
          const controls = <>
          {!value.staged && <ActionDecisionPanel key={`${value.run_id}|${selection.instrument_id}`} runId={value.run_id} instrumentId={selection.instrument_id} onChanged={() => void lifecycles.refetch()} />}
          <button type="button" onClick={() => openInstrument(selection.instrument_id)}>Open in Screener workflow</button>
          <details className="lifecycle-source"><summary>Source evidence and News detail from this run</summary>
          {(() => {
            const candidate = value.evidence.find((item) => item.instrument.instrument_id === selection.instrument_id);
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
          <h4>Blocked evidence</h4>{(value.evidence.find((item) => item.instrument.instrument_id === selection.instrument_id)?.blocked ?? []).map((item, index) =>
            <p key={index}>{String(item.capability)} · {Array.isArray(item.reason_codes) ? item.reason_codes.join(", ") : "Unavailable"}</p>)}
          <h4>Uncertainties</h4><ul>{selection.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul>
          </details></>;
          return lifecycle ? <LifecycleCard key={selection.instrument_id} lifecycle={lifecycle} runId={value.run_id}>{controls}</LifecycleCard>
            : <article className="ai-screener-candidate" key={selection.instrument_id}>
              <header><h3>#{selection.rank} {selection.instrument_id}</h3></header>
              {!experimental && !lifecycles.isError && <p role="status">Loading lifecycle…</p>}
              {controls}
            </article>;
        })}
      </>}
    </section>}
    {!experimental && lifecycles.data && <TradeLifecycleGroups list={lifecycles.data} runId={runId} />}
  </PanelFrame>;
}
