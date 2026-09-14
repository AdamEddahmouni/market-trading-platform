import type { ReactNode } from "react";
import { ImpBullMark } from "./ImpBullMark";
import { ImpCommandSearch } from "./ImpCommandSearch";
import { ImpExecutionPosture } from "./ImpExecutionPosture";
import { NavShell } from "../NavShell";
import type { Mode } from "../mode-session/types";

type Props = {
  mode: Mode;
  onSwitchMode: () => void;
  children: ReactNode;
  topStack: ReactNode;
};

export function ImpProductChrome({ mode, onSwitchMode, children, topStack }: Props) {
  return (
    <div className="imp-product-shell">
      <aside className="imp-product-sidebar" aria-label="Product navigation">
        <div className="imp-brand-block">
          <ImpBullMark className="imp-bull-mark" />
          <div className="imp-wordmark">
            <span className="imp-wordmark-title">IMP</span>
            <span className="imp-wordmark-tag">Integrated Market Platform</span>
          </div>
        </div>
        <NavShell mode={mode} layout="sidebar" />
        <footer className="imp-sidebar-footer">
          <span className="imp-sidebar-version">UI v1 · board 03</span>
        </footer>
      </aside>
      <div className="imp-product-main">
        <header className="imp-top-bar">
          <ImpCommandSearch />
          <ImpExecutionPosture mode={mode} />
          <button type="button" className="imp-switch-mode" onClick={onSwitchMode}>
            Switch mode
          </button>
        </header>
        {topStack}
        {children}
      </div>
    </div>
  );
}
