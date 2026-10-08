import type { AiScreenerRun } from "../../../api/screenerAi";

export const STAGE_LABEL: Record<string, string> = { ENUMERATION: "Reading every Screener row", ELIGIBILITY: "Checking evidence for every row",
  PLANNING: "Planning batches and budget", BUDGET_HELD: "Budget held for the whole run", BATCH_INFERENCE: "Model batches",
  GLOBAL_REDUCTION: "Comparing batch finalists", STORED: "Storing the result",
  TOKEN_PLANNING: "Measuring request requirements", REUSE_ASSESSMENT: "Checking valid earlier inference", COMPACTION: "Packing equivalent evidence" };
const SHORT_LABEL: Record<string, string> = { ENUMERATION: "reading rows", ELIGIBILITY: "checking evidence", PLANNING: "planning", BUDGET_HELD: "budget held",
  BATCH_INFERENCE: "batch", GLOBAL_REDUCTION: "comparing finalists", STORED: "storing",
  TOKEN_PLANNING: "measuring requests", REUSE_ASSESSMENT: "checking reuse", COMPACTION: "packing evidence" };
/** The step a bounded call is in, inside the batch or comparison stage. */
const STEP_LABEL: Record<string, string> = { PACKET: "building the packet", BUDGET_RESERVED: "budget reserved", MODEL_CALL: "model call", VALIDATION: "checking the answer" };
const number = (value: unknown) => typeof value === "number" ? value : null;
const inCall = (run: AiScreenerRun) => run.stage === "BATCH_INFERENCE" || run.stage === "GLOBAL_REDUCTION";

/** True while a request is with the model: the only time slow and stuck need telling apart. */
export const modelCallInFlight = (run: AiScreenerRun) => inCall(run) && run.stages[run.stages.length - 1]?.detail.step === "MODEL_CALL";

/** "4,630 rows · 4,605 eligible · 150 evaluated": counts the server has produced so far, never a projection. */
export function progressText(run: AiScreenerRun) {
  const progress = run.progress ?? {};
  return [number(progress.universe_count) !== null ? `${progress.universe_count!.toLocaleString()} rows` : null,
    number(progress.eligible_count) !== null ? `${progress.eligible_count!.toLocaleString()} eligible` : null,
    number(progress.rows_evaluated) !== null ? `${progress.rows_evaluated!.toLocaleString()} AI-evaluated` : null,
    number(progress.batches_planned) !== null ? `${progress.batches_completed ?? 0} of ${progress.batches_planned} batches done` : null,
    number(progress.reused_batches) !== null ? progress.reused_batches + " reused batches" : null,
    number(progress.new_inference_requests) !== null ? progress.new_inference_requests + " new requests" : null,
  ].filter(Boolean).join(" · ");
}

export const seconds = (ms: number) => ms < 10_000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms / 1000)}s`;

/** "model call 7.0s": the stage the server is in and how long it has been there. Server-measured, never extrapolated. */
export function currentStageText(run: AiScreenerRun) {
  const entry = run.stages[run.stages.length - 1];
  if (!run.stage || !entry) return "starting";
  if (!inCall(run)) return `${SHORT_LABEL[run.stage] ?? run.stage} ${seconds(entry.elapsed_ms)}`;
  const batch = number(entry.detail.batch), total = number(entry.detail.batches_planned), step = typeof entry.detail.step === "string" ? entry.detail.step : null;
  const where = run.stage === "BATCH_INFERENCE" ? `batch ${batch ?? "?"} of ${total ?? "?"}` : `comparing finalists${number(entry.detail.round) !== null ? ` round ${entry.detail.round}` : ""}`;
  return `${where}${step ? ` · ${STEP_LABEL[step] ?? step}` : ""} · ${seconds(entry.elapsed_ms)} in this stage`;
}

/** What the model call is being compared against, so slow and stuck look different. */
export function modelCallContext(run: AiScreenerRun) {
  const typical = run.typical_latency_ms == null ? "no earlier call measured for this model"
    : `typical ${seconds(run.typical_latency_ms)} from ${run.typical_latency_samples} measured ${run.typical_latency_samples === 1 ? "call" : "calls"}`;
  return `${typical} · request times out at ${run.timeout_seconds}s`;
}

/**
 * Stage-by-stage progress of one full-universe run. Each stage shows the time the server measured and the counts it
 * has actually produced; there is no percentage derived from assumed model latency, and a stage that did not happen
 * says so.
 */
export default function AiRunProgress({ run }: { run: AiScreenerRun }) {
  const reached = new Map(run.stages.map((entry) => [entry.stage, entry]));
  const currentIndex = run.stage ? run.stage_order.indexOf(run.stage) : run.stage_order.length;
  const counts = progressText(run);
  return <section className="ai-run-progress" aria-label="AI Screener run progress">
    <p className="ai-run-progress-head" role="status">{run.state === "RUNNING" ? run.stop_requested ? "Stopping after the call in flight" : "Running" : run.state === "FAILED" ? "Failed" : "Finished"} · {run.state === "RUNNING" ? `${currentStageText(run)} · ` : ""}
      {run.engine.model_id ?? "no model"}{counts ? ` · ${counts}` : ""} · {seconds(run.elapsed_ms)} in total</p>
    <ol className="ai-run-stages">{run.stage_order.map((stage, index) => {
      const entry = reached.get(stage);
      const state = entry ? run.stage === stage ? "current" : "done" : index < currentIndex ? "skipped" : "pending";
      return <li key={stage} className={`ai-run-stage ${state}`} aria-current={state === "current" ? "step" : undefined}>
        <span>{STAGE_LABEL[stage] ?? stage}</span>
        <span>{entry ? seconds(entry.elapsed_ms) : state === "skipped" ? "not needed" : "—"}{entry && stage === "BUDGET_HELD" && typeof entry.detail.held_tokens === "number" ? ` · ${entry.detail.held_tokens.toLocaleString()} tokens and ${entry.detail.held_requests ?? "?"} requests held` : ""}
          {entry && stage === "BATCH_INFERENCE" && number(entry.detail.batches_planned) !== null ? ` · ${entry.detail.batches_completed ?? 0} of ${entry.detail.batches_planned} done` : ""}
          {entry && entry.detail.shared === true ? " · waiting on the same call started elsewhere" : ""}</span>
      </li>;
    })}</ol>
    {modelCallInFlight(run) && <p className="ai-screener-meta">{modelCallContext(run)}. Each batch is one request with no streaming; a batch answer is a finalist list, not a result.</p>}
  </section>;
}
