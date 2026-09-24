/**
 * Operator-action presentation model.
 *
 * This describes how an already-authorized domain action is shown and
 * confirmed. It is not an execution API: descriptors carry no command URL,
 * no secret, and no authority the backend did not already expose.
 */

export const OPERATOR_ACTION_AVAILABILITY = [
  "AVAILABLE",
  "BLOCKED",
  "READ_ONLY",
  "UNAVAILABLE",
] as const;

export type OperatorActionAvailability = (typeof OPERATOR_ACTION_AVAILABILITY)[number];

export type OperatorActionConsequence =
  | "none"
  | "local_workstation"
  | "configuration"
  | "operator_record"
  | "navigation";

/** Domain-owned reason. Codes are not a global IMP state enum. */
export type OperatorActionDomainReason = {
  code: string;
  detail?: string;
};

export type OperatorActionConfirmation = {
  title: string;
  /** Operator-relevant facts. Do not put secrets here. */
  facts: ReadonlyArray<{ label: string; value: string }>;
  confirmLabel: string;
  cancelLabel: string;
};

export type OperatorActionTarget = {
  label: string;
  id?: string;
};

export type OperatorActionDescriptor = {
  id: string;
  /** Domain family, e.g. `platform.lifecycle`. Not an endpoint. */
  domain: string;
  title: string;
  description?: string;
  availability: OperatorActionAvailability;
  /** Required for every non-AVAILABLE action. Missing reasons stay explicit. */
  reason?: OperatorActionDomainReason;
  consequence: OperatorActionConsequence;
  /** Present only when the operator must confirm before the mutation. */
  confirmation?: OperatorActionConfirmation;
  target?: OperatorActionTarget;
};

export const OPERATOR_ACTION_RESULT_KIND = [
  "SUCCESS",
  "REQUEST_FAILED",
  "RESULT_UNVERIFIED",
  "REFRESH_FAILED_AFTER_MUTATION",
] as const;

export type OperatorActionResultKind = (typeof OPERATOR_ACTION_RESULT_KIND)[number];

export type OperatorActionResultState = {
  kind: OperatorActionResultKind;
  message: string;
  /** Domain reason when the backend or a re-check rejected the action. */
  reasonCode?: string;
};

export function actionNeedsExplanation(action: OperatorActionDescriptor): boolean {
  return action.availability !== "AVAILABLE";
}

/** Honest sentence when a non-available action has no domain reason. */
export function actionExplanation(action: OperatorActionDescriptor): string {
  if (!actionNeedsExplanation(action)) return "";
  const detail = action.reason?.detail?.trim();
  if (detail) return detail;
  if (action.reason?.code) {
    return `No explanation was reported for ${action.reason.code}.`;
  }
  return "No reason was reported.";
}
