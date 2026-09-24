import { useEffect, useRef } from "react";
import type { OperatorActionConfirmation } from "../../state/operatorAction";

type Props = {
  confirmation: OperatorActionConfirmation;
  pending: boolean;
  confirmId?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

/** Inline confirmation. Replaces `window.confirm`. Escape cancels. */
export function ActionConfirmation({ confirmation, pending, confirmId, onConfirm, onCancel }: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmRef.current?.focus();
  }, []);

  return (
    <div
      className="operator-action-confirm"
      role="group"
      aria-label={confirmation.title}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !pending) {
          event.preventDefault();
          onCancel();
        }
      }}
    >
      <p className="operator-action-confirm-title">{confirmation.title}</p>
      <dl className="operator-action-confirm-facts">
        {confirmation.facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>
      <div className="operator-action-confirm-buttons">
        <button
          ref={confirmRef}
          id={confirmId}
          type="button"
          className="operator-action-confirm-submit"
          onClick={onConfirm}
          disabled={pending}
          aria-busy={pending || undefined}
        >
          {pending ? "Working…" : confirmation.confirmLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={pending}>
          {confirmation.cancelLabel}
        </button>
      </div>
    </div>
  );
}
