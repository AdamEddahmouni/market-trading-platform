import { useCallback, useEffect, useMemo, useRef, useState, type FunctionComponent, type MutableRefObject } from "react";
import { DockviewReact, themeDark, type DockviewApi, type DockviewReadyEvent, type IDockviewPanelProps } from "dockview-react";
import "dockview-react/dist/styles/dockview.css";
import type { PanelId, PanelLayout, ScreenerQuote, ScreenerRow, ScreenerUniverse } from "../../../api/screener";
import { demandPanels, releasePanels, releasePanelsOnUnload, type PanelDemand } from "../../../api/screenerPanels";
import ChartsPanel from "./ChartsPanel";
import CvdPanel from "./CvdPanel";
import FuturesContextPanel from "./FuturesContextPanel";
import Level2Panel from "./Level2Panel";
import OptionsPanel from "./OptionsPanel";
import OrderFlowPanel from "./OrderFlowPanel";
import { LIVE_PANELS, PANEL_TITLES, PANELS } from "./registry";
import { PanelErrorBoundary, PanelFrame, PanelMessage, SpecialistContext, useSelection, type PanelActions, type SpecialistSelection } from "./shared";
import "./dock.css";

/** Arrowing past rows must not open provider subscriptions for each row. */
export const PANEL_SETTLE_MS = 250;
const HEARTBEAT_MS = 15_000;
const ORDER = PANELS.map((panel) => panel.id);

function contained(id: PanelId, Panel: FunctionComponent<IDockviewPanelProps>) {
  const Wrapped = (props: IDockviewPanelProps) => {
    const { supportedPanels } = useSelection();
    return <PanelErrorBoundary id={id}>{supportedPanels.has(id) ? <Panel {...props} /> :
      <PanelFrame id={id} state="UNAVAILABLE"><PanelMessage>{PANEL_TITLES[id]} is unavailable for this universe. The layout is retained.</PanelMessage></PanelFrame>}</PanelErrorBoundary>;
  };
  Wrapped.displayName = `Contained(${id})`;
  return Wrapped;
}
const COMPONENTS: Record<PanelId, FunctionComponent<IDockviewPanelProps>> = {
  order_flow: contained("order_flow", OrderFlowPanel), cvd: contained("cvd", CvdPanel), level2: contained("level2", Level2Panel),
  charts: contained("charts", ChartsPanel), futures: contained("futures", FuturesContextPanel),
  options: contained("options", OptionsPanel),
};

export type DockHandle = { openOrFocus: (id: PanelId) => void; reset: () => void };
type Props = {
  /** Read once when the dock mounts. */
  layout: PanelLayout;
  row: ScreenerRow | null;
  quote: ScreenerQuote | undefined;
  universe?: ScreenerUniverse;
  supportedPanels?: ReadonlySet<PanelId>;
  clientId: string;
  /** A launcher request made before the lazy dock had loaded. */
  pending: PanelId | null;
  handleRef: MutableRefObject<DockHandle | null>;
  /** Called only when the set of open panels changes. */
  onOpenChange: (open: PanelId[]) => void;
  /** Called on every arrangement change; the parent persists it without re-rendering the table. */
  onLayout: (layout: Pick<PanelLayout, "open_panels" | "active_panel" | "dockview_layout">) => void;
};

const ordered = (ids: Iterable<string>) => ORDER.filter((id) => [...ids].includes(id));
const maxColumns = (width: number) => width >= 1700 ? 5 : width >= 1300 ? 4 : width >= 900 ? 3 : 2;

/** Presentation fields only: a panel entry never carries params or nested data. */
export function serializeLayout(api: DockviewApi): Record<string, unknown> | null {
  if (!api.panels.length) return null;
  const json = api.toJSON() as unknown as { panels: Record<string, Record<string, unknown>> } & Record<string, unknown>;
  const panels = Object.fromEntries(Object.entries(json.panels).map(([id, entry]) => [id,
    Object.fromEntries(Object.entries(entry).filter(([key, value]) => key !== "params" && (value === null || ["string", "number", "boolean"].includes(typeof value))))]));
  const { floatingGroups: _floating, popoutGroups: _popout, ...rest } = json;
  return { ...rest, panels };
}

function useSettled(value: string | null, delay: number) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    if (value === null) { setSettled(null); return; }
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

/** Selected instrument + open live panels → one reference-counted demand, with heartbeat and release. */
function usePanelDemand(clientId: string, instrumentId: string | null, livePanels: PanelId[], universe: ScreenerUniverse) {
  const [demand, setDemand] = useState<PanelDemand | null>(null);
  const held = useRef(false);
  const key = `${universe}|${instrumentId ?? ""}|${livePanels.join(",")}`;
  useEffect(() => {
    if (!livePanels.length && !held.current) { setDemand(null); return; }
    let cancelled = false;
    // No live panel (e.g. a universe without the capability) releases by
    // demanding nothing; a stale instrument would be refused and leak holds.
    const target = livePanels.length ? instrumentId : null;
    const send = () => {
      held.current = livePanels.length > 0 && target !== null;
      void (universe === "US_EQUITIES" ? demandPanels(clientId, target, livePanels) : demandPanels(clientId, target, livePanels, universe))
        .then((result) => { if (!cancelled) setDemand(result.instrument_id === target ? result : null); })
        .catch(() => { if (!cancelled) setDemand(null); });
    };
    send();
    // A heartbeat keeps the backend's client lease alive; nothing held needs none.
    const timer = target !== null ? window.setInterval(send, HEARTBEAT_MS) : undefined;
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [key]);
  useEffect(() => {
    const release = () => releasePanelsOnUnload(clientId);
    window.addEventListener("pagehide", release);
    return () => {
      window.removeEventListener("pagehide", release);
      if (held.current) void releasePanels(clientId).catch(() => undefined);
    };
  }, [clientId]);
  return demand;
}

export default function ScreenerDock({ layout, row, quote, universe = "US_EQUITIES", supportedPanels = new Set<PanelId>(["order_flow", "cvd", "level2", "charts", "futures", "options"]), clientId, pending, handleRef, onOpenChange, onLayout }: Props) {
  const apiRef = useRef<DockviewApi | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState<PanelId[]>([]);
  const callbacks = useRef({ onOpenChange, onLayout });
  callbacks.current = { onOpenChange, onLayout };
  const settledId = useSettled(row?.instrument.instrument_id ?? null, PANEL_SETTLE_MS);
  const livePanels = useMemo(() => open.filter((id) => LIVE_PANELS.has(id) && supportedPanels.has(id)), [open, supportedPanels]);
  const demand = usePanelDemand(clientId, settledId, livePanels, universe);

  const focusPanel = useCallback((id: PanelId) => {
    window.requestAnimationFrame(() => document.getElementById(`screener-panel-${id}`)?.focus());
  }, []);
  const addPanel = useCallback((api: DockviewApi, id: PanelId) => {
    const width = hostRef.current?.clientWidth ?? 1200;
    const reference = api.activeGroup ?? api.groups[api.groups.length - 1];
    const base = { id, component: id, title: PANEL_TITLES[id] };
    if (!reference) api.addPanel(base);
    else api.addPanel({ ...base, position: { referenceGroup: reference, direction: api.groups.length < maxColumns(width) ? "right" : "within" } });
  }, []);
  const arrange = useCallback((api: DockviewApi, ids: PanelId[]) => {
    api.clear();
    const width = hostRef.current?.clientWidth ?? 1200;
    for (const id of ordered(ids)) {
      const last = api.groups[api.groups.length - 1];
      const base = { id, component: id, title: PANEL_TITLES[id], inactive: true };
      if (!last) api.addPanel(base);
      else api.addPanel({ ...base, position: { referenceGroup: last, direction: api.groups.length < maxColumns(width) ? "right" : "within" } });
    }
  }, []);
  const openOrFocus = useCallback((id: PanelId) => {
    const api = apiRef.current;
    if (!api) return;
    const existing = api.getPanel(id);
    if (existing) existing.api.setActive(); else addPanel(api, id);
    focusPanel(id);
  }, [addPanel, focusPanel]);
  const reset = useCallback(() => {
    const api = apiRef.current;
    if (!api) return;
    const active = api.activePanel?.id as PanelId | undefined;
    arrange(api, ordered(api.panels.map((panel) => panel.id)));
    if (active) api.getPanel(active)?.api.setActive();
  }, [arrange]);
  useEffect(() => {
    handleRef.current = { openOrFocus, reset };
    return () => { handleRef.current = null; };
  }, [handleRef, openOrFocus, reset]);

  const onReady = useCallback((event: DockviewReadyEvent) => {
    const api = event.api;
    apiRef.current = api;
    const emit = () => {
      const ids = ordered(api.panels.map((panel) => panel.id));
      setOpen((current) => current.join() === ids.join() ? current : ids);
      callbacks.current.onOpenChange(ids);
    };
    const persist = () => callbacks.current.onLayout({ open_panels: ordered(api.panels.map((panel) => panel.id)),
      active_panel: (api.activePanel?.id as PanelId | undefined) ?? null, dockview_layout: serializeLayout(api) });
    api.onDidAddPanel(emit);
    api.onDidRemovePanel(() => { emit(); persist(); });
    api.onDidLayoutChange(persist);
    api.onDidActivePanelChange(persist);
    // Restore: the saved arrangement when it names exactly the open panels, else a default arrangement.
    const saved = layout.dockview_layout as { panels?: Record<string, unknown> } | null;
    let restored = false;
    if (saved && saved.panels && ordered(Object.keys(saved.panels)).join() === ordered(layout.open_panels).join()) {
      try { api.fromJSON(saved as never); restored = api.panels.length === layout.open_panels.length; } catch { restored = false; }
    }
    if (!restored) arrange(api, layout.open_panels);
    if (layout.active_panel) api.getPanel(layout.active_panel)?.api.setActive();
    if (pending) openOrFocus(pending);
    emit();
    persist();
  }, []);

  const actions = useMemo<PanelActions>(() => ({
    close: (id) => apiRef.current?.getPanel(id)?.api.close(),
    move: (id, direction) => {
      const api = apiRef.current;
      const panel = api?.getPanel(id);
      if (!api || !panel) return;
      if (direction === "split") {
        if (panel.group.panels.length > 1) panel.api.moveTo({ group: panel.group, position: "right" });
      } else {
        const target = api.adjacentGroupInDirection(panel.group, direction);
        if (target) panel.api.moveTo({ group: target as never, position: "center" });
      }
      focusPanel(id);
    },
    resize: (id, delta) => {
      const group = apiRef.current?.getPanel(id)?.group;
      if (group) group.api.setSize({ width: Math.max(160, group.api.width + delta) });
    },
  }), [focusPanel]);
  const selection = useMemo<SpecialistSelection>(() => ({ row, universe, supportedPanels, settledId, quote, demand, actions }), [row, universe, supportedPanels, settledId, quote, demand, actions]);

  return <SpecialistContext.Provider value={selection}>
    <div className="screener-dock-host" ref={hostRef}>
      <DockviewReact components={COMPONENTS} onReady={onReady} theme={themeDark} disableFloatingGroups
        className="screener-dockview" />
    </div>
  </SpecialistContext.Provider>;
}
