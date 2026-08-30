import { useEffect, useRef, type RefObject } from "react";

type Props = {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  triggerRef: RefObject<HTMLButtonElement>;
};

export function LiveModeConfirmation({ open, onCancel, onConfirm, triggerRef }: Props) {
  const goBackRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(true);

  useEffect(() => {
    if (!open) return;
    restoreFocus.current = true;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    goBackRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      if (restoreFocus.current) triggerRef.current?.focus();
    };
  }, [open, triggerRef]);

  if (!open) return null;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;

    const first = goBackRef.current;
    const last = confirmRef.current;
    if (!first || !last) return;

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="mode-dialog-backdrop">
      <div
        className="mode-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="live-mode-dialog-title"
        aria-describedby="live-mode-dialog-description"
        onKeyDown={handleKeyDown}
      >
        <p className="mode-session-eyebrow">Live data boundary</p>
        <h2 id="live-mode-dialog-title">Enter the live-data environment?</h2>
        <p id="live-mode-dialog-description">
          Current provider data may be displayed. This does not enable live trading, place
          orders, or grant execution authority.
        </p>
        <div className="mode-authority-summary">
          <p>Data environment: LIVE</p>
          <p>Execution authority: LOCKED</p>
        </div>
        <div className="mode-dialog-actions">
          <button type="button" ref={goBackRef} onClick={onCancel}>
            Go back
          </button>
          <button
            type="button"
            ref={confirmRef}
            onClick={() => {
              restoreFocus.current = false;
              onConfirm();
            }}
          >
            Enter live data
          </button>
        </div>
      </div>
    </div>
  );
}
