import type { LifecycleDecision, LifecycleEvidence, TradeLifecycle } from "../../../api/screenerLifecycle";
import {
  ENTRY_LABEL, EXIT_LABEL, ORIGIN_LABEL, PAPER_CLOSE_LABEL, QUALITY_LABEL, RISK_LABEL, UNAVAILABLE, actionLabel, ageText, clock, codeText,
  conditionText, freshnessText, marketDataLabel, money, quotePrice, signedMoney, stamp, stopPrice,
} from "./lifecyclePresentation";

type Group = NonNullable<LifecycleEvidence["supporting"]>;

function EvidenceList({ title, group, empty }: { title: string; group: Group | undefined; empty: string }) {
  return <section aria-label={title}>
    <h5>{title}</h5>
    {!group?.items.length ? <p className="lifecycle-empty">{empty}</p> : <ul className="lifecycle-evidence">
      {group.items.map((item, index) => <li key={item.evidence_id ?? index}>
        {item.lineage ? <span>Evidence reference unavailable ({item.lineage.replace(/_/g, " ")})</span> : <>
          <strong>{item.capability?.replace(/_/g, " ") ?? UNAVAILABLE}</strong> · {item.fact ?? "No fact recorded"}
          <span className="lifecycle-evidence-meta"> — {item.source ?? "Source unavailable"} · {stamp(item.as_of)} · {freshnessText(item)}</span>
        </>}
        <details><summary>Details</summary><p>Evidence {item.evidence_id ?? UNAVAILABLE} · {item.decision_admissibility ?? UNAVAILABLE}{item.weak_reasons?.length ? ` · weak: ${item.weak_reasons.join(", ")}` : ""}</p></details>
      </li>)}
    </ul>}
    {Boolean(group?.truncated) && <p className="lifecycle-empty">{group!.truncated} more not shown.</p>}
  </section>;
}

/** Supporting, conflicting and missing evidence are separate, equally visible sections. */
export function EvidenceSections({ evidence }: { evidence: LifecycleEvidence }) {
  return <>
    <EvidenceList title="Supporting" group={evidence.supporting} empty="None cited." />
    <section aria-label="Conflicting">
      <h5>Conflicting</h5>
      {!evidence.conflicting?.items.length && !evidence.conflicting_alignments?.length && <p className="lifecycle-empty">None recorded.</p>}
      {Boolean(evidence.conflicting?.items.length) && <ul className="lifecycle-evidence">{evidence.conflicting!.items.map((item, index) => <li key={item.evidence_id ?? index}>
        <strong>{item.capability?.replace(/_/g, " ") ?? UNAVAILABLE}</strong> · {item.fact ?? "No fact recorded"}
        <span className="lifecycle-evidence-meta"> — {item.source ?? "Source unavailable"} · {stamp(item.as_of)} · {freshnessText(item)}</span>
        <details><summary>Details</summary><p>Evidence {item.evidence_id ?? UNAVAILABLE}</p></details>
      </li>)}</ul>}
      {evidence.conflicting_alignments?.map((item) => <p key={item.alignment_id ?? item.kind}>
        Evidence alignment {item.result}: {item.kind?.replace(/_/g, " ").toLowerCase()} · observed direction {item.observed_direction ?? "unknown"}{item.limitations.length ? ` · ${item.limitations.join(" ")}` : ""}
      </p>)}
    </section>
    <EvidenceList title="Weak" group={evidence.weak} empty="None recorded." />
    <section aria-label="Missing or unavailable">
      <h5>Missing / unavailable — what IMP does not know</h5>
      {!evidence.missing?.length && !evidence.blocked?.length && <p className="lifecycle-empty">None recorded.</p>}
      {Boolean(evidence.missing?.length) && <p>Missing: {evidence.missing!.map((item) => item.replace(/_/g, " ")).join(", ")}</p>}
      {evidence.blocked?.map((item, index) => <p key={index}>
        Excluded: {item.capability?.replace(/_/g, " ")} · {item.freshness_status ?? "UNAVAILABLE"} · {item.reason_codes.map(codeText).join(", ") || "no reason recorded"} · {item.source ?? "source unavailable"} · {stamp(item.as_of)}
      </p>)}
    </section>
  </>;
}

function Conditions({ title, rows }: { title: string; rows: LifecycleDecision["entry_conditions"] }) {
  if (!rows?.length) return null;
  return <table className="lifecycle-conditions"><caption>{title}</caption><tbody>
    {rows.map((row) => <tr key={row.condition_id}><th scope="row">{conditionText(row.condition_id)}</th><td>{row.status === "MET" ? "Met" : "Not met"}</td>
      <td>{row.source === "SERVER_RISK_CONTROL" ? "Deterministic risk control" : "Server action policy"}</td></tr>)}
  </tbody></table>;
}

/** One decision exactly as it was recorded, with the evidence it froze. */
export function DecisionBlock({ decision, heading }: { decision: LifecycleDecision; heading?: string }) {
  const deterministic = decision.origin === "DETERMINISTIC_RISK_CONTROL";
  return <div className="lifecycle-decision" data-testid={`lifecycle-decision-${decision.decision_id}`}>
    {heading && <h5>{heading}</h5>}
    <p><strong>{actionLabel(decision.action_state)}</strong> · {stamp(decision.decision_time)} · evidence cutoff {clock(decision.decision_cutoff)} · valid until {clock(decision.valid_until)}</p>
    <p>Decided by: {ORIGIN_LABEL[decision.origin]} · {deterministic ? "Model: none" : decision.model?.called
      ? `AI proposal: ${decision.ai_proposal_state ? actionLabel(decision.ai_proposal_state) : UNAVAILABLE} → server decision: ${actionLabel(decision.action_state)} · model ${decision.model.provider_id ?? UNAVAILABLE} / ${decision.model.model_id ?? UNAVAILABLE}`
      : "Model: not called"}</p>
    {decision.action_state === "REVALIDATION_REQUIRED" && <p role="status">Decision needs fresh evidence.</p>}
    <p>{decision.rationale ?? "No rationale recorded."}</p>
    {decision.direction && <p>Direction: {decision.direction}</p>}
    {decision.reference_price && <p>Decision reference (quote, not a fill): {quotePrice(decision.reference_price)} · as of {clock(decision.reference_as_of)}</p>}
    {decision.risk_exit && <p>EXIT reason: SMA trailing stop breached · stop {stopPrice(decision.risk_exit.active_stop)} · observed {stopPrice(decision.risk_exit.trigger_price)} at {stamp(decision.risk_exit.triggered_at)}</p>}
    {decision.blocker_codes.length > 0 && <div className="lifecycle-blockers" role="status"><strong>Blockers</strong>
      <ul>{decision.blocker_codes.map((code) => <li key={code}>{codeText(code)} <code>{code}</code></li>)}</ul></div>}
    <Conditions title="Entry conditions" rows={decision.entry_conditions} />
    <Conditions title="Hold conditions" rows={decision.hold_conditions} />
    <Conditions title="Exit conditions" rows={decision.exit_conditions} />
    {decision.evidence && <details><summary>Evidence frozen with this decision</summary><EvidenceSections evidence={decision.evidence} /></details>}
    <details><summary>Details</summary><p>Decision {decision.decision_id} · snapshot {decision.evidence_snapshot_id ?? UNAVAILABLE} · trace {decision.decision_trace_id ?? UNAVAILABLE} · run {decision.candidate_run_id ?? UNAVAILABLE} · Opportunity {decision.opportunity_id ?? "none"} · readiness {decision.execution_readiness}</p></details>
  </div>;
}

function Signed({ minor, currency, testId }: { minor: number | null; currency: string; testId: string }) {
  const value = signedMoney(minor, currency);
  return <span data-testid={testId} className={`lifecycle-signed lifecycle-signed-${value.direction}`} aria-label={value.label}>{value.text}</span>;
}

/** Entry, position, risk, exit and P&L in text. Shared by the summary card and the expanded view. */
export function LifecycleFacts({ lifecycle }: { lifecycle: TradeLifecycle }) {
  const { entry, exit, position, pnl, risk_control: risk, currency } = lifecycle;
  const mark = position.mark;
  const open = position.state === "LONG" || position.state === "SHORT";
  return <dl className="lifecycle-facts">
    <div data-testid="lifecycle-entry"><dt>Entry</dt><dd>
      {ENTRY_LABEL[entry.status]}
      {entry.fill ? <> · Position opened {stamp(entry.fill.time)} · simulated Paper fill {money(entry.fill.price_minor, currency)}{entry.fill_count > 1 ? ` · ${entry.fill_count} entry fills, average ${money(entry.average_price_minor, currency)}` : ""}</>
        : <> · Paper: {entry.paper === "SUBMITTED_NOT_FILLED" ? "order submitted, no fill" : "no fill"}</>}
      {entry.decision_reference && <> · Decision reference {quotePrice(entry.decision_reference.price)} at {clock(entry.decision_reference.decision_time)} (quote, not a fill)</>}
    </dd></div>
    <div data-testid="lifecycle-position"><dt>Position</dt><dd>
      {position.state === "UNAVAILABLE" ? "Unavailable — position snapshot not readable" : open
        ? <>{position.state} {position.quantity} · average entry {money(position.average_entry_minor ?? null, currency)}</>
        : position.closed ? "FLAT — episode closed" : "FLAT"}
    </dd></div>
    {open && <div data-testid="lifecycle-mark"><dt>Current mark</dt><dd>
      {mark?.price_minor == null ? "Unavailable — no mark for this position" : <>{money(mark.price_minor, currency)} · {mark.quality} · {mark.source ?? "source unavailable"} · {ageText(mark.age_ms)}</>}
    </dd></div>}
    {open && <div data-testid="lifecycle-unrealized"><dt>Unrealized P&amp;L</dt><dd>
      <Signed minor={pnl.unrealized_minor} currency={currency} testId="lifecycle-unrealized-value" /> · {QUALITY_LABEL[pnl.quality]}
    </dd></div>}
    {lifecycle.kind === "POSITION_EPISODE" && <div data-testid="lifecycle-realized"><dt>Realized P&amp;L</dt><dd>
      <Signed minor={pnl.realized_minor} currency={currency} testId="lifecycle-realized-value" /> · simulated Paper, this episode only, net of {money(pnl.costs_minor, currency)} costs
    </dd></div>}
    <div data-testid="lifecycle-risk"><dt>Risk control</dt><dd>
      SMA trailing stop · {RISK_LABEL[risk.status]}
      {risk.stop?.active_stop != null && <> · active stop {stopPrice(risk.stop.active_stop)}</>}
      {risk.stop?.sma_value != null && <> · SMA {stopPrice(risk.stop.sma_value)}</>}
      {risk.stop?.distance_to_stop != null && <> · distance {stopPrice(risk.stop.distance_to_stop)}</>}
      {risk.status === "STALE" && <> · last legitimate level retained, not current</>}
      {risk.status === "BREACHED" && <> · observed {stopPrice(risk.stop?.trigger_price)} at {stamp(risk.stop?.triggered_at)} · EXIT decision generated</>}
      {" "}· Deterministic risk control · Model: none
    </dd></div>
    <div data-testid="lifecycle-exit"><dt>Exit</dt><dd>
      {EXIT_LABEL[exit.status]}
      {exit.fill && <> · Position closed {stamp(exit.fill.time)} · simulated close fill {money(exit.fill.price_minor, currency)}</>}
      {lifecycle.kind === "POSITION_EPISODE" && !exit.fill && <> · Paper close: {PAPER_CLOSE_LABEL[exit.paper_close]}</>}
      {exit.status === "PARTIALLY_CLOSED" && <> · {exit.closed_quantity} closed at average {money(exit.average_price_minor, currency)}</>}
      {exit.decision_reference && <> · Exit decision reference {quotePrice(exit.decision_reference.price)} at {clock(exit.decision_reference.decision_time)} (quote, not a fill)</>}
    </dd></div>
  </dl>;
}

export default function LifecycleDetail({ lifecycle }: { lifecycle: TradeLifecycle }) {
  const { candidate, decision, risk_control: risk, experiment, reevaluation, currency } = lifecycle;
  const history = (lifecycle.decisions ?? []).filter((item) => item.decision_id !== decision?.decision_id);
  const byId = new Map((lifecycle.decisions ?? []).map((item) => [item.decision_id, item] as const));
  return <div className="lifecycle-detail" data-testid="lifecycle-detail">
    <section aria-label="Why selected">
      <h4>Why selected</h4>
      {candidate ? <>
        <p>{candidate.rationale ?? "No rationale recorded."}</p>
        <p className="lifecycle-meta">Rank #{candidate.rank ?? "—"} · selected {stamp(candidate.selected_at)} · evidence cutoff {clock(candidate.decision_cutoff)}
          {candidate.selected_in_current_run ? " · current AI Screener run" : " · earlier AI Screener run"}
          {candidate.lineage === "DECISION_SNAPSHOT" && " · rebuilt from the entry decision's frozen snapshot"}</p>
        {candidate.uncertainties.length > 0 && <p>Uncertainties: {candidate.uncertainties.join("; ")}</p>}
        <EvidenceSections evidence={candidate.evidence} />
        <details><summary>Details</summary><p>Run {candidate.run_id ?? UNAVAILABLE} · {candidate.provider_id ?? UNAVAILABLE} / {candidate.model_id ?? UNAVAILABLE} · prompt {candidate.prompt_id ?? UNAVAILABLE} v{candidate.prompt_version ?? "—"}{candidate.simulated ? " · SOFTWARE_CONTROLLED fixture" : ""}</p></details>
      </> : <p role="status">LINEAGE UNAVAILABLE — this Paper activity has no recorded AI candidate or decision. It is not presented as AI-selected.</p>}
    </section>
    <section aria-label="Decision">
      <h4>Decision</h4>
      {decision ? <DecisionBlock decision={byId.get(decision.decision_id) ?? decision} /> : <p className="lifecycle-empty">No action decision has been recorded for this {lifecycle.kind === "CANDIDATE" ? "candidate" : "episode"}.</p>}
    </section>
    <section aria-label="Entry, position, risk and exit">
      <h4>Entry · Position · Risk · Exit · Result</h4>
      <LifecycleFacts lifecycle={lifecycle} />
      {risk.policy && <p className="lifecycle-meta">Stop policy: {risk.policy.sma_window_bars}-bar SMA on {risk.policy.bar_interval} bars · previous stop {stopPrice(risk.stop?.previous_stop)} · last update {stamp(risk.stop?.last_updated_at)}</p>}
      {(lifecycle.entry.fills?.length ?? 0) + (lifecycle.exit.fills?.length ?? 0) > 1 && <table className="lifecycle-conditions"><caption>Simulated Paper fills</caption><tbody>
        {[...(lifecycle.entry.fills ?? []), ...(lifecycle.exit.fills ?? [])].map((fill) => <tr key={fill.fill_id}><th scope="row">{fill.position_effect}</th>
          <td>{fill.side} {fill.quantity} @ {money(fill.price_minor, currency)}</td><td>{stamp(fill.time)}</td></tr>)}
      </tbody></table>}
    </section>
    {experiment && <section aria-label="Paper experiment" data-testid="lifecycle-experiment">
      <h4>Paper experiment · SIMULATED</h4>
      <p>Account equity {money(experiment.equity_minor, currency)} · cash {money(experiment.cash_minor, currency)} · execution {experiment.execution.replace(/_/g, " ")} · market data {marketDataLabel(experiment.market_data)}. Simulated capital — not live capital.</p>
    </section>}
    {reevaluation && lifecycle.kind === "POSITION_EPISODE" && lifecycle.stage !== "POSITION_CLOSED" && <section aria-label="Reevaluation">
      <h4>Reevaluation</h4>
      <p>{reevaluation.worker_label ?? reevaluation.worker_state ?? UNAVAILABLE} · requested {reevaluation.requested_cadence_seconds ?? "—"}s · effective {reevaluation.effective_cadence_seconds ?? "—"}s · last {clock(reevaluation.last_completed)}</p>
    </section>}
    <section aria-label="Lifecycle history">
      <h4>What happened</h4>
      {Boolean(lifecycle.timeline_truncated) && <p className="lifecycle-empty">{lifecycle.timeline_truncated} earlier events not shown.</p>}
      <ol className="lifecycle-timeline" data-testid="lifecycle-timeline">
        {(lifecycle.timeline ?? []).map((row, index) => {
          const recorded = row.kind === "DECISION" && row.ref.id ? byId.get(row.ref.id) : undefined;
          return <li key={`${row.kind}-${row.ref.id}-${index}`}>
            <time dateTime={row.at ?? undefined}>{stamp(row.at)}</time> <strong>{row.event}</strong> <span className="lifecycle-evidence-meta">· {row.source}</span>
            {row.reason && <p>{row.reason}</p>}
            {Boolean(row.reason_codes?.length) && row.kind === "DECISION" && <p>Reason: {row.reason_codes!.map(codeText).join("; ")}</p>}
            {recorded && <details><summary>Decision as recorded at {clock(recorded.decision_time)}</summary><DecisionBlock decision={recorded} /></details>}
            <details><summary>Details</summary><p>{row.ref.type.replace(/_/g, " ").toLowerCase()} {row.ref.id ?? UNAVAILABLE}</p></details>
          </li>;
        })}
      </ol>
      {history.length === 0 && (lifecycle.timeline ?? []).length === 0 && <p className="lifecycle-empty">No state changes recorded.</p>}
    </section>
    {Boolean(lifecycle.prior_episodes?.length) && <section aria-label="Other episodes of this instrument">
      <h4>Other episodes · {lifecycle.symbol}</h4>
      <ul>{lifecycle.prior_episodes!.map((item) => <li key={item.lifecycle_id}>
        {item.open ? "Open" : "Closed"} · opened {stamp(item.opened_at)}{item.closed_at ? ` · closed ${stamp(item.closed_at)}` : ""} · realized {signedMoney(item.realized_pnl_minor, currency).text}{item.ai_selected ? "" : " · unlinked Paper activity"}
      </li>)}</ul>
      <p className="lifecycle-meta">Each episode keeps its own entry, stop, P&amp;L and history. Nothing above is carried over from these.</p>
    </section>}
    {lifecycle.limitations.length > 0 && <p role="status">Limitations: {lifecycle.limitations.map(codeText).join("; ")}</p>}
    <details><summary>Lineage details</summary>
      <p>Lifecycle {lifecycle.lifecycle_id} · account {lifecycle.lineage.account_id} · experiment {lifecycle.lineage.experiment_id ?? "none"} · origin run {lifecycle.lineage.origin_run_id ?? "LINEAGE UNAVAILABLE"} · opening fill {lifecycle.lineage.opening_fill_id ?? "none"} · opening decision {lifecycle.lineage.opening_decision_id ?? "none"} · projection as of {stamp(lifecycle.as_of)}</p>
    </details>
  </div>;
}
