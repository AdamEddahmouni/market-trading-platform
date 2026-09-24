import { useEffect, useId, useRef, useState } from "react";
import type { OperatorActionDescriptor, OperatorActionResultState } from "../../state/operatorAction";
import { ActionConfirmation } from "./ActionConfirmation";
import { ActionResult } from "./ActionResult";
import { ActionUnavailableReason } from "./ActionUnavailableReason";

type Props = {
  action: OperatorActionDescriptor;
  pending?: boolean;
  result?: OperatorActionResultState | null;
  /** Fires once per attempt, after confirmation when confirmation is required. */
  onActivate: () => void | Promise<void>;
  confirmId?: string;
  /** Overrides the accessible name when the visible title is shared (e.g. "Refresh"). */
  accessibleName?: string;
};

/**
 * Shared operator-action control. The caller owns the domain mutation.
 * This component only presents availability, confirmation, pending, and result.
 */
export function OperatorActionButton({
  action,
  pending = false,
  result = null,
  onActivate,
  confirmId,
  accessibleName,
}: Props) {
  const reasonId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(false);
  const inFlight = useRef(false);
  const [confirming, setConfirming] = useState(false);
  const unavailable = action.availability !== "AVAILABLE";
  const needsConfirm = Boolean(action.confirmation);

  async function activate() {
    if (pending || inFlight.current || unavailable) return;
    if (needsConfirm && !confirming) {
      setConfirming(true);
      return;
    }
    inFlight.current = true;
    setConfirming(false);
    try {
      await onActivate();
    } finally {
      inFlight.current = false;
    }
  }

  function cancel() {
    restoreFocus.current = true;
    setConfirming(false);
  }

  useEffect(() => {
    if (!confirming && restoreFocus.current) {
      restoreFocus.current = false;
      triggerRef.current?.focus();
    }
  }, [confirming]);

  return (
    <div className="operator-action" data-action-id={action.id} data-availability={action.availability}>
      {confirming && action.confirmation ? (
        <ActionConfirmation
          confirmation={action.confirmation}
          pending={pending}
          confirmId={confirmId}
          onConfirm={activate}
          onCancel={cancel}
        />
      ) : (
        <button
          ref={triggerRef}
          type="button"
          className="operator-action-button"
          onClick={() => void activate()}
          disabled={unavailable || pending}
          aria-disabled={unavailable || pending || undefined}
          aria-busy={pending || undefined}
          aria-describedby={unavailable ? reasonId : undefined}
          aria-label={accessibleName}
        >
          {pending ? "Working…" : action.title}
        </button>
      )}
      {action.description && !confirming ? <p className="operator-action-description">{action.description}</p> : null}
      <ActionUnavailableReason action={action} id={reasonId} />
      {result ? <ActionResult result={result} /> : null}
    </div>
  );
}
