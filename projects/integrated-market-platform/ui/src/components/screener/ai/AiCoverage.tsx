import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAiScreenerCoverage, type AiScreenerCoverage, type AiScreenerResult } from "../../../api/screenerAi";
import { compactTokens } from "../news/SynthesisControl";
import { ErrorDetail, PanelMessage } from "../panels/shared";

const STATUS_TEXT: Record<string, string> = {
  GLOBAL_SELECTION_COMPLETE: "Final · every eligible row was evaluated and the finalists were compared globally",
  COMPLETE_NO_SELECTION: "Final · every eligible row was evaluated and none was selected",
  NO_ELIGIBLE_ROWS: "Final · no row had enough current evidence, so no model was called",
  EMPTY_UNIVERSE: "Final · the Screener query matched no rows",
  EVIDENCE_PROVIDER_UNAVAILABLE: "Not run · the quote source returned nothing, so no row could be assessed; this says nothing about the rows",
  PROVISIONAL_PARTIAL_COVERAGE: "Partial · the run did not finish; this is not a search of the whole universe",
  AI_COVERAGE_BUDGET_INSUFFICIENT: "Not run · today's shared budget cannot pay for the whole plan; no model was called",
  UNIVERSE_ENUMERATION_FAILED: "Not run · the Screener result could not be read completely",
  STOPPED: "Stopped · the run was stopped before it finished; this is not a search of the whole universe",
  INTERRUPTED: "Interrupted · the server restarted during the run",
  FAILED: "Failed · the run did not finish",
};

export const coverageStatusText = (status: string) => STATUS_TEXT[status] ?? status;
const count = (value: number | null | undefined) => value == null ? "?" : value.toLocaleString();

/** One line of real accounting: rows read, assessed, eligible and actually evaluated by the model. */
export function coverageLine(coverage: AiScreenerCoverage) {
  const share = coverage.ai_coverage_pct == null ? "" : ` (${coverage.ai_coverage_pct}% of eligible)`;
  return `${count(coverage.universe_count)} rows · ${count(coverage.assessed_count)} assessed · ${count(coverage.eligible_count)} eligible · `
    + `${count(coverage.ai_evaluated_count)} AI-evaluated${share} · batch ${coverage.batches_completed} of ${coverage.batches_planned}`;
}

function budgetLine(coverage: AiScreenerCoverage) {
  const budget = coverage.budget;
  if (!budget.capped) return "Local or unbudgeted engine · no token or request cap applied.";
  const spent = `used ${compactTokens((budget.tokens_input ?? 0) + (budget.tokens_output ?? 0))} tokens`;
  if (budget.required_tokens == null) return `Shared budget · ${spent}.`;
  return `Shared budget · the plan needed ${compactTokens(budget.required_tokens)} tokens and ${budget.required_requests ?? "?"} requests · `
    + `${compactTokens(budget.available_tokens ?? 0)} tokens and ${budget.available_requests ?? "?"} requests were available · ${spent}.`;
}

/** The run's accounting, its status in plain words, and why every row that was not evaluated was not. */
export function CoverageSummary({ coverage }: { coverage: AiScreenerCoverage }) {
  const reasons = Object.entries(coverage.counts.reasons);
  const excluded = typeof coverage.reduction.finalists_excluded_count === "number" ? coverage.reduction.finalists_excluded_count : 0;
  return <section className="ai-coverage" aria-label="AI Screener coverage">
    <p className={`ai-coverage-status ${coverage.selection_complete ? "final" : "partial"}`} role="status">{coverageStatusText(coverage.status)}{coverage.reason && coverage.reason !== coverage.status ? ` · ${coverage.reason}` : ""}</p>
    <p className="ai-screener-meta">{coverageLine(coverage)} · {coverage.finalist_count} batch {coverage.finalist_count === 1 ? "finalist" : "finalists"} · {coverage.model_calls} model {coverage.model_calls === 1 ? "call" : "calls"}</p>
    {excluded > 0 && <p className="ai-screener-meta">{excluded} batch {excluded === 1 ? "finalist was" : "finalists were"} left out of the final comparison: no admissible current evidence at that cutoff.</p>}
    <p className="ai-screener-meta">Not evaluated: {count(coverage.counts.ineligible)} ineligible · {count(coverage.counts.evidence_blocked)} evidence missing, stale or unavailable · {count(coverage.counts.unprocessed)} eligible but not processed{coverage.reconciled ? "" : " · counts do not reconcile"}.</p>
    <p className="ai-screener-meta">{budgetLine(coverage)}</p>
    {reasons.length > 0 && <details><summary>Why rows were not evaluated · {reasons.length} {reasons.length === 1 ? "reason" : "reasons"}</summary>
      <ul>{reasons.map(([reason, rows]) => <li key={reason}>{reason} · {rows.toLocaleString()}</li>)}</ul>
    </details>}
  </section>;
}

/** Batch finalists of a run that did not finish. Shown for inspection only: no Action Decision is offered. */
export function ProvisionalFinalists({ result }: { result: AiScreenerResult }) {
  const finalists = result.provisional ?? [];
  if (!finalists.length) return null;
  return <section className="ai-coverage-provisional" aria-label="Provisional batch finalists">
    <PanelMessage tone="warn">Provisional · {finalists.length} batch {finalists.length === 1 ? "finalist" : "finalists"} from the batches that finished. They were never compared globally and cannot be evaluated for action.</PanelMessage>
    <ul>{finalists.map((item) => <li key={`${item.batch}|${item.instrument_id}`}>{item.instrument_id} · batch {item.batch} rank {item.rank_in_batch} · evidence cutoff {item.evidence_cutoff}<br />{item.rationale}</li>)}</ul>
  </section>;
}

/** Per-call receipts and rows that were not evaluated, read from the server's ledger only when opened. */
export function CoverageReceipts({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const receipts = useQuery({ queryKey: ["screener-ai-screener-coverage", runId], queryFn: ({ signal }) => fetchAiScreenerCoverage(runId, signal),
    enabled: open, staleTime: Infinity, retry: false });
  const skipped = receipts.data?.rows.items ?? [];
  return <details className="ai-coverage-receipts" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>Batch receipts and rows not evaluated</summary>
    {receipts.isPending && open && <p className="ai-screener-meta">Reading receipts…</p>}
    {receipts.isError && <PanelMessage tone="error" role="alert">Receipts for this run are unavailable.<ErrorDetail error={receipts.error} /></PanelMessage>}
    {receipts.data && <>
      <ol>{receipts.data.calls.map((call) => <li key={call.call_id}>{call.stage === "GLOBAL_REDUCTION" ? `Comparison round ${call.round ?? "?"}` : "Batch"} {call.index + 1} of {call.of} · {call.instrument_ids.length} rows · {call.outcome} · {call.state}{call.reason ? ` · ${call.reason}` : ""} · cutoff {call.evidence_cutoff} · {call.selected.length} selected{call.tokens_input != null ? ` · ${compactTokens((call.tokens_input ?? 0) + (call.tokens_output ?? 0))} tokens` : ""}</li>)}</ol>
      {receipts.data.unfinished_calls.length > 0 && <PanelMessage tone="warn">{receipts.data.unfinished_calls.length} model {receipts.data.unfinished_calls.length === 1 ? "call has" : "calls have"} no recorded outcome; the reserved tokens stay charged.</PanelMessage>}
      <p className="ai-screener-meta">Rows the model did not evaluate: showing {skipped.length.toLocaleString()} of {receipts.data.rows.total.toLocaleString()}.</p>
      <ul>{skipped.map((row) => <li key={row.instrument_id}>{row.instrument_id} · {row.class}{row.reasons.length ? ` · ${row.reasons.join(", ")}` : ""}</li>)}</ul>
    </>}
  </details>;
}
