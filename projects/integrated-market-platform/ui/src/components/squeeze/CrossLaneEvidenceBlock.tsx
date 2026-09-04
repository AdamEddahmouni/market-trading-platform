import type { WorkspaceSqueezeResponse } from "../../api/client";

type Props = {
  squeeze: WorkspaceSqueezeResponse;
  onExplain?: (ref: string) => void;
};

export function CrossLaneEvidenceBlock({ squeeze, onExplain }: Props) {
  const evidence = squeeze.cross_lane_evidence;
  if (!evidence || evidence.length === 0) {
    return null;
  }

  return (
    <section className="squeeze-cross-lane-block">
      <h3>Cross-lane evidence</h3>
      <p className="squeeze-cross-lane-note">
        Normalized lane signals fused into squeeze causal evaluation. Traceable refs per SHARED P3.
      </p>
      <ul className="cross-lane-evidence-list">
        {evidence.map((item, index) => (
          <li
            key={`${item.lane}-${item.signal}-${index}`}
            className={`cross-lane-evidence-item ${item.available ? "available" : "unavailable"}`}
          >
            <div className="cross-lane-evidence-header">
              <strong>{item.signal}</strong>
              <span className="cross-lane-lane">{item.lane}</span>
            </div>
            <p className="cross-lane-detail">{item.detail}</p>
            <p className="cross-lane-meta">
              Strength: {item.strength}
              {item.provenance_class ? ` · ${item.provenance_class}` : ""}
              {item.quality_flags && item.quality_flags.length > 0
                ? ` · flags: ${item.quality_flags.join(", ")}`
                : ""}
            </p>
            {item.source_ref && onExplain ? (
              <button type="button" onClick={() => onExplain(item.source_ref)}>
                Trace ref
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
