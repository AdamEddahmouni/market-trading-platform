import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { workspacePathForInstrument } from "../../../api/instrumentIdentity";
import { tradeLifecycle, type TradeLifecycle } from "../../../api/screenerLifecycle";
import { canUsePaperActions } from "../../mode-session/modeAuthority";
import { PaperHandoff } from "../panels/ActionDecisionPanel";
import { ErrorDetail } from "../panels/shared";
import LifecycleDetail, { LifecycleFacts } from "./LifecycleDetail";
import { ORIGIN_LABEL, actionLabel, clock, codeText, evidenceCounts, stageLabel } from "./lifecyclePresentation";

/**
 * One AI-selected candidate or Paper position episode, summarised in text.
 * The summary comes from the list projection; evidence and history load on expansion.
 */
export default function LifecycleCard({ lifecycle, runId, children }: { lifecycle: TradeLifecycle; runId: string | null; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [handoffFailed, setHandoffFailed] = useState(false);
  const { decision, candidate } = lifecycle;
  // The cache identity carries every state a transition changes, so an expanded view never shows a superseded lifecycle.
  const detail = useQuery({
    queryKey: ["screener-trade-lifecycle", lifecycle.lifecycle_id, runId, lifecycle.stage, decision?.decision_id ?? null, lifecycle.entry.status,
      lifecycle.exit.status, lifecycle.risk_control.status, lifecycle.position.mark?.as_of ?? null],
    queryFn: ({ signal }) => tradeLifecycle(lifecycle.lifecycle_id, runId, signal), enabled: open, retry: false, staleTime: 5_000,
  });
  const heading = `${lifecycle.group === "SELECTED" && candidate?.rank != null ? `#${candidate.rank} ` : ""}${lifecycle.symbol}`;
  const exitReady = lifecycle.kind === "POSITION_EPISODE" && decision?.action_state === "EXIT" && decision.execution_readiness === "PREVIEW_ALLOWED"
    && lifecycle.freshness.decision_current === true && lifecycle.exit.status === "EXIT_DECIDED";
  const permitted = canUsePaperActions("PAPER", true, { execution_mode: "INTERNAL_SIMULATION", execution_authority: "PAPER_ONLY" });
  const panel = `lifecycle-detail-${lifecycle.lifecycle_id}`;
  return <article className="ai-screener-candidate lifecycle-card" data-testid={`lifecycle-card-${lifecycle.symbol}`} aria-label={`Trade lifecycle for ${lifecycle.symbol}`}>
    <header>
      <h3>{heading}</h3>
      <p className="lifecycle-stage" data-testid="lifecycle-stage">{stageLabel(lifecycle)}</p>
    </header>
    <p className="lifecycle-meta" data-testid="lifecycle-origin">
      {lifecycle.position_origin === "UNLINKED_PAPER_ACTIVITY" ? "Unlinked Paper activity — no AI candidate or decision lineage for this position"
        : lifecycle.group === "ACTIVE_MANAGED" ? `Active managed position — opened from AI Screener run selected ${clock(candidate?.selected_at)}${runId ? "; not selected by the latest run" : ""}`
          : lifecycle.kind === "POSITION_EPISODE" && candidate?.selected_in_current_run && !lifecycle.origin.same_as_current_run ? "Selected by this run · position opened from an earlier AI Screener run"
            : lifecycle.group === "RECENT_CLOSED" ? "AI-selected · closed episode" : "AI-selected candidate"}
    </p>
    <dl className="lifecycle-facts">
      <div data-testid="lifecycle-decision"><dt>Decision</dt><dd>
        {decision ? <><strong>{actionLabel(decision.action_state)}</strong> · {clock(decision.decision_time)} · {ORIGIN_LABEL[decision.origin]}{decision.origin === "DETERMINISTIC_RISK_CONTROL" ? " · Model: none" : ""}
          {lifecycle.freshness.decision_current === false && lifecycle.stage !== "POSITION_CLOSED" ? " · expired — needs fresh evidence" : ""}</> : "Not assessed yet"}
      </dd></div>
      <div data-testid="lifecycle-evidence"><dt>Evidence</dt><dd>{evidenceCounts(lifecycle)}</dd></div>
    </dl>
    <LifecycleFacts lifecycle={lifecycle} />
    {decision && decision.blocker_codes.length > 0 && lifecycle.stage !== "POSITION_CLOSED" && <div className="lifecycle-blockers" role="status" data-testid="lifecycle-blockers">
      <strong>{decision.action_state === "REVALIDATION_REQUIRED" ? "Decision needs fresh evidence" : "Blocked"}</strong>
      <ul>{decision.blocker_codes.map((code) => <li key={code}>{codeText(code)}</li>)}</ul>
    </div>}
    <div className="lifecycle-actions">
      <button type="button" aria-expanded={open} aria-controls={panel} onClick={() => setOpen((value) => !value)}>{open ? "Hide lifecycle" : "View lifecycle"}</button>
      {exitReady && decision && <PaperHandoff decision={decision} permitted={permitted} onError={() => setHandoffFailed(true)} />}
      {lifecycle.kind === "POSITION_EPISODE" && <>
        <Link to={workspacePathForInstrument(lifecycle.instrument_id)}>Open Paper Workspace</Link>
        <Link to="/portfolio">Open Portfolio</Link>
      </>}
    </div>
    {handoffFailed && <p role="alert">The Paper exit could not be prepared. The decision may have expired or changed; nothing was submitted.</p>}
    {exitReady && <p className="lifecycle-meta">Preparing opens the Paper Workspace. Nothing is submitted until you preview and confirm there.</p>}
    <div id={panel}>
      {open && detail.isPending && <p role="status">Loading lifecycle…</p>}
      {open && detail.isError && <p role="alert">Lifecycle detail is unavailable.<ErrorDetail error={detail.error} /></p>}
      {open && detail.data && <LifecycleDetail lifecycle={detail.data} />}
    </div>
    {children}
  </article>;
}
