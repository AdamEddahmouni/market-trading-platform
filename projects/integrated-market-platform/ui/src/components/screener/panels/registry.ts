import type { PanelId, PanelLayout } from "../../../api/screener";

/** Specialist panels, in launcher and default-arrangement order. */
export const PANELS: ReadonlyArray<{ id: PanelId; title: string }> = [
  { id: "order_flow", title: "Order Flow" },
  { id: "cvd", title: "CVD" },
  { id: "level2", title: "Level 2" },
  { id: "charts", title: "Charts" },
  { id: "futures", title: "Futures Context" },
  { id: "options", title: "Options" },
];
export const PANEL_TITLES = Object.fromEntries(PANELS.map((panel) => [panel.id, panel.title])) as Record<PanelId, string>;
/** Panels that hold a live provider subscription while open. */
export const LIVE_PANELS: ReadonlySet<PanelId> = new Set<PanelId>(["order_flow", "cvd", "level2"]);
export const DOCK_HEIGHT_DEFAULT = 300;
export const DOCK_HEIGHT_MIN = 140;
export const DOCK_HEIGHT_MAX = 1200;
export const DEFAULT_PANEL_LAYOUT: PanelLayout = {
  version: 1, open_panels: [], active_panel: null, dock_height: DOCK_HEIGHT_DEFAULT, dockview_layout: null,
};
export const clampDockHeight = (height: number) => Math.round(Math.max(DOCK_HEIGHT_MIN, Math.min(DOCK_HEIGHT_MAX, height)));
