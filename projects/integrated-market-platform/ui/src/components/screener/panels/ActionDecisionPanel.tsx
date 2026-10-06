import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { actionHistory, prepareAction, previewAction, runAction, type ActionDecision, type ActionPreview } from "../../../api/screenerAction";
import { workspacePathForInstrument } from "../../../api/instrumentIdentity";
import { canUsePaperActions } from "../../mode-session/modeAuthority";
import NextSessionPanel from "./NextSessionPanel";

function PaperHandoff({ decision, permitted, onError }: { decision: ActionDecision; permitted: boolean; onError: () => void }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const current = useRef(decision.decision_id); current.current = decision.decision_id;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  return <button type="button" disabled={!permitted || busy} onClick={() => {
    const identifier = decision.decision_id;
    setBusy(true);
    void prepareAction(identifier).then((draft) => {
      if (mounted.current && current.current === identifier) navigate(workspacePathForInstrument(draft.instrumentId), { state: draft });
    }).catch(() => { if (mounted.current) onError(); }).finally(() => { if (mounted.current) setBusy(false); });
  }}>{decision.action_state === "EXIT" ? "Prepare Paper Exit" : "Prepare Paper Preview"}</button>;
}

function DecisionRecord({ decision }: { decision: ActionDecision }) {
  const snapshot = decision.evidence_snapshot;
  return <>
    <h4>{decision.action_state.replace(/_/g, " ")}</h4>
    <p>Direction: {decision.direction ?? "Unavailable"} · Position: {decision.position.state} · {decision.position.quantity} units</p>
    <p>{decision.rationale}</p>
    <p>Uncertainties: {decision.model_proposal?.uncertainties.join(", ") || "None disclosed"}</p>
    <p>Decision time {decision.decision_time} · Evidence cutoff {snapshot.cutoff} · Valid until {decision.valid_until}</p>
    {decision.reference_quote && <p>Decision reference price: {decision.reference_quote.source_value ?? "Unavailable"} · as of {decision.reference_quote.as_of ?? "Unavailable"}. Paper preview price and simulated fill are recorded separately.</p>}
    {(["entry_plan", "hold_plan", "exit_plan"] as const).map((plan) => <section key={plan} aria-label={plan.replace(/_/g, " ")}>
      <h5>{plan.replace(/_/g, " ")}</h5>
      {decision[plan].length ? decision[plan].map((condition) => <p key={condition.condition_id}>{condition.condition_id} · {condition.status} · source {condition.source} · valid until {condition.valid_until}</p>) : <p>Unavailable / not applicable</p>}
    </section>)}
    <p>Execution readiness: {decision.execution_readiness} · Risk: {decision.risk_decision_ref ? JSON.stringify(decision.risk_decision_ref) : "NOT_PREVIEWED"}</p>
    <p>Blockers: {decision.blocker_codes.join(", ") || "None"}</p>
    <p>Supporting: {decision.supporting_refs.join(", ") || "None"}</p>
    <p>Conflicting: {decision.conflicting_refs.join(", ") || "None"}</p>
    <p>Weak: {decision.weak_refs.join(", ") || "None"} · Missing: {decision.missing_capabilities.join(", ") || "None"}</p>
    <p>Governed Opportunity: {decision.opportunity_id ?? "Unavailable — candidate has no governed Opportunity lineage"}</p>
    <p>Model: {decision.model.provider_id} · {decision.model.model_id} · {decision.model.prompt_id}</p>
    <details><summary>Immutable evidence snapshot</summary>
      <p>{decision.evidence_snapshot_id} · {decision.decision_trace_id}</p>
      {[...snapshot.evidence.current_market_evidence, ...snapshot.evidence.reference_evidence].map((e) => <details key={e.evidence_id}>
        <summary>{e.evidence_id} · {e.capability}</summary><p>{e.source} · {e.as_of} · valid until {e.valid_until}</p><code>{JSON.stringify(e.facts)}</code>
      </details>)}
      <details><summary>Position, Opportunity, policy and candidate provenance</summary><code>{JSON.stringify(snapshot)}</code></details>
    </details>
  </>;
}

export default function ActionDecisionPanel({ runId, instrumentId }: { runId: string; instrumentId: string }) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<ActionPreview | null>(null);
  const [decision, setDecision] = useState<ActionDecision | null>(null);
  const [history, setHistory] = useState<ActionDecision[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [opportunity, setOpportunity] = useState("");
  const identity = `${runId}|${instrumentId}`;
  const current = useRef(identity); current.current = identity;
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++; controller.current?.abort(); setOpen(false); setPreview(null); setDecision(null); setHistory([]); setBusy(false); setError(false); setOpportunity("");
    return () => { generation.current++; controller.current?.abort(); };
  }, [identity]);
  // Display-only expiry clock; never reevaluates a decision or calls a model.
  useEffect(() => { if (!decision) return; const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, [decision]);
  const request = async (task: (signal: AbortSignal) => Promise<void>) => {
    const key = identity; const version = ++generation.current;
    controller.current?.abort(); const c = new AbortController(); controller.current = c;
    setBusy(true); setError(false);
    try { await task(c.signal); } catch { if (current.current === key && version === generation.current && !c.signal.aborted) setError(true); }
    finally { if (current.current === key && version === generation.current) setBusy(false); }
  };
  const expired = Boolean(decision && Date.parse(decision.valid_until) <= now);
  const permitted = canUsePaperActions("PAPER", Boolean(preview?.paper_authority), preview?.paper_authority ? { execution_mode: "INTERNAL_SIMULATION", execution_authority: "PAPER_ONLY" } : undefined);
  return <section className="action-decision" aria-label={`Decision assessment for ${instrumentId}`}>
    <button type="button" disabled={busy} onClick={() => {
      setOpen(true);
      void request(async (signal) => { const value = await previewAction(runId, instrumentId, signal); if (!signal.aborted && current.current === identity) setPreview(value); });
    }}>Open decision assessment</button>
    {open && <>
      {error && <p role="alert">Decision request failed or requires revalidation. Retry explicitly.</p>}
      {preview && <>
        <p>Current position: {preview.position.state} · {preview.position.quantity} units · Governed Opportunity: {preview.opportunity_id ?? "Unavailable"}</p>
        <p>Cutoff {preview.decision_cutoff} · Candidate valid until {preview.candidate_valid_until} · {preview.provider_id} · {preview.model_id}</p>
        <p>Paper authority: {preview.paper_authority ? "Available for independent preview" : "Unavailable"}</p>
        <label>Governed Opportunity <select aria-label="Governed Opportunity" value={opportunity} disabled={busy} onChange={(event) => {
          const selected = event.target.value; setOpportunity(selected); setDecision(null);
          void request(async (signal) => { const value = await previewAction(runId, instrumentId, signal, selected); if (!signal.aborted && current.current === identity) setPreview(value); });
        }}><option value="">Evidence lineage only</option>{(preview.available_opportunities ?? []).map((item) => <option key={item.opportunity_id} value={item.opportunity_id}>{item.opportunity_id} · {item.direction}</option>)}</select></label>
        <button type="button" disabled={busy || !preview.candidate_current} onClick={() => void request(async (signal) => {
          const value = await runAction(runId, instrumentId, signal, opportunity); if (!signal.aborted && current.current === identity) { setDecision(value); setNow(Date.now()); }
        })}>{busy ? "Evaluating…" : "Evaluate Decision"}</button>
      </>}
      {decision && <section aria-label="Current decision"><p>CURRENT DECISION</p><DecisionRecord decision={decision} />
        {expired && <p role="status">Expired — revalidation required.</p>}
        {!expired && decision.execution_readiness === "PREVIEW_ALLOWED" && (decision.action_state === "ENTER" || decision.action_state === "EXIT") &&
          <PaperHandoff key={decision.decision_id} decision={decision} permitted={permitted} onError={() => setError(true)} />}
        <p>Evaluation places no order. Workspace requires a fresh risk preview and explicit confirmation.</p>
        <NextSessionPanel decisionId={decision.decision_id} actionState={decision.action_state} />
      </section>}
      <button type="button" disabled={busy} onClick={() => void request(async (signal) => {
        const value = await actionHistory(instrumentId, signal); if (!signal.aborted && current.current === identity) setHistory(value.decisions);
      })}>Read decision history</button>
      {history.map((item) => <details key={item.decision_id}><summary>{item.decision_time} · {item.previous_state ?? "Initial"} → {item.action_state}</summary><DecisionRecord decision={item} /><NextSessionPanel decisionId={item.decision_id} actionState={item.action_state} /></details>)}
    </>}
  </section>;
}
