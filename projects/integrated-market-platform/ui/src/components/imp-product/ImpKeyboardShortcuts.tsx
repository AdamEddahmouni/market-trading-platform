import { useRef } from "react";
import { useFocusTrap } from "../../lib/useFocusTrap";

export const KEYBOARD_SHORTCUTS = [
  { keys: "Ctrl/Cmd+K", action: "Focus command search" },
  { keys: "/", action: "Focus command search" },
  { keys: "A", action: "Toggle research assistant" },
  { keys: "Esc", action: "Close shortcuts, mobile menu, or drawers" },
  { keys: "?", action: "Toggle this shortcut list" },
] as const;

type Props = {
  open: boolean;
  onClose: () => void;
};

export function ImpKeyboardShortcuts({ open, onClose }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(open, dialogRef);

  if (!open) return null;

  return (
    <div className="imp-shortcuts-layer" onClick={onClose}>
      <div
        ref={dialogRef}
        id="imp-shortcuts-dialog"
        className="imp-shortcuts-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="imp-shortcuts-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="imp-shortcuts-title">Keyboard shortcuts</h2>
            <p className="imp-shortcuts-subtitle">Expert workflow. Standard navigation stays available.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close keyboard shortcuts">
            Close
          </button>
        </header>
        <table className="imp-shortcuts-table">
          <caption className="sr-only">Shipped operator shortcuts</caption>
          <thead>
            <tr>
              <th scope="col">Shortcut</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {KEYBOARD_SHORTCUTS.map((row) => (
              <tr key={row.keys}>
                <th scope="row">
                  <kbd>{row.keys}</kbd>
                </th>
                <td>{row.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
