import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import type { ScreenerUniverse } from "../../../api/screener";
import { SETUP_QUERY_KEY, type Remedy } from "../../../api/screenerSetup";
import { fetchSynthesisPreview, postNewsSynthesis, postSynthesisEngine, type AiStatus, type NewsStory, type NewsSynthesis,
  type NewsWindowId, type SynthesisBudget, type SynthesisEngine, type SynthesisRefItem, type SynthesisRequest } from "../../../api/screenerNews";
import { humanize, newsDayTime } from "./newsFormat";
import { RemedyHint } from "../setup/Remedy";

const PREVIEW_ROOT = "screener-news-synthesis-preview";
const TICK_MS = 1_000;

export const compactTokens = (value: number) => value >= 1000 ? `${Math.round(value / 1000)}k` : String(value);

/** AI status and pre-click cost for one synthesis target; never calls a model. */
export function useSynthesisPreview(request: SynthesisRequest, enabled: boolean) {
  return useQuery({
    queryKey: [PREVIEW_ROOT, request.universe, request.scope, request.instrument ?? null, request.window ?? "24h"],
    queryFn: ({ signal }) => fetchSynthesisPreview(request, signal),
    enabled, staleTime: 30_000, retry: 1,
  });
}

/** Every cached view of this universe's AI status takes the post-call budget at once, not on its next refetch. */
function applyBudget(client: QueryClient, universe: ScreenerUniverse, budget: SynthesisBudget) {
  const exhausted = budget.requests >= budget.max_requests || budget.tokens >= budget.max_tokens;
  const patch = <T extends { ai: AiStatus }>(old: T | undefined): T | undefined => old && {
    ...old, ai: { ...old.ai, budget, ...(exhausted ? { state: "UNAVAILABLE" as const, reason: "SYNTHESIS_DAILY_BUDGET_EXHAUSTED" } : {}) } };
  client.setQueriesData<{ ai: AiStatus }>({ queryKey: ["screener-news-instrument", universe] }, patch);
  client.setQueriesData<{ ai: AiStatus }>({ queryKey: [PREVIEW_ROOT, universe] }, patch);
  // The next estimate (and its cached flag) and the Setup checklist follow the call.
  void client.invalidateQueries({ queryKey: [PREVIEW_ROOT, universe] });
  void client.invalidateQueries({ queryKey: SETUP_QUERY_KEY });
}

/** An engine switch applies everywhere at once: every cached AI status takes the new one, then refetches. */
function applyAiStatus(client: QueryClient, ai: AiStatus) {
  const patch = <T extends { ai: AiStatus }>(old: T | undefined): T | undefined => old && { ...old, ai };
  client.setQueriesData<{ ai: AiStatus }>({ queryKey: ["screener-news-instrument"] }, patch);
  client.setQueriesData<{ ai: AiStatus }>({ queryKey: [PREVIEW_ROOT] }, patch);
  void client.invalidateQueries({ queryKey: [PREVIEW_ROOT] });
  void client.invalidateQueries({ queryKey: ["screener-news-instrument"] });
  void client.invalidateQueries({ queryKey: SETUP_QUERY_KEY });
}

const AUTO = "auto";
const optionValue = (engine: string, model: string | null) => `${engine}|${model ?? ""}`;
/** A missing key points at Setup, where it is entered; the reason code otherwise. */
const needs = (engine: SynthesisEngine) => engine.reason?.endsWith("_NOT_SET") ? "add a key in Setup"
  : engine.runtime === "LOCAL_MODEL" ? "not installed" : humanize(engine.reason ?? "unavailable");

/** Which engine and model synthesis runs on: free local model or a paid API. Saved on the server; calls no model. */
function EngineSelect({ ai, disabled, onChanged }: { ai: AiStatus; disabled: boolean; onChanged: () => void }) {
  const client = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  const engines = ai.engines ?? [];
  if (!engines.length) return null;
  const chosen = engines.find((engine) => engine.id === ai.engine);
  const value = chosen ? optionValue(chosen.id, ai.engine_model ?? chosen.default_model) : AUTO;
  const change = async (next: string) => {
    if (next === AUTO || next === value) return;
    const split = next.indexOf("|");
    setSaving(true); setFailed(false);
    try {
      const status = await postSynthesisEngine(next.slice(0, split), next.slice(split + 1) || null);
      applyAiStatus(client, status);
      onChanged();
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };
  return <span className="news-ai-engine">
    <label>AI engine <select value={value} disabled={disabled || saving} onChange={(event) => void change(event.target.value)}
      title="Free local model or a paid API. Paid engines share one hard daily limit.">
      {!chosen && <option value={AUTO}>Automatic{ai.model_id ? ` (now ${ai.model_id})` : ""}</option>}
      {engines.map((engine) => {
        const cost = engine.runtime === "LOCAL_MODEL" ? "free" : "paid";
        const ready = engine.state === "AVAILABLE";
        return <optgroup key={engine.id} label={ready ? `${engine.label} (${cost})` : `${engine.label}: ${needs(engine)}`}>
          {engine.models.length ? engine.models.map((model) => <option key={model} value={optionValue(engine.id, model)} disabled={!ready}>
            {engine.label} · {model} ({ready ? cost : needs(engine)})</option>)
            : <option value={optionValue(engine.id, null)} disabled>{engine.label} ({needs(engine)})</option>}
        </optgroup>;
      })}
    </select></label>
    {saving && <span className="screener-panel-note" role="status"> Switching…</span>}
    {failed && <span className="screener-panel-note" role="alert"> Could not switch the AI engine.</span>}
  </span>;
}

type Cited = { story_id: string; headline: string; url: string | null };

function Refs({ refs, cited, onCite }: { refs: string[]; cited: Cited[]; onCite: (id: string | null) => void }) {
  if (!refs.length) return null;
  return <span className="news-refs">Sources: {refs.map((ref) => {
    const index = cited.findIndex((item) => item.story_id === ref);
    const story = index >= 0 ? cited[index] : null;
    const label = story ? story.headline : `story ${ref} not in the loaded feed`;
    const number = index >= 0 ? String(index + 1) : "?";
    const hover = { title: label, "aria-label": `${number} ${label}`, onMouseEnter: () => onCite(ref), onMouseLeave: () => onCite(null),
      onFocus: () => onCite(ref), onBlur: () => onCite(null) };
    const content = number;
    return story?.url ? <a key={ref} className="news-ref-chip" href={story.url} target="_blank" rel="noopener noreferrer" {...hover}>{content}</a>
      : <span key={ref} className={`news-ref-chip${story ? "" : " missing"}`} tabIndex={0} {...hover}>{content}</span>;
  })}</span>;
}

function SynthesisBlock({ result, cited, citedId, onCite, universe, tookS, showInputs }: {
  result: NewsSynthesis; cited: Cited[]; citedId: string | null; onCite: (id: string | null) => void; universe: ScreenerUniverse;
  tookS: number | null; showInputs: boolean;
}) {
  const label = `AI synthesis · model ${result.model_id ?? "unknown"}${result.runtime === "LOCAL_MODEL" ? " (local)" : ""} · generated ${newsDayTime(result.generated_at, universe)}`;
  const took = tookS != null ? ` · took ${tookS < 1 ? "<1" : tookS} s` : "";
  if (result.state !== "CURRENT" || !result.synthesis) {
    return <p className="screener-panel-note" role="status">{label} · {humanize(result.state)}{result.reason ? ` · ${result.reason}` : ""}{took}.</p>;
  }
  const s = result.synthesis;
  const refList = (title: string, items: SynthesisRefItem[]) => <div className="news-ai-block">
    <p className="news-ai-label">{label}</p><h4>{title}</h4>
    {items.length ? <ul>{items.map((item, index) => <li key={index}>{item.text} <Refs refs={item.refs} cited={cited} onCite={onCite} /></li>)}</ul>
      : <p className="screener-panel-note">None stated.</p>}</div>;
  return <div className="news-ai" aria-label="AI synthesis result">
    <div className="news-ai-block"><p className="news-ai-label">{label}</p><h4>Summary</h4><p>{s.summary}</p></div>
    {refList("Observed facts", s.observed_facts)}
    {refList("Derived context", s.derived_context)}
    <div className="news-ai-block"><p className="news-ai-label">{label}</p><h4>Uncertainties</h4>
      {s.uncertainties.length ? <ul>{s.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="screener-panel-note">None stated.</p>}</div>
    {refList("Conflicting evidence", s.conflicting_evidence)}
    {refList("Potential market relevance", s.potential_market_relevance)}
    {showInputs && cited.length > 0 && <div className="news-ai-inputs"><h4>Headlines given to the model</h4>
      <ol className="news-panel-feed" aria-label="Headlines given to the model">{cited.map((item) =>
        <li key={item.story_id} data-story-id={item.story_id} className={item.story_id === citedId ? "cited" : undefined}>
          {item.url ? <a className="news-headline" href={item.url} target="_blank" rel="noopener noreferrer">{item.headline}</a>
            : <span className="news-headline">{item.headline}</span>}</li>)}</ol></div>}
    <p className="screener-panel-note">Coverage: {result.coverage.synthesized_story_count != null && result.coverage.synthesized_story_count < result.coverage.story_count ? `${result.coverage.synthesized_story_count} of ${result.coverage.story_count}` : result.coverage.story_count} stories · {result.coverage.source_count} sources{result.coverage.missing_providers.length ? ` · missing ${result.coverage.missing_providers.join(", ")}` : ""} · prompt {result.prompt_id} v{result.prompt_version}{result.cache ? ` · ${result.cache === "HIT" ? "served from cache" : "newly generated"}` : ""}{took}. AI output is a synthesis of the listed headlines, not verified fact or advice.</p>
  </div>;
}

type Props = {
  request: SynthesisRequest;
  ai: AiStatus;
  /** The one step that enables AI when it is not configured. */
  remedy?: Remedy | null;
  /** Loaded stories; resolve refs when the server did not list the model's inputs. */
  stories: NewsStory[];
  /** Hovered or focused citation, so the caller can highlight that headline. */
  onCite?: (storyId: string | null) => void;
  /** List the model's inputs under the result (no headline list is on screen). */
  showInputs?: boolean;
  /** Whether the cost preview may load (the section is on screen). */
  visible?: boolean;
};

/** Explicit, operator-requested AI synthesis. The caller keys it by target; a new target cancels an in-flight request. */
export function SynthesisControl({ request, ai, remedy = null, stories, onCite, showInputs = false, visible = true }: Props) {
  const client = useQueryClient();
  const target = `${request.universe}|${request.scope}|${request.instrument ?? ""}|${request.window ?? "24h"}`;
  const current = useRef(target);
  current.current = target;
  const inflight = useRef<AbortController | null>(null);
  const [result, setResult] = useState<{ key: string; value: NewsSynthesis; tookS: number } | null>(null);
  const [status, setStatus] = useState<{ key: string; state: "running" | "error"; startedAt: number } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [citedId, setCitedId] = useState<string | null>(null);
  useEffect(() => { setResult(null); setStatus(null); setCitedId(null); }, [target]);
  // A target change or unmount cancels an in-flight request; its result could only label the wrong instrument.
  useEffect(() => { current.current = target; return () => { current.current = ""; inflight.current?.abort(); inflight.current = null; }; }, [target]);
  const running = status?.key === target && status.state === "running";
  useEffect(() => {
    if (!running) return undefined;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(timer);
  }, [running]);
  const paid = ai.runtime === "PAID_API";
  const preview = useSynthesisPreview(request, visible && paid && ai.state === "AVAILABLE");
  const cite = (id: string | null) => { setCitedId(id); onCite?.(id); };
  const cited = useMemo<Cited[]>(() => result?.value.stories
    ?? (result?.value.story_ids ?? []).flatMap((id) => stories.filter((story) => story.story_id === id)), [result, stories]);

  const clearResult = () => { setResult(null); setStatus(null); setCitedId(null); };
  const engineSelect = <EngineSelect ai={ai} disabled={running} onChanged={clearResult} />;
  if (ai.state !== "AVAILABLE") {
    return <>{engineSelect}<p className="screener-panel-note">AI synthesis {ai.state === "NOT_CONFIGURED" ? "not configured" : "unavailable"}{ai.reason ? ` · ${ai.reason}` : ""}. Nothing is generated.</p>
      {remedy && <p className="screener-panel-note"><RemedyHint remedy={remedy} compact /></p>}</>;
  }
  const local = ai.runtime === "LOCAL_MODEL";
  const budget = ai.budget ?? null;
  const generate = async () => {
    const requested = target;
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    const startedAt = Date.now();
    setStatus({ key: requested, state: "running", startedAt });
    try {
      const value = await postNewsSynthesis(request, controller.signal);
      if (value.budget) applyBudget(client, request.universe, value.budget);
      // A result for a target that has since changed is discarded.
      if (current.current !== requested) return;
      setResult({ key: requested, value, tookS: Math.round((Date.now() - startedAt) / 1000) }); setStatus(null);
    } catch {
      if (current.current === requested && !controller.signal.aborted) setStatus({ key: requested, state: "error", startedAt });
    } finally {
      if (inflight.current === controller) inflight.current = null;
    }
  };
  const estimate = paid ? preview.data?.estimate ?? null : null;
  // "30 of 340 stories" when the model would see only part of what the scope matched.
  const storyText = !estimate ? "" : estimate.available_story_count != null && estimate.available_story_count > estimate.story_count
    ? `${estimate.story_count} of ${estimate.available_story_count} stories` : `${estimate.story_count} stories`;
  const cost = !estimate ? "" : estimate.cached ? " · cached, no cost"
    : estimate.tokens != null ? ` · ≈ ${compactTokens(estimate.tokens)} tokens, ${storyText}` : ` · ${storyText}`;
  const elapsed = running ? Math.max(0, Math.floor((now - (status?.startedAt ?? now)) / 1000)) : 0;
  return <>
    {engineSelect}
    <button type="button" className="screener-control" disabled={running} onClick={() => void generate()}
      title={estimate && !estimate.cached && estimate.tokens != null ? "Worst case reserved against today's budget; actual usage is usually lower." : undefined}>
      {running ? "Generating…" : `Generate AI synthesis${cost}`}</button>
    {running && <span className="news-ai-elapsed"><span aria-hidden="true"> {elapsed} s</span>{local ? " · local runs typically take 30–45 s" : ""}
      <span className="sr-only" role="status">Generating AI synthesis</span></span>}
    <span className="screener-panel-note"> {ai.model_id ? `Model ${ai.model_id}${local ? " (local, no API cost)" : ""}. ` : ""}Runs only when requested.
      {local && ai.reason === "STARTS_ON_REQUEST" ? " The local model starts on the first request (allow up to a minute)." : ""}
      {budget ? ` Paid API · today ${budget.requests}/${budget.max_requests} requests · ${compactTokens(budget.tokens)}/${compactTokens(budget.max_tokens)} tokens (hard daily limit, shared by all paid engines).` : ""}</span>
    {status?.key === target && status.state === "error" && <p className="screener-panel-note" role="alert">AI synthesis request failed.</p>}
    {result?.key === target && <SynthesisBlock result={result.value} cited={cited} citedId={citedId} onCite={cite} universe={request.universe}
      tookS={result.tookS} showInputs={showInputs} />}
  </>;
}

/** Universe-wide synthesis ("what's moving {universe}") over the current window's feed. */
export function UniverseSynthesis({ universe, universeLabel, window }: { universe: ScreenerUniverse; universeLabel: string; window: NewsWindowId }) {
  const request: SynthesisRequest = { universe, scope: "UNIVERSE", window };
  const preview = useSynthesisPreview(request, true);
  const ai = preview.data?.ai;
  return <section className="news-brief news-universe-ai" aria-label="Universe AI synthesis">
    <h2>AI synthesis · what&apos;s moving {universeLabel} <span className="news-class">AI</span></h2>
    {ai ? <SynthesisControl key={`${universe}|${window}`} request={request} ai={ai} stories={[]} showInputs />
      : preview.isError ? <p className="news-meta" role="alert">AI synthesis status unavailable. <button type="button" onClick={() => void preview.refetch()}>Retry</button></p>
      : <p className="news-meta" role="status">Checking AI synthesis…</p>}
  </section>;
}
