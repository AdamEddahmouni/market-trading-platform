import type { WorkspaceSqueezeResponse } from "../../api/client";

type Criterion = {
  rule_id: string;
  category: string;
  outcome: string;
  reason: string;
};

type Props = {
  squeeze: WorkspaceSqueezeResponse;
};

export function StateTransitionBlock({ squeeze }: Props) {
  const machine = squeeze.state_machine;
  if (!machine) {
    return (
      <div className="squeeze-state-banner">
        <span className="squeeze-state-label">STATE: {squeeze.ignition_state ?? "UNKNOWN"}</span>
        <span className="squeeze-freshness">Freshness: {squeeze.freshness ?? "UNKNOWN"}</span>
      </div>
    );
  }

  const failedThresholds = machine.failed_thresholds ?? machine.changed_criteria ?? [];

  return (
    <section className="squeeze-state-machine" aria-label="Causal squeeze state">
      <div className="squeeze-state-banner">
        <span className="squeeze-state-label">STATE: {machine.current_state}</span>
        <span className="squeeze-freshness">last Δ {machine.last_transition_label}</span>
        {machine.transition_count && machine.transition_count > 1 ? (
          <span className="squeeze-transition-count">
            {machine.transition_count} causal transitions
          </span>
        ) : null}
        {machine.overall_confidence ? (
          <span className="squeeze-confidence">confidence {machine.overall_confidence}</span>
        ) : null}
      </div>
      <div className="state-transition-grid">
        <div className="state-transition-column">
          <h3>Failed thresholds</h3>
          <p className="state-transition-note">
            Phase 3A rule outcomes that did not pass — not the same as a causal state transition.
          </p>
          <CriterionList items={failedThresholds} emptyLabel="No failing thresholds in this snapshot." />
        </div>
        <div className="state-transition-column">
          <h3>Passing thresholds</h3>
          <CriterionList items={machine.unchanged_criteria ?? []} emptyLabel="No passing thresholds recorded." />
        </div>
        {machine.unknown_criteria && machine.unknown_criteria.length > 0 ? (
          <div className="state-transition-column">
            <h3>Unknown thresholds</h3>
            <CriterionList items={machine.unknown_criteria} emptyLabel="None" />
          </div>
        ) : null}
      </div>
      <CausalTransitionLog transitions={machine.state_transitions ?? []} />
      <TransitionLog transitions={machine.transitions ?? []} />
    </section>
  );
}

type TransitionEvent = {
  at_label?: string;
  from_state?: string;
  to_state?: string;
  kind?: string;
  trigger?: string;
  hysteresis_applied?: boolean;
  changed_at?: string;
};

function CausalTransitionLog({ transitions }: { transitions: TransitionEvent[] }) {
  if (!transitions.length) {
    return null;
  }
  return (
    <div className="state-transition-log causal-transition-log">
      <h3>Causal state transitions</h3>
      <ul className="state-transition-event-list">
        {transitions.map((event, index) => (
          <li key={`causal-${event.from_state ?? "from"}-${event.to_state ?? "to"}-${index}`}>
            <span className="transition-states">
              {event.from_state ?? "UNKNOWN"} → {event.to_state ?? "UNKNOWN"}
            </span>
            {event.trigger ? <span className="transition-trigger">{event.trigger}</span> : null}
            {event.changed_at ? <span className="transition-at">at {event.changed_at}</span> : null}
            {event.hysteresis_applied ? (
              <span className="transition-hysteresis">hysteresis applied</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TransitionLog({ transitions }: { transitions: TransitionEvent[] }) {
  if (!transitions.length) {
    return null;
  }
  return (
    <div className="state-transition-log">
      <h3>Snapshot log</h3>
      <ul className="state-transition-event-list">
        {transitions.map((event, index) => (
          <li key={`${event.kind ?? "event"}-${event.from_state ?? "from"}-${event.to_state ?? "to"}-${index}`}>
            <span className="transition-states">
              {event.from_state ?? "UNKNOWN"} → {event.to_state ?? "UNKNOWN"}
            </span>
            {event.at_label ? <span className="transition-at">at {event.at_label}</span> : null}
            {event.trigger ? <span className="transition-trigger">{event.trigger}</span> : null}
            {event.kind ? <span className="transition-kind">{event.kind}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CriterionList({ items, emptyLabel }: { items: Criterion[]; emptyLabel: string }) {
  if (!items.length) {
    return <p className="state-transition-empty">{emptyLabel}</p>;
  }
  return (
    <ul className="state-transition-list">
      {items.map((item) => (
        <li key={item.rule_id}>
          <code>{item.rule_id}</code>
          <span>{item.category}</span>
          <span className={`outcome-${item.outcome.toLowerCase()}`}>{item.outcome}</span>
          {item.reason ? <span className="criterion-reason">{item.reason}</span> : null}
        </li>
      ))}
    </ul>
  );
}
