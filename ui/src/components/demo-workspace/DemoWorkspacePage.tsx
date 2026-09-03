import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import {
  WorkspaceObservability,
  type WorkspaceObservabilityProps,
  useWorkspaceContext,
} from "../workspace-shared/WorkspaceObservability";

type Props = WorkspaceObservabilityProps;

export function DemoWorkspacePage(props: Props) {
  const { instrumentId } = props;
  const { dataLabel, healthState, evidence } = useWorkspaceContext(instrumentId);

  return (
    <section className="page workspace-page demo-workspace-page">
      <header className="demo-workspace-header">
        <div>
          <span className="demo-eyebrow">Demo · Historical research</span>
          <h1>{instrumentId}</h1>
          <p className="workspace-health-line">
            {dataLabel} · {healthState}
            {evidence?.evidence_mix_summary && evidence.evidence_mix_summary !== "UNKNOWN"
              ? ` · ${evidence.evidence_mix_summary.replace(/_/g, " ")} evidence`
              : ""}
          </p>
          <p>
            Inspect lane evidence and replay context without execution authority. Order controls are
            unavailable in Demo.
          </p>
        </div>
        <span className="demo-state-badge">Observational workspace</span>
      </header>

      <WorkspaceModuleNav instrumentId={instrumentId} active="overview" />

      <aside className="panel mode-restriction-note" role="note">
        <strong>Demo is exploration only.</strong>
        <p>Order and paper-session controls are unavailable. Switch to Paper mode to simulate orders.</p>
      </aside>

      <WorkspaceObservability {...props} />
    </section>
  );
}
