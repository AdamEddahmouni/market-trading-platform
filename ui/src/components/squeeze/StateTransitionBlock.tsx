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

  return (
    <section className="squeeze-state-machine" aria-label="Ignition state machine">
      <div className="squeeze-state-banner">
        <span className="squeeze-state-label">STATE: {machine.current_state}</span>
        <span className="squeeze-freshness">last Δ {machine.last_transition_label}</span>
      </div>
      <div className="state-transition-grid">
        <div className="state-transition-column">
          <h3>Changed criteria</h3>
          <CriterionList items={machine.changed_criteria ?? []} emptyLabel="No failing criteria in frozen snapshot." />
        </div>
        <div className="state-transition-column">
          <h3>Unchanged criteria</h3>
          <CriterionList items={machine.unchanged_criteria ?? []} emptyLabel="No passing criteria recorded." />
        </div>
        {machine.unknown_criteria && machine.unknown_criteria.length > 0 ? (
          <div className="state-transition-column">
            <h3>Unknown criteria</h3>
            <CriterionList items={machine.unknown_criteria} emptyLabel="None" />
          </div>
        ) : null}
      </div>
    </section>
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
