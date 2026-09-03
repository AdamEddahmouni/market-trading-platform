import type { PaperOrderPreviewResponse, PaperOrderRequest } from "../../api/schemas";

export type PaperPreviewPresentationStatus =
  | "NOT_PREVIEWED"
  | "PREVIEWING"
  | "ACCEPTED"
  | "REJECTED"
  | "STALE"
  | "REVALIDATION_REQUIRED"
  | "AUTHORITY_UNAVAILABLE"
  | "ERROR";

export type PaperPreviewPresentationState = {
  status: PaperPreviewPresentationStatus;
  title: string;
  message: string;
  reasonCodes?: string[];
  riskStatus?: string;
  decision?: string;
  canSubmit: boolean;
  previewOrigin?: "manual" | "workspace" | null;
};

export type PreviewPresentationInput = {
  authorized: boolean;
  preview: PaperOrderPreviewResponse["preview"] | null;
  confirmedRequest: PaperOrderRequest | null;
  confirmedRequestIsCurrent: boolean;
  previewMutationPending: boolean;
  error: string | null;
  previewOrigin: "manual" | "workspace" | null;
};

export function derivePreviewPresentationState(input: PreviewPresentationInput): PaperPreviewPresentationState {
  const base = {
    canSubmit: false,
    previewOrigin: input.previewOrigin,
  };

  if (!input.authorized) {
    return {
      ...base,
      status: "AUTHORITY_UNAVAILABLE",
      title: "Authority unavailable",
      message: "Paper execution is gated. Open a simulation session or restore Paper authority to preview or submit.",
    };
  }

  if (input.previewMutationPending) {
    return {
      ...base,
      status: "PREVIEWING",
      title: "Previewing",
      message: "Running preview against current Paper portfolio and risk limits…",
    };
  }

  if (input.error) {
    return {
      ...base,
      status: "ERROR",
      title: "Preview error",
      message: input.error,
    };
  }

  if (input.preview && !input.confirmedRequestIsCurrent) {
    return {
      ...base,
      status: "REVALIDATION_REQUIRED",
      title: "Revalidation required",
      message: "Order inputs changed after the last preview. Re-preview before submit.",
      riskStatus: input.preview.risk_status,
      decision: input.preview.decision,
      reasonCodes: input.preview.reason_codes,
    };
  }

  if (input.preview) {
    const passed = input.preview.risk_status === "PASS";
    return {
      ...base,
      status: passed ? "ACCEPTED" : "REJECTED",
      title: passed
        ? input.previewOrigin === "workspace"
          ? "Revalidated in workspace"
          : "Preview accepted"
        : "Preview rejected",
      message: passed
        ? "Current preview passed risk checks. Submit remains operator-controlled."
        : `Preview blocked by risk (${input.preview.decision ?? input.preview.risk_status}).`,
      riskStatus: input.preview.risk_status,
      decision: input.preview.decision,
      reasonCodes: input.preview.reason_codes,
      canSubmit: passed && input.confirmedRequestIsCurrent,
    };
  }

  return {
    ...base,
    status: "NOT_PREVIEWED",
    title: "Not previewed",
    message: "Preview against current Paper portfolio and risk state before submitting.",
  };
}
