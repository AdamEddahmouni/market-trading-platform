import type { PaperDecisionSnapshot } from "./buildPaperDecisionSnapshot";
import type { DecisionBullet } from "./paperDecisionSemantics";
import { laneModuleTitle } from "../workspace-module-shared/buildLaneModeContent";
import type { PaperHandoffModel } from "./buildPaperHandoffModel";

type Props = {
  snapshot: PaperDecisionSnapshot;
  handoff?: PaperHandoffModel;
};

function BulletList({ items }: { items: DecisionBullet[] }) {
  if (items.length === 0) return <p className="muted">None</p>;
  return (
    <ul>
      {items.map((item) => (
        <li key={`${item.lane}-${item.text}`} className={item.isOrigin ? "origin-lane-bullet" : undefined}>
          {item.text}
        </li>
      ))}
    </ul>
  );
}

function originLabel(snapshot: PaperDecisionSnapshot, handoff?: PaperHandoffModel): string | null {
  if (handoff?.kind === "attention" && handoff.attentionId) {
    return `Paper Command attention ${handoff.attentionId}`;
  }
  if (snapshot.originLane) return laneModuleTitle(snapshot.originLane);
  if (handoff?.kind === "lane" && handoff.sourceTitle) return handoff.sourceTitle;
  return null;
}

export function PaperDecisionSnapshotPanel({ snapshot, handoff }: Props) {
  if (snapshot.phase === "loading") {
    return (
      <section className="panel paper-cockpit-panel" aria-labelledby="decision-snapshot-heading">
        <h2 id="decision-snapshot-heading">Decision snapshot</h2>
        <p role="status">Loading workspace evidence…</p>
      </section>
    );
  }

  if (snapshot.phase === "error") {
    return (
      <section className="panel paper-cockpit-panel" aria-labelledby="decision-snapshot-heading">
        <h2 id="decision-snapshot-heading">Decision snapshot</h2>
        <p className="paper-cockpit-warning" role="status">
          {snapshot.phaseMessage ?? "Workspace evidence could not be loaded."}
        </p>
      </section>
    );
  }

  return (
    <section className="panel paper-cockpit-panel" aria-labelledby="decision-snapshot-heading">
      <h2 id="decision-snapshot-heading">Decision snapshot</h2>
      {originLabel(snapshot, handoff) ? (
        <p className="paper-cockpit-origin">
          Origin: <strong>{originLabel(snapshot, handoff)}</strong>
        </p>
      ) : (
        <p className="muted">No handoff — review workspace evidence before drafting.</p>
      )}
      {handoff?.kind === "attention" ? (
        <p className="muted paper-cockpit-source-hint">
          Source surfaced attention without a directional recommendation. Supports, contradicts, and gaps below
          reflect current workspace evidence only.
        </p>
      ) : null}
      {handoff?.kind === "lane" && snapshot.contradicts.length > 0 && snapshot.supports.length > 0 ? (
        <p className="muted paper-cockpit-source-hint">
          Current workspace evidence may disagree with the lane handoff context — review both before preview.
        </p>
      ) : null}
      {snapshot.overallInsufficient ? (
        <p className="muted">Evidence is insufficient for a directional conclusion.</p>
      ) : null}
      <div className="decision-snapshot-grid">
        <div>
          <h3>Supports</h3>
          <BulletList items={snapshot.supports} />
        </div>
        <div>
          <h3>Contradicts</h3>
          <BulletList items={snapshot.contradicts} />
        </div>
        <div>
          <h3>Watch / unclear</h3>
          <BulletList items={snapshot.unclear} />
        </div>
        <div>
          <h3>Data gaps</h3>
          <BulletList items={snapshot.dataGaps} />
        </div>
      </div>
    </section>
  );
}
