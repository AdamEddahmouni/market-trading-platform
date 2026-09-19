import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { LAB_UNAVAILABLE, LAB_UNKNOWN, type LabFact } from "./labPresentation";

function isCopyableFact(fact: LabFact): boolean {
  return Boolean(fact.copyable) && fact.value !== LAB_UNKNOWN && fact.value !== LAB_UNAVAILABLE;
}

export function LabFactGrid({ facts }: { facts: LabFact[] }) {
  return (
    <dl className="lab-fact-grid">
      {facts.map((fact) => (
        <div key={fact.label}>
          <dt>{fact.label}</dt>
          <dd>
            {isCopyableFact(fact) ? <CopyableIdentifier value={fact.value} chars={6} /> : fact.value}
            {fact.note ? <p className="lab-muted">{fact.note}</p> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function LabWarningList({ warnings }: { warnings: string[] }) {
  return (
    <ul className="lab-warning-list">
      {warnings.map((warning) => (
        <li key={warning}>{warning}</li>
      ))}
    </ul>
  );
}
