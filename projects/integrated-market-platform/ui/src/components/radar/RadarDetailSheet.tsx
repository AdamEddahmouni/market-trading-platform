import { useEffect, useRef, type ReactNode } from "react";
import { useFocusTrap } from "../../lib/useFocusTrap";

type Props = {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
};

/**
 * Mobile detail sheet for the Radar queue (below BP_MD the queue/detail grid
 * collapses and detail opens here instead). Follows the shell's overlay
 * pattern: backdrop, focus trap, Escape to close, body scroll lock, focus
 * restored to the triggering row on close.
 */
export function RadarDetailSheet({ open, onClose, children }: Props) {
  const sheetRef = useRef<HTMLElement>(null);
  useFocusTrap(open, sheetRef);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="imp-radar-sheet-backdrop"
        aria-label="Close opportunity detail"
        tabIndex={-1}
        onClick={onClose}
      />
      <aside
        ref={sheetRef}
        className="imp-radar-detail-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="Opportunity detail"
        data-testid="imp-radar-detail-sheet"
      >
        <div className="imp-radar-detail-sheet-bar">
          <button type="button" className="imp-radar-detail-sheet-close" onClick={onClose}>
            Close detail
          </button>
        </div>
        <div className="imp-radar-detail-sheet-body">{children}</div>
      </aside>
    </>
  );
}
