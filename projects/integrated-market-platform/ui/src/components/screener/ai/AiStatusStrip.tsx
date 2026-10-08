import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AiScreenerRun, AiScreenerRuns, AiScreenerScope } from "../../../api/screenerAi";
import { reevaluationStatus, stopReevaluation, type ReevaluationStatus } from "../../../api/screenerReevaluation";
import { compactTokens } from "../news/SynthesisControl";
import { ErrorDetail, etClock, useNow } from "../panels/shared";
import { coverageStatusText } from "./AiCoverage";
import { currentStageText, modelCallContext, modelCallInFlight, progressText } from "./AiRunProgress";
import { useAiScreenerRuns } from "./useAiScreenerRuns";

export const LOOP_STATUS_KEY = ["screener-reevaluation-status"] as const;

/** Reason codes in plain words; the code stays visible underneath so it can be searched. */
const REASONS: Record<string, string> = {
  SYNTHESIS_DAILY_BUDGET_EXHAUSTED: "today's model budget is used up",
  SYNTHESIS_DAILY_TOKEN_LIMIT: "the run would exceed today's token budget",
  SYNTHESIS_DAILY_REQUEST_LIMIT: "today's request limit is reached",
  ANTHROPIC_API_KEY_NOT_SET: "no API key is set for the selected engine",
  NO_SYNTHESIS_PROVIDER_CONFIGURED: "no AI engine is set up on this machine",
  EVIDENCE_PACKET_BOUND_EXCEEDED: "too much evidence for one call",
  INSUFFICIENT_EVIDENCE: "no candidate had enough current evidence",
  AI_COVERAGE_BUDGET_INSUFFICIENT: "today's budget cannot pay for every eligible row plus the global comparison",
  PROVISIONAL_PARTIAL_COVERAGE: "the run did not finish, so the universe was not fully searched",
  UNIVERSE_ENUMERATION_FAILED: "the Screener result could not be read completely",
  STOPPED: "stopped by the operator before it finished",
  EVIDENCE_PROVIDER_UNAVAILABLE: "the quote source returned nothing, so no row could be assessed",
  SYNTHESIS_RUN_HOLD_EXHAUSTED: "a request outgrew the budget held for this run",
};
export const plainReason = (code: string | null | undefined) => !code ? "no reason reported" : REASONS[code] ? `${REASONS[code]} (${code})` : code;

/** "2:13", or "1:02:13" past the hour. */
export function countdown(ms: number) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const hours = Math.floor(total / 3600), minutes = Math.floor((total % 3600) / 60), seconds = total % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}` : `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function lastPass(latest: AiScreenerRun | null, now: number) {
  if (!latest) return "no pass since the server started";
  const at = etClock(latest.finished_at);
  if (latest.state === "FAILED" || !latest.summary) return `last pass ${at} failed (${plainReason(latest.error?.code)})`;
  const summary = latest.summary;
  const coverage = summary.coverage;
  // A run that did not finish is never summarised as a count of selections: it says what was and was not evaluated.
  if (coverage && !coverage.selection_complete) return `last pass ${at} incomplete · ${coverage.ai_evaluated_count.toLocaleString()} of ${coverage.eligible_count.toLocaleString()} eligible rows AI-evaluated (${plainReason(coverage.status)})`;
  if (summary.state !== "CURRENT" && summary.state !== "NO_GROUNDED_CANDIDATES") return `last pass ${at} gave no result (${plainReason(summary.reason ?? summary.state)})`;
  const left = summary.valid_until ? Date.parse(summary.valid_until) - now : null;
  const searched = coverage ? `${coverage.ai_evaluated_count.toLocaleString()} AI-evaluated of ${(coverage.universe_count ?? 0).toLocaleString()} rows` : `${summary.intake_count ?? "?"} intake rows`;
  return `last pass ${at} · ${summary.selected.length} selected · ${searched}${left === null || !summary.selected.length ? "" : left > 0 ? ` · evidence expires in ${countdown(left)}` : " · evidence expired"}`;
}

/** The scheduled loop, read only. A cycle re-runs the AI Screener only when the candidate list has changed materially. */
function loopText(loop: ReevaluationStatus | undefined, failed: boolean, now: number) {
  if (failed) return "automatic passes: status unavailable";
  if (!loop) return "automatic passes: checking";
  if (loop.worker_state === "NOT_CONFIGURED") return "automatic passes not configured";
  if (loop.worker_state === "RUNNING" || loop.worker_state === "DELAYED") {
    const left = loop.next_scheduled ? Date.parse(loop.next_scheduled) - now : null;
    return left !== null && left > 0 ? `next automatic cycle in ${countdown(left)}` : loop.worker_state === "DELAYED" ? "automatic cycle delayed" : "automatic cycle due";
  }
  return `automatic passes: ${loop.worker_label.toLowerCase()}`;
}

function mainText(data: AiScreenerRuns, loop: string, now: number) {
  if (data.state === "RUNNING" && data.active) {
    const run = data.active;
    const counts = progressText(run);
    return `${run.stop_requested ? "Stopping after the call in flight" : "Running"} · ${currentStageText(run)} · ${run.engine.model_id ?? "no model"}${counts ? ` · ${counts}` : ""}`;
  }
  if (data.state === "WAITING_FOR_BUDGET") {
    const reset = data.budget ? ` · resets ${etClock(data.budget.resets_at)} (in ${countdown(Date.parse(data.budget.resets_at) - now)})` : "";
    return `Waiting for budget · ${data.ai.reason ? plainReason(data.ai.reason) : "today's shared budget is used up"}${reset}`;
  }
  if (data.state === "NOT_CONFIGURED") return `Not configured · ${plainReason(data.ai.reason)}`;
  if (data.state === "BLOCKED") return `Blocked · ${plainReason(data.ai.reason)}`;
  return `Idle · ${lastPass(data.latest, now)} · ${loop}`;
}

function budgetText(data: AiScreenerRuns) {
  const budget = data.budget;
  if (!budget) return data.ai.runtime === "LOCAL_MODEL" ? "Local model · no API cost" : data.ai.runtime ? "No shared budget reported" : null;
  const held = data.active ? budget.held_tokens ?? 0 : 0;
  const spent = data.latest?.summary?.coverage?.budget;
  const used = spent ? (spent.tokens_input ?? 0) + (spent.tokens_output ?? 0) : 0;
  return `Budget ${compactTokens(budget.tokens)} / ${compactTokens(budget.max_tokens)} tokens · ${budget.requests_left} of ${budget.max_requests} requests left${
    held > 0 ? ` · this run holds ${compactTokens(held)}` : used > 0 ? ` · last run used ${compactTokens(used)}` : ""}`;
}

function budgetDetail(data: AiScreenerRuns) {
  const budget = data.budget;
  if (!budget) return undefined;
  return `${budget.run_size !== null ? `The last run held ${budget.run_size.toLocaleString()} tokens for its whole plan. A different Screener query needs a different amount; each run states what it needs before any model call. ` : "No run has held tokens yet. Each run states what it needs before any model call. "}`
    + `${budget.requests_left} of ${budget.max_requests} requests and ${budget.headroom.toLocaleString()} of ${budget.max_tokens.toLocaleString()} tokens left for UTC day ${budget.day}. Shared by every paid AI feature on this machine.`;
}

/**
 * Always-visible AI status for the Main Screener: whether a model is working, on what, at which stage and for how
 * long, what the budget still allows, and when evidence expires. It reads server state and starts nothing on its own;
 * "Run now" is the same explicit operator action as the panel's Run AI Screener.
 */
export default function AiStatusStrip({ scope, onOpen }: { scope: AiScreenerScope; onOpen: () => void }) {
  const client = useQueryClient();
  const { runs, start, stop: stopRun } = useAiScreenerRuns(true);
  const loop = useQuery({ queryKey: LOOP_STATUS_KEY, queryFn: ({ signal }) => reevaluationStatus(signal), refetchInterval: 15_000, retry: false });
  const stop = useMutation({ mutationFn: () => stopReevaluation(), onSettled: () => client.invalidateQueries({ queryKey: LOOP_STATUS_KEY }) });
  const data = runs.data;
  const now = useNow(1_000, Boolean(data));
  const looping = loop.data?.worker_state === "RUNNING" || loop.data?.worker_state === "DELAYED";
  const call = data?.active && modelCallInFlight(data.active) ? modelCallContext(data.active) : undefined;
  const interrupted = data?.interrupted?.[data.interrupted.length - 1];
  return <section className={`ai-strip ${data ? data.state.toLowerCase() : "unknown"}`} aria-label="AI status">
    <span className="ai-strip-tag">AI</span><span className="ai-strip-dot" aria-hidden="true" />
    {/* The engine every AI panel on this machine uses; a run in progress names its own model in the line itself. */}
    {data && data.state !== "RUNNING" && data.ai.model_id && <span className="ai-strip-engine" title="The engine used by every AI panel on this machine">
      {data.ai.model_id} · {data.ai.runtime === "LOCAL_MODEL" ? "local" : "paid"}</span>}
    {/* Not a live region: this line changes every second while a model works, and announcing that would drown everything else. */}
    {data ? <p className="ai-strip-main">{mainText(data, loopText(loop.data, loop.isError, now), now)}{call ? ` · ${call}` : ""}</p>
      : runs.isError ? <p className="ai-strip-main">Status unavailable; a run may still be in progress on the server.<ErrorDetail error={runs.error} /></p>
      : <p className="ai-strip-main">Checking AI status…</p>}
    {data && budgetText(data) && <p className="ai-strip-budget" title={budgetDetail(data)}>{budgetText(data)}</p>}
    {start.isError && <p className="ai-strip-error" role="alert">Could not start a run.<ErrorDetail error={start.error} /></p>}
    {stop.isError && <p className="ai-strip-error" role="alert">Could not stop automatic passes.</p>}
    {stopRun.isError && <p className="ai-strip-error" role="alert">Could not stop the run.<ErrorDetail error={stopRun.error} /></p>}
    {/* Shown until a later run has finished: after that the latest pass is the news. */}
    {data && !data.active && !data.latest && interrupted && <p className="ai-strip-error">{coverageStatusText(interrupted.status ?? "INTERRUPTED")} · {interrupted.calls_completed ?? 0} model {interrupted.calls_completed === 1 ? "call" : "calls"} had finished{interrupted.unknown_provider_outcomes ? ` · ${interrupted.unknown_provider_outcomes} had no recorded outcome and ${interrupted.unknown_provider_outcomes === 1 ? "stays" : "stay"} charged` : ""}. Nothing was resumed.</p>}
    <div className="ai-strip-actions">
      {data?.active && <button type="button" disabled={stopRun.isPending || data.active.stop_requested === true} onClick={() => stopRun.mutate(data.active!.run_id)}
        title="No further model call starts. A call already sent is not cancelled and its tokens stay charged; finished batches are kept as provisional.">{data.active.stop_requested ? "Stopping…" : "Stop run"}</button>}
      {looping && <button type="button" disabled={stop.isPending} onClick={() => stop.mutate()} title="Stops the scheduled loop. A model call already in flight finishes; nothing is submitted.">Stop automatic passes</button>}
      {data?.state === "IDLE" && <button type="button" disabled={start.isPending || scope.settled === false} onClick={() => start.mutate(scope)}
        title="Assesses every row of the current Screener query and sends each eligible row to the model in batches. The run plans its whole cost first and calls no model if today's budget cannot pay for it.">Run now</button>}
      <button type="button" onClick={onOpen}>Open</button>
    </div>
  </section>;
}
