import { Suspense, useEffect, useRef, useState, type KeyboardEvent, type ReactNode, type Ref } from "react";
import type { PanelId } from "../../api/screener";
import type { AiScreenerScope } from "../../api/screenerAi";
import { PanelMessage, reloadableLazy, ScreenerErrorBoundary } from "./panels/shared";

export type RailTab = "preview" | "ai";
const TABS: { id: RailTab; label: string }[] = [{ id: "preview", label: "Preview" }, { id: "ai", label: "AI" }];
/** The last rail tab is a per-viewer convenience; the server-saved preview layout stays {open, width}. */
export const RAIL_TAB_KEY = "imp.screener.railTab";
export function readRailTab(): RailTab {
  try { return window.localStorage.getItem(RAIL_TAB_KEY) === "ai" ? "ai" : "preview"; } catch { return "preview"; }
}
export function writeRailTab(tab: RailTab) {
  try { window.localStorage.setItem(RAIL_TAB_KEY, tab); } catch { /* storage blocked: the tab still switches */ }
}
export const RAIL_AI_PANEL_ID = "screener-rail-panel-ai";

// The AI Screener's controls load on first visit to the AI tab, keeping the Screener's initial bundle within budget.
const AiScreenerWorkspace = reloadableLazy(() => import("./ai/AiScreenerWorkspace"));

type Props = {
  tab: RailTab;
  onTab: (tab: RailTab) => void;
  /** False for a universe without the AI Screener: the rail is the Quick Preview alone, with no tabs. */
  aiSupported: boolean;
  overlay: boolean;
  width: number;
  paneRef?: Ref<HTMLDivElement>;
  onClose: () => void;
  /** The Quick Preview; null while there is nothing to preview (an overlay with no selection). */
  preview: ReactNode;
  screenerScope: AiScreenerScope;
  openInstrument: (instrumentId: string) => void;
  openNews?: (instrumentId: string, identity: Record<string, string>) => void;
  openPanel?: (id: PanelId) => void;
};

/**
 * The Screener's right rail: Quick Preview and, beside it, the AI Screener. The AI tab needs no selected row, and it
 * mounts on first visit and then stays mounted while hidden, so switching tabs keeps a run's progress and any open
 * decision on screen.
 */
export default function RightRail({ tab, onTab, aiSupported, overlay, width, paneRef, onClose, preview, screenerScope, openInstrument, openNews, openPanel }: Props) {
  const active = aiSupported ? tab : "preview";
  const [aiMounted, setAiMounted] = useState(active === "ai");
  useEffect(() => { if (active === "ai") setAiMounted(true); }, [active]);
  const tabRefs = useRef<Partial<Record<RailTab, HTMLButtonElement | null>>>({});
  const onTabKey = (event: KeyboardEvent) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = TABS.findIndex((item) => item.id === active);
    const next = event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length;
    onTab(TABS[next].id); tabRefs.current[TABS[next].id]?.focus();
  };
  const className = `screener-rail${overlay ? " overlay" : ""}${aiSupported ? " with-tabs" : ""}`;
  return <div className={className} ref={paneRef} style={overlay ? undefined : { width }}>
    {aiSupported && <div className="screener-rail-bar">
      <div className="screener-rail-tabs" role="tablist" aria-label="Right rail" onKeyDown={onTabKey}>
        {TABS.map((item) => <button key={item.id} type="button" role="tab" id={`screener-rail-tab-${item.id}`} aria-controls={`screener-rail-panel-${item.id}`}
          aria-selected={active === item.id} tabIndex={active === item.id ? 0 : -1} ref={(node) => { tabRefs.current[item.id] = node; }}
          onClick={() => onTab(item.id)}>{item.label}</button>)}
      </div>
      <button type="button" className="screener-preview-close" onClick={onClose} aria-label="Close right rail">×</button>
    </div>}
    <div className="screener-rail-panel" role={aiSupported ? "tabpanel" : undefined} id="screener-rail-panel-preview"
      aria-labelledby={aiSupported ? "screener-rail-tab-preview" : undefined} hidden={active !== "preview"}>{preview}</div>
    {aiSupported && <div className="screener-rail-panel" role="tabpanel" id={RAIL_AI_PANEL_ID} aria-labelledby="screener-rail-tab-ai"
      hidden={active !== "ai"} tabIndex={-1}
      onKeyDown={(event) => {
        const target = event.target as HTMLElement;
        if (event.key === "Escape" && !["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) { event.stopPropagation(); onClose(); }
      }}>
      {aiMounted && <ScreenerErrorBoundary label="AI Screener">
        <Suspense fallback={<PanelMessage>Loading AI Screener…</PanelMessage>}>
          <AiScreenerWorkspace visible={active === "ai"} screenerScope={screenerScope} openInstrument={openInstrument} openNews={openNews} openPanel={openPanel} />
        </Suspense>
      </ScreenerErrorBoundary>}
    </div>}
  </div>;
}
