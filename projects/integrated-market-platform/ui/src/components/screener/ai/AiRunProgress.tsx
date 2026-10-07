import type { AiScreenerRun } from "../../../api/screenerAi";

export const STAGE_LABEL: Record<string, string> = { SCOPE: "Reading the Screener scope", NEWS: "Reading news", EVIDENCE: "Gating evidence",
  PACKET: "Building the packet", BUDGET_RESERVED: "Budget reserved", MODEL_CALL: "Model call", VALIDATION: "Checking the answer", STORED: "Storing the result" };
const SHORT_LABEL: Record<string, string> = { SCOPE: "scope", NEWS: "news", EVIDENCE: "evidence", PACKET: "packet", BUDGET_RESERVED: "budget reserved",
  MODEL_CALL: "model call", VALIDATION: "checking the answer", STORED: "storing" };

export const seconds = (ms: number) => ms < 10_000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms / 1000)}s`;

/** "model call 7.0s": the stage the server is in and how long it has been there. Server-measured, never extrapolated. */
export function currentStageText(run: AiScreenerRun) {
  const entry = run.stages[run.stages.length - 1];
  return run.stage && entry ? `${SHORT_LABEL[run.stage] ?? run.stage} ${seconds(entry.elapsed_ms)}` : "starting";
}

/** What the model call is being compared against, so slow and stuck look different. */
export function modelCallContext(run: AiScreenerRun) {
  const typical = run.typical_latency_ms == null ? "no earlier call measured for this model"
    : `typical ${seconds(run.typical_latency_ms)} from ${run.typical_latency_samples} measured ${run.typical_latency_samples === 1 ? "call" : "calls"}`;
  return `${typical} · request times out at ${run.timeout_seconds}s`;
}

/**
 * Stage-by-stage progress of one run. The model call is a single request with no streaming, so there is no
 * percentage: each stage shows the time the server measured, and a stage that did not happen says so.
 */
export default function AiRunProgress({ run }: { run: AiScreenerRun }) {
  const reached = new Map(run.stages.map((entry) => [entry.stage, entry]));
  const currentIndex = run.stage ? run.stage_order.indexOf(run.stage) : run.stage_order.length;
  const call = reached.get("MODEL_CALL");
  const slow = run.stage === "MODEL_CALL" && call && run.typical_latency_ms != null && call.elapsed_ms > 2 * run.typical_latency_ms;
  return <section className="ai-run-progress" aria-label="AI Screener run progress">
    <p className="ai-run-progress-head" role="status">{run.state === "RUNNING" ? "Running" : run.state === "FAILED" ? "Failed" : "Finished"} · {run.state === "RUNNING" ? `${currentStageText(run)} · ` : ""}
      {run.engine.model_id ?? "no model"}{run.intake_count != null ? ` · ${run.intake_count} candidates` : ""}{run.packet_bytes != null ? ` · packet ${run.packet_bytes.toLocaleString()} bytes` : ""} · {seconds(run.elapsed_ms)} in total</p>
    <ol className="ai-run-stages">{run.stage_order.map((stage, index) => {
      const entry = reached.get(stage);
      const state = entry ? run.stage === stage ? "current" : "done" : index < currentIndex ? "skipped" : "pending";
      return <li key={stage} className={`ai-run-stage ${state}`} aria-current={state === "current" ? "step" : undefined}>
        <span>{STAGE_LABEL[stage] ?? stage}</span>
        <span>{entry ? seconds(entry.elapsed_ms) : state === "skipped" ? "not needed" : "—"}{entry && stage === "BUDGET_RESERVED" && typeof entry.detail.reserved_tokens === "number" ? ` · ${entry.detail.reserved_tokens.toLocaleString()} tokens held` : ""}
          {entry && stage === "MODEL_CALL" && entry.detail.shared === true ? " · waiting on the same call started elsewhere" : ""}</span>
      </li>;
    })}</ol>
    {run.stage === "MODEL_CALL" && <p className="ai-screener-meta">{slow ? "Slower than typical. " : ""}{modelCallContext(run)}. One request, no streaming: there is no partial answer to show.</p>}
  </section>;
}
