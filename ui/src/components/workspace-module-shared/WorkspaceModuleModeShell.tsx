import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Mode } from "../mode-session/types";
import {
  WorkspaceModuleNav,
  type WorkspaceModuleId,
} from "../WorkspaceModuleNav";

export type WorkspaceModuleModeShellProps = {
  mode: Mode;
  instrumentId: string;
  active: WorkspaceModuleId;
  pageClassName: string;
  moduleTitle: string;
  description: ReactNode;
  headerExtra?: ReactNode;
  squeezeQuery?: string;
  children: ReactNode;
};

function modePageClass(mode: Mode): string {
  if (mode === "DEMO") return "demo-workspace-module-page";
  if (mode === "PAPER") return "paper-workspace-module-page";
  return "live-workspace-module-page";
}

function DemoModuleHeader({
  instrumentId,
  moduleTitle,
  description,
  headerExtra,
}: Pick<
  WorkspaceModuleModeShellProps,
  "instrumentId" | "moduleTitle" | "description" | "headerExtra"
>) {
  return (
    <header className="demo-workspace-module-header">
      <div>
        <span className="demo-eyebrow">Demo · Historical research</span>
        <h1>
          {instrumentId} — {moduleTitle}
        </h1>
        <p className="workspace-module-description">{description}</p>
        {headerExtra}
      </div>
      <span className="demo-state-badge">Observational module</span>
    </header>
  );
}

function PaperModuleHeader({
  instrumentId,
  moduleTitle,
  description,
  headerExtra,
}: {
  instrumentId: string;
  moduleId: WorkspaceModuleId;
  moduleTitle: string;
  description: ReactNode;
  headerExtra?: ReactNode;
}) {
  return (
    <header className="paper-workspace-module-header">
      <div>
        <span className="paper-eyebrow">Paper · Simulation context</span>
        <h1>
          {instrumentId} — {moduleTitle}
        </h1>
        <p className="workspace-module-description">{description}</p>
        {headerExtra}
      </div>
      <div className="workspace-module-paper-links">
        <Link to={`/workspace/${instrumentId}`}>Open workspace overview</Link>
        <Link to="/portfolio">Open paper portfolio</Link>
      </div>
    </header>
  );
}

function LiveModuleHeader({
  instrumentId,
  moduleTitle,
  description,
  headerExtra,
}: Pick<
  WorkspaceModuleModeShellProps,
  "instrumentId" | "moduleTitle" | "description" | "headerExtra"
>) {
  return (
    <header className="live-workspace-module-header">
      <div>
        <span className="live-eyebrow">Live · Read-only observational</span>
        <h1>
          {instrumentId} — {moduleTitle}
        </h1>
        <p className="workspace-module-description">{description}</p>
        {headerExtra}
      </div>
      <Link to="/live-canary">Open live canary</Link>
    </header>
  );
}

function ModeRestrictionNote({ mode }: { mode: Mode }) {
  if (mode === "DEMO") {
    return (
      <aside className="panel mode-restriction-note" role="note" data-testid="workspace-mode-restriction-note">
        <strong>Demo is exploration only.</strong>
        <p>
          Lane modules are read-only. Switch to Paper mode to route evidence into simulation from the
          workspace overview.
        </p>
      </aside>
    );
  }
  if (mode === "PAPER") {
    return (
      <aside className="panel mode-restriction-note paper-module-note" role="note" data-testid="workspace-mode-restriction-note">
        <strong>Paper simulation context.</strong>
        <p>
          Lane evidence informs paper orders from the workspace overview — use{" "}
          <strong>Draft paper order from lane</strong> to pre-fill the ticket, or open the overview
          directly.
        </p>
      </aside>
    );
  }
  if (mode === "LIVE") {
    return (
      <aside className="panel mode-restriction-note" role="note" data-testid="workspace-mode-restriction-note">
        <strong>Live is read-only here.</strong>
        <p>
          Lane modules show broker-observed context without execution authority. Use the live canary
          for operational safety review.
        </p>
      </aside>
    );
  }
  return null;
}

export function WorkspaceModuleModeShell({
  mode,
  instrumentId,
  active,
  pageClassName,
  moduleTitle,
  description,
  headerExtra,
  squeezeQuery,
  children,
}: WorkspaceModuleModeShellProps) {
  const headerProps = { instrumentId, moduleTitle, description, headerExtra };

  return (
    <section className={`page workspace-module-page ${pageClassName} ${modePageClass(mode)}`}>
      {mode === "DEMO" ? <DemoModuleHeader {...headerProps} /> : null}
      {mode === "PAPER" ? <PaperModuleHeader {...headerProps} moduleId={active} /> : null}
      {mode === "LIVE" ? <LiveModuleHeader {...headerProps} /> : null}

      <WorkspaceModuleNav instrumentId={instrumentId} active={active} squeezeQuery={squeezeQuery} />

      <ModeRestrictionNote mode={mode} />

      {children}
    </section>
  );
}
