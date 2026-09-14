import { describe, expect, it } from "vitest";
import {
  ApiRequestError,
  CANONICAL_ERROR_CATEGORIES,
  formatApiRequestError,
  isCanonicalErrorCategory,
  parseApiErrorEnvelope,
} from "./errors";

describe("canonical error_category union", () => {
  it("matches the twelve backend WS05 categories from PR #90", () => {
    expect([...CANONICAL_ERROR_CATEGORIES]).toEqual([
      "VALIDATION_ERROR",
      "PROVIDER_UNAVAILABLE",
      "PROVIDER_REJECTED",
      "STALE_DATA",
      "UNSUPPORTED_CAPABILITY",
      "ACCOUNT_UNAVAILABLE",
      "RISK_BLOCKED",
      "MODE_BLOCKED",
      "AUTH_ERROR",
      "RATE_LIMITED",
      "TIMEOUT",
      "INTERNAL_ERROR",
    ]);
  });

  it("accepts only exact backend category strings", () => {
    expect(isCanonicalErrorCategory("MODE_BLOCKED")).toBe(true);
    expect(isCanonicalErrorCategory("mode_blocked")).toBe(false);
    expect(isCanonicalErrorCategory("UI_REQUEST_INVALID")).toBe(false);
  });
});

describe("parseApiErrorEnvelope", () => {
  it("returns the API error_category without remapping reason_code", () => {
    expect(
      parseApiErrorEnvelope({
        error: "bad field",
        reason_code: "UI_REQUEST_INVALID",
        error_category: "VALIDATION_ERROR",
      }),
    ).toEqual({
      error: "bad field",
      reason_code: "UI_REQUEST_INVALID",
      error_category: "VALIDATION_ERROR",
    });
  });

  it("fails closed when error_category is omitted", () => {
    expect(
      parseApiErrorEnvelope({
        error: "bad field",
        reason_code: "UI_REQUEST_INVALID",
      }),
    ).toBeNull();
  });

  it("fails closed for an unknown error_category", () => {
    expect(
      parseApiErrorEnvelope({
        error: "bad field",
        reason_code: "UI_REQUEST_INVALID",
        error_category: "NOT_A_BACKEND_CATEGORY",
      }),
    ).toBeNull();
  });

  it("does not invent a category from reason_code or payload.code", () => {
    expect(
      parseApiErrorEnvelope({
        code: "UI_REQUEST_INVALID",
        message: "bad field",
        reason_code: "PAPER_EXECUTION_NOT_AUTHORIZED",
      }),
    ).toBeNull();
  });
});

describe("formatApiRequestError", () => {
  it("surfaces error_category then reason_code then message", () => {
    const error = new ApiRequestError({
      error: "Paper execution is not authorized",
      reason_code: "PAPER_EXECUTION_NOT_AUTHORIZED",
      error_category: "MODE_BLOCKED",
    });
    expect(formatApiRequestError(error)).toBe(
      "MODE_BLOCKED: PAPER_EXECUTION_NOT_AUTHORIZED: Paper execution is not authorized",
    );
    expect(error.code).toBe("PAPER_EXECUTION_NOT_AUTHORIZED");
    expect(error.errorCategory).toBe("MODE_BLOCKED");
  });
});
