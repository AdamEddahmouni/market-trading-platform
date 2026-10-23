import { useEffect, useState } from 'react';
import type { DecisionEvidence } from '../../api/decisionFreshness';
import { Code, codeWords, Stamp } from './screenerText';

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

const MODE_TEXT: Record<string, string> = { REALTIME: 'streamed', DELAYED: 'delayed', SNAPSHOT: 'snapshot', PUBLICATION_BASED: 'published',
  HISTORICAL: 'historical', REPLAY: 'replay', UNKNOWN: 'delivery unknown' };
const STATE_TEXT: Record<string, string> = { CURRENT: 'current', STALE: 'stale', UNAVAILABLE: 'unavailable', UNKNOWN: 'freshness unknown',
  SESSION_CLOSED: 'session closed' };
const USE_TEXT: Record<string, string> = { ADMISSIBLE: 'usable for decisions', DEGRADED: 'reference only', BLOCKED: 'not usable for decisions' };
const words = (map: Record<string, string>, code: string) => map[code] ?? codeWords(code).toLowerCase();
/** "streamed", "published", ...: a delivery mode in words. */
export const deliveryText = (mode: string) => words(MODE_TEXT, mode);
/** "current", "stale", ...: a freshness state in words. */
export const freshnessText = (state: string) => words(STATE_TEXT, state);
/** "movement:3" → "Movement 3", "quote" → "Quote". */
const capabilityText = (capability: string) => codeWords(capability.replace(/:/g, ' '));

type Effective = { item: DecisionEvidence; state: string; decision: string; expired: boolean };
const effective = (inputs: DecisionEvidence[], now: number): Effective[] => inputs.map((item) => {
  const state = currentFreshness(item, now);
  const expired = state !== item.freshness_status;
  return { item, state, decision: expired ? 'BLOCKED' : item.decision_admissibility, expired };
});

// Worst first: what most needs the operator's eye leads the roll-up.
const ROLLUP_ORDER = ['UNAVAILABLE', 'STALE', 'UNKNOWN', 'SESSION_CLOSED'];
export type FreshnessRollup = { tone: 'ok' | 'warn' | 'bad'; text: string };
/** One badge for all of a view's inputs: "All current", or what is not ("2 stale · 1 unavailable"). */
export function freshnessRollup(inputs: DecisionEvidence[] | undefined, now: number): FreshnessRollup | null {
  if (!inputs?.length) return null;
  const rows = effective(inputs, now);
  const counts = new Map<string, number>();
  for (const row of rows) if (row.state !== 'CURRENT') counts.set(row.state, (counts.get(row.state) ?? 0) + 1);
  if (!counts.size) return { tone: 'ok', text: 'All current' };
  const order = [...counts.keys()].sort((a, b) => (ROLLUP_ORDER.indexOf(a) + 1 || 99) - (ROLLUP_ORDER.indexOf(b) + 1 || 99));
  const blocked = rows.some((row) => row.decision === 'BLOCKED');
  return { tone: blocked ? 'bad' : 'warn', text: order.map((state) => `${counts.get(state)} ${words(STATE_TEXT, state)}`).join(' · ') };
}

/**
 * The evidence behind a view, collapsed under one "Data freshness" line with a roll-up badge. Each input reads as one
 * plain sentence; its server record (source, clocks, policy, reason codes) is one level further down.
 */
export function DecisionFreshness({ inputs }: { inputs?: DecisionEvidence[] }) {
  const now = useDecisionNow(inputs);
  if (!inputs?.length) return null;
  const rollup = freshnessRollup(inputs, now)!;
  return <details className="decision-freshness">
    <summary>Data freshness <span className={`decision-rollup ${rollup.tone}`}>{rollup.text}</span>
      <span className="decision-count"> · {inputs.length} {inputs.length === 1 ? 'input' : 'inputs'}</span></summary>
    <ul aria-label="Decision input freshness">
      {effective(inputs, now).map(({ item, state, decision, expired }, index) => <li key={`${item.capability}:${index}`}><details>
        <summary><span title={item.capability}>{capabilityText(item.capability)}</span> · <span title={item.delivery_mode}>{words(MODE_TEXT, item.delivery_mode)}</span>
          {' · '}<span title={state} className={state === 'CURRENT' ? undefined : 'decision-off'}>{words(STATE_TEXT, state)}</span>
          {' · '}<span title={decision}>{words(USE_TEXT, decision)}</span></summary>
        <dl>
          <div><dt>Source</dt><dd>{item.source ?? 'Unavailable'}</dd></div>
          <div><dt>Currentness basis</dt><dd><Code code={item.basis} /></dd></div>
          <div><dt>{item.delivery_mode === 'PUBLICATION_BASED' ? 'Observed / published' : 'Observation as of'}</dt><dd><Stamp iso={item.as_of} fallback="Unknown" /></dd></div>
          <div><dt>Received</dt><dd><Stamp iso={item.received_at} fallback="Unknown" /></dd></div>
          <div><dt>Fetched / retrieved</dt><dd><Stamp iso={item.fetched_at} fallback="Unknown" /></dd></div>
          <div><dt>Evaluated</dt><dd><Stamp iso={item.evaluated_at} /></dd></div>
          {item.age_ms != null && <div><dt>Age at evaluation</dt><dd>{Math.round(item.age_ms / 1000)}s</dd></div>}
          <div><dt>Policy</dt><dd>{item.policy} · {item.policy_version}{item.stale_after_ms != null ? ` · ${item.stale_after_ms / 1000}s limit` : ' · cadence not verified'}</dd></div>
          <div><dt>Decision use</dt><dd>{words(USE_TEXT, decision)} · current market: {!expired && item.eligible_for_current_decision ? 'eligible' : 'blocked'} · reference: {!expired && item.eligible_for_reference ? 'eligible' : 'blocked'}</dd></div>
          <div><dt>Reason</dt><dd>{expired ? <Code code="SERVER_POLICY_EXPIRED">Server freshness window expired</Code>
            : item.reason_codes.length ? item.reason_codes.map((code, at) => <span key={code}>{at ? ' · ' : ''}<Code code={code} /></span>) : 'None'}</dd></div>
        </dl>
      </details></li>)}
    </ul>
  </details>;
}
