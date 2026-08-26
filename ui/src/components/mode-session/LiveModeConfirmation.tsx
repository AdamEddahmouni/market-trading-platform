import { useEffect, useRef, type RefObject } from "react";

type LiveModeConfirmationProps = {
  onCancel: () => void;
  onConfirm: () => void;
  triggerRef: RefObject<HTMLButtonElement>;
};

export function LiveModeConfirmation({
  onCancel,
  onConfirm,
  triggerRef,
}: LiveModeConfirmationProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    return () => triggerRef.current?.focus();
  }, [triggerRef]);

  return (
    <div className="live-confirmation-backdrop">
      <div
        ref={dialogRef}
        className="live-confirmation"
        role="dialog"
        aria-modal="true"
        aria-labelledby="live-confirmation-title"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onCancel();
            return;
          }
          if (event.key === "Tab") {
            const buttons = Array.from(
              dialogRef.current?.querySelectorAll<HTMLButtonElement>("button") ?? [],
            );
            const first = buttons[0];
            const last = buttons.at(-1);
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <p className="mode-eyebrow">Read-only live data</p>
        <h2 id="live-confirmation-title">Enter the live-data environment?</h2>
        <p>
          Current provider data may be displayed. This does not enable live trading, place orders,
          or grant execution authority.
        </p>
        <div className="live-authority-summary" aria-label="Live authority summary">
          <p>Data environment: LIVE</p>
          <p>Execution authority: LOCKED</p>
        </div>
        <div className="live-confirmation-actions">
          <button ref={cancelRef} type="button" onClick={onCancel}>
            Go back
          </button>
          <button type="button" onClick={onConfirm}>
            Enter live data
          </button>
        </div>
      </div>
    </div>
  );
}
