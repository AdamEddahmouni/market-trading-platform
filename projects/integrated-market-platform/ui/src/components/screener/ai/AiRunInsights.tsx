import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { aiScopeKey, fetchAiScreenerHistory, type AiScreenerHistoryRun, type AiScreenerReason, type AiScreenerScope } from "../../../api/screenerAi";
import { compactTokens } from "../news/SynthesisControl";
import { ErrorDetail, etClock } from "../panels/shared";
import { plainReason } from "./AiStatusStrip";

const CAPABILITY: Record<string, string> = { QUOTE: "Quote", TECHNICALS: "Technicals", ORDER_FLOW: "Order flow", NEWS: "News", SENTIMENT: "Sentiment",
  LEVEL2: "Depth", OPTIONS: "Options", FUTURES: "Futures", RATES: "Rates", CVD: "CVD", SQUEEZE: "Squeeze", FUNDAMENTALS: "Fundamentals", CROSS_ASSET: "Cross-asset" };
const BLOCK_REASON: Record<string, string> = { NO_OBSERVATION_TIME: "no observation time", AGE_EXCEEDS_POLICY: "too old", NO_USABLE_FACTS: "no usable values",
  SESSION_CLOSED: "market closed", FLOW_QUALITY_OR_WINDOW_INSUFFICIENT: "flow window incomplete" };
const words = (code: string) => code.replace(/_/g, " ").toLowerCase();

/** "Technicals blocked: no observation time · all 20", "Quote blocked: too old · LABT", "No news story · 18 of 20". */
export function reasonText(reason: AiScreenerReason) {
  const what = reason.kind === "NO_NEWS" ? "No news story" : reason.kind === "INSUFFICIENT" ? "Not enough current evidence"
    : `${CAPABILITY[reason.capability ?? ""] ?? words(reason.capability ?? "evidence")} blocked${reason.reason ? `: ${BLOCK_REASON[reason.reason] ?? words(reason.reason)}` : ""}`;
  const where = reason.count === reason.of ? `all ${reason.of}` : reason.count <= reason.symbols.length ? reason.symbols.join(", ") : `${reason.count} of ${reason.of}`;
  return `${what} · ${where}`;
}

/**
 * Why a pass had little to select from, as short chips read from its evidence packet. The codes stay in each chip's
 * title. The model's own wording is kept separate, behind a disclosure, because it is prose and not evidence.
 */
export function AiReasonChips({ reasons, limitations }: { reasons: AiScreenerReason[]; limitations: string[] }) {
  if (!reasons.length && !limitations.length) return null;
  return <div className="ai-reasons">
    {reasons.length > 0 && <ul className="ai-reason-chips" aria-label="What limited this pass">{reasons.map((reason) =>
      <li key={`${reason.kind}|${reason.capability}|${reason.reason}`} title={[reason.capability, reason.reason, `${reason.count} of ${reason.of}`, reason.symbols.join(", ")].filter(Boolean).join(" · ")}>{reasonText(reason)}</li>)}</ul>}
    {limitations.length > 0 && <details className="ai-reason-prose"><summary>The model's own explanation</summary>{limitations.map((item) => <p key={item}>{item}</p>)}</details>}
  </div>;
}

function change(run: AiScreenerHistoryRun) {
  if (run.added === null || run.removed === null) return "first stored pass of this query";
  if (!run.added.length && !run.removed.length) return "no change";
  return [run.added.length ? `added ${run.added.join(", ")}` : null, run.removed.length ? `removed ${run.removed.join(", ")}` : null].filter(Boolean).join(" · ");
}

/**
 * Stored passes, newest first, with what each added or removed against the previous pass of the same Screener
 * query. Read only when opened; includes passes made by the scheduled loop.
 */
export function AiRunHistory({ scope }: { scope: AiScreenerScope }) {
  const [open, setOpen] = useState(false);
  const history = useQuery({ queryKey: ["screener-ai-screener-history"], queryFn: ({ signal }) => fetchAiScreenerHistory(20, signal), enabled: open, staleTime: 5_000, retry: false });
  const question = aiScopeKey(scope);
  return <details className="ai-run-history" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>Run history</summary>
    {open && history.isPending && <p role="status">Loading stored passes…</p>}
    {history.isError && <p role="alert">Run history is unavailable.<ErrorDetail error={history.error} /></p>}
    {history.data && (history.data.runs.length === 0 ? <p>No pass has been stored on this machine yet.</p> : <table>
      <caption>The latest {history.data.runs.length} stored passes on this machine, including automatic ones</caption>
      <thead><tr><th scope="col">Finished</th><th scope="col">Engine</th><th scope="col">Result</th><th scope="col">Selected</th><th scope="col">Tokens</th><th scope="col">Model time</th><th scope="col">Against the previous pass</th></tr></thead>
      <tbody>{history.data.runs.map((run) => {
        const other = aiScopeKey(run.scope as AiScreenerScope) !== question;
        const tokens = (run.tokens_input ?? 0) + (run.tokens_output ?? 0);
        return <tr key={run.candidate_run_id} className={other ? "ai-run-history-other" : undefined}>
          <th scope="row">{etClock(run.generated_at)}{other ? ` · other scope (${run.scope.universe ?? "unknown"})` : ""}</th>
          <td>{run.model_id ?? "none"}{run.runtime ? ` · ${run.runtime === "LOCAL_MODEL" ? "local" : "paid"}` : ""}</td>
          <td title={run.reason ?? run.state}>{run.state === "CURRENT" ? "selected" : run.state === "NO_GROUNDED_CANDIDATES" ? "nothing selected" : plainReason(run.reason ?? run.state)}</td>
          <td>{run.selected_count} of {run.intake_count ?? "?"}{run.selected.length ? ` · ${run.selected.map((pick) => pick.instrument_id).join(", ")}` : ""}</td>
          <td>{run.cache === "HIT" ? "cached" : tokens ? compactTokens(tokens) : "—"}</td>
          <td>{run.cache === "HIT" || run.latency_ms == null ? "—" : `${(run.latency_ms / 1000).toFixed(1)}s`}</td>
          <td>{change(run)}</td>
        </tr>;
      })}</tbody></table>)}
  </details>;
}
