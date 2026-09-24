import { resolveSemanticState, SEMANTIC_TONE_ICON } from "../../state/semanticState";
import { actionExplanation, type OperatorActionDescriptor } from "../../state/operatorAction";

type Props = {
  action: OperatorActionDescriptor;
  id: string;
};

/**
 * Visible explanation for blocked, unavailable, and read-only actions.
 * Tone comes from the shared semantic adapter. The domain reason code stays
 * separate from the availability label.
 */
export function ActionUnavailableReason({ action, id }: Props) {
  if (action.availability === "AVAILABLE") return null;
  const state = resolveSemanticState("action", action.availability);
  const explanation = actionExplanation(action);
  return (
    <p id={id} className="operator-action-reason" data-availability={action.availability} data-tone={state.tone}>
      <span className="operator-action-reason-icon" aria-hidden="true">
        {SEMANTIC_TONE_ICON[state.tone]}
      </span>
      <span className="operator-action-reason-label">{state.label}.</span> {explanation}
      {action.reason?.code ? (
        <span className="operator-action-reason-code">
          {" "}
          Reason code: <code>{action.reason.code}</code>.
        </span>
      ) : null}
    </p>
  );
}
