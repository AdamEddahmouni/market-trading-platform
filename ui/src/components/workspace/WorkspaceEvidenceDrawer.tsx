import type { WorkspaceEvidenceLane } from "../../api/schemas";

type Props = {
  lane: WorkspaceEvidenceLane | null;
  onClose: () => void;
  onExplain?: (ref: string) => void;
};

export function WorkspaceEvidenceDrawer({ lane, onClose, onExplain }: Props) {
  if (!lane) return null;
  return (
    <aside className="evidence-drawer" role="dialog" aria-label="Evidence detail">
      <header>
        <h3>{lane.lane.replace(/_/g, " ")}</h3>
        <button type="button" onClick={onClose}>Close</button>
      </header>
      <dl className="metric-list">
        <div>
          <dt>Summary</dt>
          <dd>{lane.summary}</dd>
        </div>
        <div>
          <dt>Relevance</dt>
          <dd>{lane.relevance}</dd>
        </div>
        {lane.direction ? (
          <div>
            <dt>Direction / state</dt>
            <dd>{lane.direction}</dd>
          </div>
        ) : null}
        {lane.confidence ? (
          <div>
            <dt>Confidence</dt>
            <dd>{lane.confidence}</dd>
          </div>
        ) : null}
        <div>
          <dt>Quality</dt>
          <dd>{lane.quality}</dd>
        </div>
        <div>
          <dt>Freshness</dt>
          <dd>{lane.freshness_label}</dd>
        </div>
        {lane.as_of ? (
          <div>
            <dt>As of</dt>
            <dd>{lane.as_of}</dd>
          </div>
        ) : null}
        {lane.sources?.length ? (
          <div>
            <dt>Sources</dt>
            <dd>{lane.sources.join(", ")}</dd>
          </div>
        ) : null}
        {lane.reason_codes?.length ? (
          <div>
            <dt>Reason codes</dt>
            <dd>{lane.reason_codes.join(", ")}</dd>
          </div>
        ) : null}
      </dl>
      {lane.missing_evidence?.length ? (
        <section>
          <h4>Missing / caveats</h4>
          <ul>
            {lane.missing_evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {lane.details && Object.keys(lane.details).length > 0 ? (
        <section>
          <h4>Underlying observations</h4>
          <pre>{JSON.stringify(lane.details, null, 2)}</pre>
        </section>
      ) : null}
      {lane.explain_ref && onExplain ? (
        <button type="button" onClick={() => onExplain(lane.explain_ref!)}>Open explain</button>
      ) : null}
    </aside>
  );
}
