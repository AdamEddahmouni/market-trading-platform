import type { PaperPreviewPresentationState } from "./paperPreviewPresentation";

type Props = {
  state: PaperPreviewPresentationState;
};

const STATUS_CLASS: Record<PaperPreviewPresentationState["status"], string> = {
  NOT_PREVIEWED: "preview-not-started",
  PREVIEWING: "preview-loading",
  ACCEPTED: "preview-pass",
  REJECTED: "preview-blocked",
  STALE: "preview-stale",
  REVALIDATION_REQUIRED: "preview-stale",
  AUTHORITY_UNAVAILABLE: "preview-authority",
  ERROR: "preview-error",
};

export function PaperPreviewStatus({ state }: Props) {
  return (
    <section
      className={`panel paper-cockpit-panel paper-preview-status ${STATUS_CLASS[state.status]}`}
      aria-labelledby="paper-preview-status-heading"
      aria-live="polite"
    >
      <h2 id="paper-preview-status-heading">Preview status</h2>
      <p>
        <strong>{state.title}</strong>
      </p>
      <p>{state.message}</p>
      {state.riskStatus ? (
        <p>
          Risk: <strong>{state.riskStatus}</strong>
          {state.decision ? ` (${state.decision})` : ""}
        </p>
      ) : null}
      {state.reasonCodes && state.reasonCodes.length > 0 ? (
        <p>Reasons: {state.reasonCodes.join(", ")}</p>
      ) : null}
      {!state.canSubmit && state.status !== "AUTHORITY_UNAVAILABLE" && state.status !== "NOT_PREVIEWED" ? (
        <p className="muted">Submit remains disabled until preview passes and inputs are current.</p>
      ) : null}
    </section>
  );
}
