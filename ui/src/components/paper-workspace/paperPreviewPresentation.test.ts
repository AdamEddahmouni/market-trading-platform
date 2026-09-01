import { describe, expect, it } from "vitest";
import { derivePreviewPresentationState } from "./paperPreviewPresentation";

describe("derivePreviewPresentationState", () => {
  const base = {
    authorized: true,
    preview: null,
    confirmedRequest: null,
    confirmedRequestIsCurrent: false,
    previewMutationPending: false,
    error: null,
    previewOrigin: null as const,
  };

  it("maps not previewed", () => {
    expect(derivePreviewPresentationState(base).status).toBe("NOT_PREVIEWED");
  });

  it("maps previewing", () => {
    expect(
      derivePreviewPresentationState({ ...base, previewMutationPending: true }).status,
    ).toBe("PREVIEWING");
  });

  it("maps accepted preview", () => {
    const state = derivePreviewPresentationState({
      ...base,
      preview: { risk_status: "PASS", decision: "ALLOW" },
      confirmedRequest: {
        side: "BUY",
        quantity: 1,
        order_type: "MARKET",
        instrument_id: "BIYA",
        symbol: "BIYA",
        client_order_id: "x",
        idempotency_key: "x",
      },
      confirmedRequestIsCurrent: true,
      previewOrigin: "workspace",
    });
    expect(state.status).toBe("ACCEPTED");
    expect(state.canSubmit).toBe(true);
    expect(state.title).toMatch(/Revalidated/i);
  });

  it("maps rejected preview", () => {
    const state = derivePreviewPresentationState({
      ...base,
      preview: { risk_status: "BLOCKED", decision: "BLOCK", reason_codes: ["POSITION_LIMIT"] },
      confirmedRequestIsCurrent: true,
    });
    expect(state.status).toBe("REJECTED");
    expect(state.reasonCodes).toEqual(["POSITION_LIMIT"]);
  });

  it("maps revalidation required when preview is stale", () => {
    const state = derivePreviewPresentationState({
      ...base,
      preview: { risk_status: "PASS", decision: "ALLOW" },
      confirmedRequestIsCurrent: false,
    });
    expect(state.status).toBe("REVALIDATION_REQUIRED");
  });

  it("maps authority unavailable", () => {
    expect(derivePreviewPresentationState({ ...base, authorized: false }).status).toBe(
      "AUTHORITY_UNAVAILABLE",
    );
  });

  it("maps transport error", () => {
    expect(derivePreviewPresentationState({ ...base, error: "offline" }).status).toBe("ERROR");
  });
});
