import { memo } from "react";
import type { PanelId } from "../../../api/screener";
import { PANELS } from "./registry";

type Props = {
  open: readonly PanelId[];
  onLaunch: (id: PanelId) => void;
  onReset: () => void;
  resetDisabled: boolean;
};

/** The single Open Panels row. A closed panel opens; an open panel is focused. */
function PanelLauncherInner({ open, onLaunch, onReset, resetDisabled }: Props) {
  return <nav className="screener-launcher" aria-label="Open panels">
    <span className="screener-launcher-label" aria-hidden="true">Open Panels</span>
    {PANELS.map((panel) => {
      const isOpen = open.includes(panel.id);
      return <button key={panel.id} type="button" className="screener-launcher-button" aria-pressed={isOpen}
        title={isOpen ? `Focus ${panel.title}` : `Open ${panel.title}`} onClick={() => onLaunch(panel.id)}>{panel.title}</button>;
    })}
    <button type="button" className="screener-launcher-reset" onClick={onReset} disabled={resetDisabled}>Reset Panel Layout</button>
  </nav>;
}

export const PanelLauncher = memo(PanelLauncherInner);
