import { useEffect, useRef, useState, type ReactNode } from "react";
import { ImpBullMark } from "./ImpBullMark";
import { ImpCommandSearch, IMP_COMMAND_SEARCH_INPUT_ID } from "./ImpCommandSearch";
import { ImpExecutionPosture } from "./ImpExecutionPosture";
import { ImpKeyboardShortcuts } from "./ImpKeyboardShortcuts";
import { NavShell } from "../NavShell";
import { isTypingTarget } from "../../lib/isTypingTarget";
import { useFocusTrap } from "../../lib/useFocusTrap";
import type { Mode } from "../mode-session/types";

export const IMP_MAIN_CONTENT_ID = "imp-main-content";
const MOBILE_NAV_MAX_PX = 900;

type Props = {
  mode: Mode;
  onSwitchMode: () => void;
  onToggleAssistant?: () => void;
  children: ReactNode;
  topStack: ReactNode;
};

function mediaQuery(): string {
  return `(max-width: ${MOBILE_NAV_MAX_PX}px)`;
}

export function ImpProductChrome({ mode, onSwitchMode, onToggleAssistant, children, topStack }: Props) {
  const [navOpen, setNavOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [isNarrow, setIsNarrow] = useState(() => window.matchMedia(mediaQuery()).matches);
  const sidebarRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const restoreNavFocusRef = useRef(true);
  const skipTrapRestoreRef = useRef(false);
  const hadMobileNavRef = useRef(false);
  const onToggleAssistantRef = useRef(onToggleAssistant);
  onToggleAssistantRef.current = onToggleAssistant;
  const mobileNavActive = isNarrow && navOpen;

  useFocusTrap(mobileNavActive, sidebarRef, skipTrapRestoreRef);

  useEffect(() => {
    const media = window.matchMedia(mediaQuery());
    const onChange = () => {
      setIsNarrow(media.matches);
      if (!media.matches) setNavOpen(false);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const sidebar = sidebarRef.current;
    const main = mainRef.current;
    if (sidebar) sidebar.toggleAttribute("inert", isNarrow && !navOpen);
    if (main) main.toggleAttribute("inert", mobileNavActive);
    if (mobileNavActive) {
      hadMobileNavRef.current = true;
      return;
    }
    if (hadMobileNavRef.current && restoreNavFocusRef.current) {
      menuButtonRef.current?.focus();
    }
    hadMobileNavRef.current = false;
  }, [isNarrow, navOpen, mobileNavActive]);

  useEffect(() => {
    if (!mobileNavActive) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileNavActive]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (shortcutsOpen) {
          event.preventDefault();
          event.stopImmediatePropagation();
          setShortcutsOpen(false);
          return;
        }
        if (mobileNavActive) {
          event.preventDefault();
          event.stopImmediatePropagation();
          restoreNavFocusRef.current = true;
          setNavOpen(false);
        }
        return;
      }
      if (event.altKey || event.ctrlKey || event.metaKey) {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && !event.altKey) {
          if (isTypingTarget(event.target)) return;
          event.preventDefault();
          document.getElementById(IMP_COMMAND_SEARCH_INPUT_ID)?.focus();
        }
        return;
      }
      if (isTypingTarget(event.target)) return;
      if (event.key === "?") {
        event.preventDefault();
        setShortcutsOpen((open) => !open);
        return;
      }
      if (event.key === "/") {
        event.preventDefault();
        document.getElementById(IMP_COMMAND_SEARCH_INPUT_ID)?.focus();
        return;
      }
      if ((event.key === "a" || event.key === "A") && onToggleAssistantRef.current) {
        event.preventDefault();
        onToggleAssistantRef.current();
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [shortcutsOpen, mobileNavActive]);

  const openNav = () => {
    restoreNavFocusRef.current = true;
    setNavOpen(true);
  };

  const closeNav = (restoreFocus: boolean) => {
    restoreNavFocusRef.current = restoreFocus;
    setNavOpen(false);
  };

  return (
    <div
      className={`imp-product-shell${navOpen ? " imp-sidebar-open" : " imp-sidebar-collapsed"}`}
      data-nav-open={navOpen ? "true" : "false"}
    >
      <a className="imp-skip-link" href={`#${IMP_MAIN_CONTENT_ID}`}>
        Skip to main content
      </a>
      <button
        type="button"
        className="imp-sidebar-backdrop"
        aria-hidden={!mobileNavActive}
        tabIndex={-1}
        onClick={() => closeNav(true)}
      />
      <aside
        ref={sidebarRef}
        id="imp-product-sidebar-nav"
        className="imp-product-sidebar"
        aria-label="Product navigation"
        aria-hidden={isNarrow && !navOpen ? true : undefined}
        role={mobileNavActive ? "dialog" : undefined}
        aria-modal={mobileNavActive ? true : undefined}
        onClick={(event) => {
          if (!isNarrow) return;
          const target = event.target as HTMLElement | null;
          if (target?.closest("a")) closeNav(false);
        }}
      >
        <div className="imp-brand-block">
          <ImpBullMark className="imp-bull-mark" />
          <div className="imp-wordmark">
            <span className="imp-wordmark-title">IMP</span>
            <span className="imp-wordmark-tag">Integrated Market Platform</span>
          </div>
          {isNarrow ? (
            <button type="button" className="imp-sidebar-close" onClick={() => closeNav(true)}>
              Close menu
            </button>
          ) : null}
        </div>
        <NavShell mode={mode} />
        <footer className="imp-sidebar-footer">
          <span className="imp-sidebar-version">Operator UI · current contracts · Ctrl+K · ?</span>
        </footer>
      </aside>
      <div className="imp-product-main" ref={mainRef}>
        <header className="imp-top-bar">
          <button
            type="button"
            ref={menuButtonRef}
            className="imp-nav-toggle"
            aria-expanded={navOpen}
            aria-controls="imp-product-sidebar-nav"
            aria-label={navOpen ? "Close menu" : "Menu"}
            onClick={() => (navOpen ? closeNav(true) : openNav())}
          >
            Menu
          </button>
          <ImpCommandSearch />
          <ImpExecutionPosture mode={mode} />
          <button
            type="button"
            className="imp-shortcuts-toggle"
            aria-expanded={shortcutsOpen}
            aria-controls="imp-shortcuts-dialog"
            aria-label="Keyboard shortcuts"
            title="Keyboard shortcuts (?)"
            onClick={() => setShortcutsOpen((open) => !open)}
          >
            ?
          </button>
          <button type="button" className="imp-switch-mode" onClick={onSwitchMode}>
            Switch mode
          </button>
        </header>
        {topStack}
        {children}
      </div>
      <ImpKeyboardShortcuts open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}
