/** Canonical IMP API error taxonomy. Mirrors backend `CanonicalErrorCategory` (PR #90). */

export const CANONICAL_ERROR_CATEGORIES = [
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
] as const;

export type CanonicalErrorCategory = (typeof CANONICAL_ERROR_CATEGORIES)[number];

const CANONICAL_ERROR_CATEGORY_SET: ReadonlySet<string> = new Set(CANONICAL_ERROR_CATEGORIES);

export function isCanonicalErrorCategory(value: unknown): value is CanonicalErrorCategory {
  return typeof value === "string" && CANONICAL_ERROR_CATEGORY_SET.has(value);
}

export type ApiErrorEnvelope = {
  error: string;
  reason_code: string;
  error_category: CanonicalErrorCategory;
};

/**
 * Parse the UI API error envelope. Fail closed when `error_category` is omitted
 * or not one of the twelve backend categories — never infer from `reason_code`.
 */
export function parseApiErrorEnvelope(payload: unknown): ApiErrorEnvelope | null {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    return null;
  }
  const record = payload as Record<string, unknown>;
  if (!isCanonicalErrorCategory(record.error_category)) {
    return null;
  }
  if (typeof record.error !== "string" || typeof record.reason_code !== "string") {
    return null;
  }
  return {
    error: record.error,
    reason_code: record.reason_code,
    error_category: record.error_category,
  };
}

export class ApiRequestError extends Error {
  readonly code: string;
  readonly reasonCode: string;
  readonly errorCategory: CanonicalErrorCategory;

  constructor(envelope: ApiErrorEnvelope) {
    super(envelope.error);
    this.name = "ApiRequestError";
    this.code = envelope.reason_code;
    this.reasonCode = envelope.reason_code;
    this.errorCategory = envelope.error_category;
  }
}

export function formatApiRequestError(error: ApiRequestError): string {
  return `${error.errorCategory}: ${error.reasonCode}: ${error.message}`;
}
