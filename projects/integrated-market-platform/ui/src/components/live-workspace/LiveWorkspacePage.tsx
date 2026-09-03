import { Link } from "react-router-dom";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import {
  WorkspaceObservability,
  type WorkspaceObservabilityProps,
  useWorkspaceContext,
} from "../workspace-shared/WorkspaceObservability";

type Props = WorkspaceObservabilityProps;

export function LiveWorkspacePage(props: Props) {
  const { instrumentId } = props;
  const { dataLabel, healthState, evidence } = useWorkspaceContext(instrumentId);

  return (
    <section className="page workspace-page live-workspace-page">
      <header className="live-workspace-header">
        <div>
          <span className="live-eyebrow">Live · Read-only observational</span>
          <h1>{instrumentId}</h1>
          <p className="workspace-health-line">
            {dataLabel} · {healthState}
            {evidence?.evidence_mix_summary && evidence.evidence_mix_summary !== "UNKNOWN"
              ? ` · ${evidence.evidence_mix_summary.replace(/_/g, " ")} evidence`
              : ""}
          </p>
          <p>
            Monitor broker-observed market context and lane evidence without execution authority.
          </p>
        </div>
        <Link to="/live-canary">Open live canary</Link>
      </header>

      <WorkspaceModuleNav instrumentId={instrumentId} active="overview" />

      <aside className="panel mode-restriction-note" role="note">
        <strong>Live is read-only here.</strong>
        <p>Order and paper-session controls are unavailable. Use the live canary for operational safety review.</p>
      </aside>

      <WorkspaceObservability {...props} />
    </section>
  );
}
