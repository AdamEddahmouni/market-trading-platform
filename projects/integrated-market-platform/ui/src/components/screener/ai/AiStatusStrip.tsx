import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AiScreenerRun, AiScreenerRuns, AiScreenerScope } from "../../../api/screenerAi";
import { reevaluationStatus, stopReevaluation, type ReevaluationStatus } from "../../../api/screenerReevaluation";
import { compactTokens } from "../news/SynthesisControl";
import { ErrorDetail, etClock, useNow } from "../panels/shared";
import { currentStageText, modelCallContext } from "./AiRunProgress";
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
  if (summary.state !== "CURRENT" && summary.state !== "NO_GROUNDED_CANDIDATES") return `last pass ${at} gave no result (${plainReason(summary.reason ?? summary.state)})`;
  const left = summary.valid_until ? Date.parse(summary.valid_until) - now : null;
  return `last pass ${at} · ${summary.selected.length} of ${summary.intake_count ?? "?"} selected${left === null ? "" : left > 0 ? ` · evidence expires in ${countdown(left)}` : " · evidence expired"}`;
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
    return `Running · ${currentStageText(run)} · ${run.engine.model_id ?? "no model"}${run.intake_count != null ? ` · ${run.intake_count} candidates` : ""}`;
  }
  if (data.state === "WAITING_FOR_BUDGET") {
    const reset = data.budget ? ` · resets ${etClock(data.budget.resets_at)} (in ${countdown(Date.parse(data.budget.resets_at) - now)})` : "";
    return `Waiting for budget · ${data.ai.reason ? plainReason(data.ai.reason) : "another run of the last measured size does not fit in today's budget"}${reset}`;
  }
  if (data.state === "NOT_CONFIGURED") return `Not configured · ${plainReason(data.ai.reason)}`;
  if (data.state === "BLOCKED") return `Blocked · ${plainReason(data.ai.reason)}`;
  return `Idle · ${lastPass(data.latest, now)} · ${loop}`;
}

function budgetText(data: AiScreenerRuns) {
  const budget = data.budget;
  if (!budget) return data.ai.runtime === "LOCAL_MODEL" ? "Local model · no API cost" : data.ai.runtime ? "No shared budget reported" : null;
  const held = data.active?.stages.find((entry) => entry.stage === "BUDGET_RESERVED")?.detail.reserved_tokens;
  const used = data.latest?.summary?.cache === "MISS" ? (data.latest.summary.tokens_input ?? 0) + (data.latest.summary.tokens_output ?? 0) : 0;
  return `Budget ${compactTokens(budget.tokens)} / ${compactTokens(budget.max_tokens)} tokens · ${budget.runs_left !== null
    ? `~${budget.runs_left} ${budget.runs_left === 1 ? "run" : "runs"} left` : `${budget.requests_left} of ${budget.max_requests} requests left · run size not yet measured`}${
    typeof held === "number" ? ` · this run holds ${compactTokens(held)}` : used > 0 ? ` · last run used ${compactTokens(used)}` : ""}`;
}

function budgetDetail(data: AiScreenerRuns) {
  const budget = data.budget;
  if (!budget) return undefined;
  return `${budget.per_run_tokens !== null ? `A run is counted as ${budget.per_run_tokens.toLocaleString()} tokens, the last amount reserved for this model. ` : "No run has reserved tokens yet, so runs left cannot be counted. "}`
    + `${budget.requests_left} of ${budget.max_requests} requests and ${budget.tokens_left.toLocaleString()} of ${budget.max_tokens.toLocaleString()} tokens left for UTC day ${budget.day}. Shared by every paid AI feature on this machine.`;
}

/**
 * Always-visible AI status for the Main Screener: whether a model is working, on what, at which stage and for how
 * long, what the budget still allows, and when evidence expires. It reads server state and starts nothing on its own;
 * "Run now" is the same explicit operator action as the panel's Run AI Screener.
 */
export default function AiStatusStrip({ scope, onOpen }: { scope: AiScreenerScope; onOpen: () => void }) {
  const client = useQueryClient();
  const { runs, start } = useAiScreenerRuns(true);
  const loop = useQuery({ queryKey: LOOP_STATUS_KEY, queryFn: ({ signal }) => reevaluationStatus(signal), refetchInterval: 15_000, retry: false });
  const stop = useMutation({ mutationFn: () => stopReevaluation(), onSettled: () => client.invalidateQueries({ queryKey: LOOP_STATUS_KEY }) });
  const data = runs.data;
  const now = useNow(1_000, Boolean(data));
  const looping = loop.data?.worker_state === "RUNNING" || loop.data?.worker_state === "DELAYED";
  const call = data?.active?.stage === "MODEL_CALL" ? modelCallContext(data.active) : undefined;
  return <section className={`ai-strip ${data ? data.state.toLowerCase() : "unknown"}`} aria-label="AI status">
    <span className="ai-strip-tag">AI</span><span className="ai-strip-dot" aria-hidden="true" />
    {/* Not a live region: this line changes every second while a model works, and announcing that would drown everything else. */}
    {data ? <p className="ai-strip-main">{mainText(data, loopText(loop.data, loop.isError, now), now)}{call ? ` · ${call}` : ""}</p>
      : runs.isError ? <p className="ai-strip-main">Status unavailable; a run may still be in progress on the server.<ErrorDetail error={runs.error} /></p>
      : <p className="ai-strip-main">Checking AI status…</p>}
    {data && budgetText(data) && <p className="ai-strip-budget" title={budgetDetail(data)}>{budgetText(data)}</p>}
    {start.isError && <p className="ai-strip-error" role="alert">Could not start a run.<ErrorDetail error={start.error} /></p>}
    {stop.isError && <p className="ai-strip-error" role="alert">Could not stop automatic passes.</p>}
    <div className="ai-strip-actions">
      {looping && <button type="button" disabled={stop.isPending} onClick={() => stop.mutate()} title="Stops the scheduled loop. A model call already in flight finishes; nothing is submitted.">Stop automatic passes</button>}
      {data?.state === "IDLE" && <button type="button" disabled={start.isPending || scope.settled === false} onClick={() => start.mutate(scope)}
        title={`Runs the AI Screener once for the current Screener scope.${data.budget?.per_run_tokens ? ` Reserves about ${data.budget.per_run_tokens.toLocaleString()} tokens.` : ""}`}>Run now</button>}
      <button type="button" onClick={onOpen}>Open</button>
    </div>
  </section>;
}
