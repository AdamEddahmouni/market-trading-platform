import type { OperatorActionResultState } from "../../state/operatorAction";

type Props = {
  result: OperatorActionResultState;
};

const RESULT_LABEL: Record<OperatorActionResultState["kind"], string> = {
  SUCCESS: "Completed",
  REQUEST_FAILED: "Not completed",
  RESULT_UNVERIFIED: "Accepted, not yet verified",
  REFRESH_FAILED_AFTER_MUTATION: "Accepted, status reload failed",
};

/**
 * Transient result of one action attempt. Authoritative page state still
 * comes from the refetched domain query, not from this message.
 */
export function ActionResult({ result }: Props) {
  const alert = result.kind === "REQUEST_FAILED" || result.kind === "REFRESH_FAILED_AFTER_MUTATION";
  return (
    <p
      className="operator-action-result"
      role={alert ? "alert" : "status"}
      data-result-kind={result.kind}
    >
      <span className="operator-action-result-label">{RESULT_LABEL[result.kind]}.</span> {result.message}
      {result.reasonCode ? (
        <span className="operator-action-reason-code">
          {" "}
          Reason code: <code>{result.reasonCode}</code>.
        </span>
      ) : null}
    </p>
  );
}
