const STATUS_LABELS: Record<string, string> = {
  CREATED: "Created",
  RISK_ACCEPTED: "Risk accepted",
  RISK_REJECTED: "Risk rejected",
  SUBMITTED: "Submitted",
  WORKING: "Working",
  ACTIVATED: "Activated",
  PARTIALLY_FILLED: "Partially filled",
  FILLED: "Filled",
  CANCEL_PENDING: "Cancel pending",
  CANCELLED: "Cancelled",
  REJECTED: "Rejected",
  EXPIRED: "Expired",
};

export function paperOrderStatusLabel(state: string | undefined | null): string {
  if (!state) return "Unknown";
  const normalized = String(state).toUpperCase();
  return STATUS_LABELS[normalized] ?? normalized.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

export function paperOrderStatusTone(state: string | undefined | null): "neutral" | "open" | "success" | "danger" {
  const normalized = String(state ?? "").toUpperCase();
  if (["FILLED", "RISK_ACCEPTED"].includes(normalized)) return "success";
  if (["REJECTED", "RISK_REJECTED", "EXPIRED", "CANCELLED"].includes(normalized)) return "danger";
  if (["SUBMITTED", "WORKING", "ACTIVATED", "PARTIALLY_FILLED", "CANCEL_PENDING"].includes(normalized)) {
    return "open";
  }
  return "neutral";
}

export function paperOrderRejectionSummary(
  state: string | undefined | null,
  reasonCodes: string[] | undefined | null,
): string | null {
  const normalized = String(state ?? "").toUpperCase();
  if (!["REJECTED", "RISK_REJECTED", "EXPIRED", "CANCELLED"].includes(normalized)) {
    return null;
  }
  if (reasonCodes?.length) {
    return reasonCodes.join(", ");
  }
  if (normalized === "RISK_REJECTED" || normalized === "REJECTED") {
    return "Order rejected";
  }
  return null;
}
