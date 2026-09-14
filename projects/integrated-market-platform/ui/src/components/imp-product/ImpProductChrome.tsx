import { useEffect, useState, type ReactNode } from "react";
import { ImpBullMark } from "./ImpBullMark";
import { ImpCommandSearch } from "./ImpCommandSearch";
import { ImpExecutionPosture } from "./ImpExecutionPosture";
import { NavShell } from "../NavShell";
import type { Mode } from "../mode-session/types";

const MOBILE_NAV_MAX_PX = 900;

type Props = {
  mode: Mode;
  onSwitchMode: () => void;
  children: ReactNode;
  topStack: ReactNode;
};

export function ImpProductChrome({ mode, onSwitchMode, children, topStack }: Props) {
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(`(max-width: ${MOBILE_NAV_MAX_PX}px)`);
    const onChange = () => {
      if (!media.matches) setNavOpen(false);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return (
    <div
      className={`imp-product-shell${navOpen ? " imp-sidebar-open" : " imp-sidebar-collapsed"}`}
      data-nav-open={navOpen ? "true" : "false"}
    >
      <button
        type="button"
        className="imp-sidebar-backdrop"
        aria-hidden={!navOpen}
        tabIndex={navOpen ? 0 : -1}
        onClick={() => setNavOpen(false)}
      />
      <aside id="imp-product-sidebar-nav" className="imp-product-sidebar" aria-label="Product navigation">
        <div className="imp-brand-block">
          <ImpBullMark className="imp-bull-mark" />
          <div className="imp-wordmark">
            <span className="imp-wordmark-title">IMP</span>
            <span className="imp-wordmark-tag">Integrated Market Platform</span>
          </div>
        </div>
        <NavShell mode={mode} layout="sidebar" />
        <footer className="imp-sidebar-footer">
          <span className="imp-sidebar-version">UI v1 · board 03 · Ctrl+K search</span>
        </footer>
      </aside>
      <div className="imp-product-main">
        <header className="imp-top-bar">
          <button
            type="button"
            className="imp-nav-toggle"
            aria-expanded={navOpen}
            aria-controls="imp-product-sidebar-nav"
            onClick={() => setNavOpen((open) => !open)}
          >
            Menu
          </button>
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
