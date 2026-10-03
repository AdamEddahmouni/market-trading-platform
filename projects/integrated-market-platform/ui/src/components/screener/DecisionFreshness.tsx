import { useEffect, useState } from 'react';
import type { DecisionEvidence } from '../../api/decisionFreshness';
const label = (value: string) => value.replace(/_/g, ' ');
/** Server evaluates eligibility. Client only withdraws expired server assertions. */
export function useDecisionNow(inputs?: DecisionEvidence[]) {
  const [now, setNow] = useState(Date.now);
  const deadline = inputs?.map(item => item.valid_until ? Date.parse(item.valid_until) : Infinity).filter(time => time > now).sort((a,b)=>a-b)[0];
  useEffect(() => {
    setNow(Date.now());
    if (!deadline || !Number.isFinite(deadline)) return;
    const timer = window.setTimeout(() => setNow(Date.now()), Math.min(Math.max(0, deadline - Date.now()) + 1, 2_147_483_647));
    return () => window.clearTimeout(timer);
  }, [inputs, deadline]);
  return now;
}
export function currentFreshness(item: DecisionEvidence, now: number) {
  return item.valid_until && now >= Date.parse(item.valid_until) && item.freshness_status === "CURRENT" ? "STALE" : item.freshness_status;
}
export function DecisionFreshness({ inputs }: { inputs?: DecisionEvidence[] }) {
  const now = useDecisionNow(inputs);
  if (!inputs?.length) return null;
  return <div className="decision-freshness" aria-label="Decision input freshness">
    {inputs.map((item, index) => {
      const state = currentFreshness(item, now);
      const expired = state !== item.freshness_status;
      const decision = expired ? 'BLOCKED' : item.decision_admissibility;
      return <details key={`${item.capability}:${index}`}>
        <summary>{item.capability} · {label(item.delivery_mode)} · {label(state)} · {decision}</summary>
        <dl>
          <div><dt>Source</dt><dd>{item.source ?? 'Unavailable'}</dd></div>
          <div><dt>Currentness basis</dt><dd>{label(item.basis)}</dd></div>
          <div><dt>{item.delivery_mode === 'PUBLICATION_BASED' ? 'Observed / published' : 'Observation as of'}</dt><dd>{item.as_of ?? 'Unknown'}</dd></div>
          <div><dt>Received</dt><dd>{item.received_at ?? 'Unknown'}</dd></div>
          <div><dt>Fetched / retrieved</dt><dd>{item.fetched_at ?? 'Unknown'}</dd></div>
          <div><dt>Evaluated</dt><dd>{item.evaluated_at}</dd></div>
          {item.age_ms != null && <div><dt>Age at evaluation</dt><dd>{Math.round(item.age_ms / 1000)}s</dd></div>}
          <div><dt>Policy</dt><dd>{item.policy} · {item.policy_version}{item.stale_after_ms != null ? ` · ${item.stale_after_ms / 1000}s limit` : ' · cadence not verified'}</dd></div>
          <div><dt>Decision use</dt><dd>{decision} · current market: {!expired && item.eligible_for_current_decision ? 'eligible' : 'blocked'} · reference: {!expired && item.eligible_for_reference ? 'eligible' : 'blocked'}</dd></div>
          <div><dt>Reason</dt><dd>{expired ? 'SERVER_POLICY_EXPIRED' : item.reason_codes.join(' · ') || 'None'}</dd></div>
        </dl>
      </details>;
    })}
  </div>;
}
