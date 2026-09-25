/**
 * Radar adapters from authoritative opportunity rows onto OperatorActionDescriptor.
 * These functions do not call the network and do not decide ranking or execution.
 */
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import type {
  OperatorActionDescriptor,
  OperatorActionDomainReason,
  OperatorActionResultState,
} from "../../state/operatorAction";
import { isOpportunityIneligible } from "../opportunity/opportunityPresentation";

export type RadarActionSurface = "detail" | "queue";

export type RadarActionContext = {
  row: OpportunityReviewRow | null;
  /** Feed/query state. Unknown or failed source stays unavailable. */
  sourceState: "ready" | "loading" | "failed";
  readOnly: boolean;
  paperActions: boolean;
  paperAccountId?: string | null;
  surface: RadarActionSurface;
};

const RECORD = "operator_record" as const;
const NAV = "navigation" as const;

function target(row: OpportunityReviewRow): { label: string; id?: string } {
  const id = row.opportunity_id || row.summary_id;
  return { label: row.instrument_id || row.headline || id, id };
}

function lifecycle(row: OpportunityReviewRow): string {
  return String(row.lifecycle_state ?? "").toUpperCase();
}

function sourceReason(ctx: RadarActionContext): OperatorActionDomainReason | null {
  if (ctx.sourceState === "loading") {
    return { code: "RADAR_FEED_LOADING", detail: "Opportunity state is still loading." };
  }
  if (ctx.sourceState === "failed") {
    return { code: "RADAR_FEED_UNAVAILABLE", detail: "Opportunity state could not be loaded." };
  }
  if (!ctx.row) {
    return { code: "OPPORTUNITY_STATE_UNAVAILABLE", detail: "No opportunity is selected." };
  }
  return null;
}

function opportunityGate(row: OpportunityReviewRow): {
  availability: "BLOCKED" | "UNAVAILABLE";
  reason: OperatorActionDomainReason;
} | null {
  const life = lifecycle(row);
  if (life.includes("EXPIRED")) {
    return {
      availability: "BLOCKED",
      reason: { code: "OPPORTUNITY_EXPIRED", detail: "This opportunity is expired." },
    };
  }
  if (life === "DISMISS" || life === "DISMISSED") {
    return {
      availability: "BLOCKED",
      reason: { code: "ALREADY_DISMISSED", detail: "This opportunity is already dismissed." },
    };
  }
  const supersession = row.supersession_reason;
  if (supersession != null && String(supersession).trim() !== "") {
    return {
      availability: "BLOCKED",
      reason: {
        code: "OPPORTUNITY_SUPERSEDED",
        detail: "This opportunity has been superseded.",
      },
    };
  }
  if (row.eligibility_state === "UNAVAILABLE") {
    return {
      availability: "UNAVAILABLE",
      reason: { code: "ELIGIBILITY_UNAVAILABLE", detail: "Eligibility state is unavailable." },
    };
  }
  if (!row.eligibility_state) {
    return {
      availability: "UNAVAILABLE",
      reason: { code: "ELIGIBILITY_UNKNOWN", detail: "Eligibility state was not reported." },
    };
  }
  if (isOpportunityIneligible(row)) {
    return {
      availability: "BLOCKED",
      reason: { code: "OPPORTUNITY_INELIGIBLE", detail: "Eligibility gate failed." },
    };
  }
  return null;
}

function ackSpecificBlock(
  row: OpportunityReviewRow,
  action: OpportunityAckAction,
): OperatorActionDomainReason | null {
  const life = lifecycle(row);
  if (action === "watch" && (life === "WATCH" || life === "WATCHED")) {
    return { code: "ALREADY_WATCHED", detail: "This opportunity is already watched." };
  }
  if (action === "review" && (life === "REVIEW" || life === "REVIEWED")) {
    return { code: "ALREADY_REVIEWED", detail: "This opportunity is already reviewed." };
  }
  return null;
}

function modeBlock(ctx: RadarActionContext): { availability: "READ_ONLY" | "UNAVAILABLE"; reason: OperatorActionDomainReason } | null {
  if (ctx.readOnly) {
    return {
      availability: "READ_ONLY",
      reason: { code: "MODE_READ_ONLY", detail: "Read-only in this mode." },
    };
  }
  if (!ctx.paperActions) {
    return {
      availability: "UNAVAILABLE",
      reason: {
        code: "PAPER_ACTIONS_UNAVAILABLE",
        detail: "Paper actions unavailable in this mode.",
      },
    };
  }
  if (!ctx.paperAccountId) {
    return {
      availability: "UNAVAILABLE",
      reason: { code: "PAPER_ACCOUNT_UNAVAILABLE", detail: "Paper account is not available." },
    };
  }
  return null;
}

function mutationAction(
  ctx: RadarActionContext,
  action: OpportunityAckAction,
  title: string,
  description: string,
): OperatorActionDescriptor {
  const id = `radar.${action}`;
  const base = {
    id,
    domain: "radar.opportunity",
    title,
    description,
    consequence: RECORD,
    target: ctx.row ? target(ctx.row) : { label: "Opportunity" },
  };
  const missing = sourceReason(ctx);
  if (missing || !ctx.row) {
    return {
      ...base,
      availability: "UNAVAILABLE",
      reason: missing ?? { code: "OPPORTUNITY_STATE_UNAVAILABLE", detail: "No opportunity is selected." },
    };
  }
  const gated = opportunityGate(ctx.row);
  if (gated) {
    return { ...base, availability: gated.availability, reason: gated.reason };
  }
  const repeated = ackSpecificBlock(ctx.row, action);
  if (repeated) {
    return { ...base, availability: "BLOCKED", reason: repeated };
  }
  const mode = modeBlock(ctx);
  if (mode) {
    return { ...base, availability: mode.availability, reason: mode.reason };
  }
  return { ...base, availability: "AVAILABLE" };
}

export function reviewOpportunityAction(ctx: RadarActionContext): OperatorActionDescriptor {
  const title = ctx.surface === "queue" ? "Review" : "Mark reviewed";
  return mutationAction(
    ctx,
    "review",
    title,
    "Records an operator review. This does not submit an order.",
  );
}

export function watchOpportunityAction(ctx: RadarActionContext): OperatorActionDescriptor {
  return mutationAction(
    ctx,
    "watch",
    "Watch",
    "Records a watch. This does not submit an order.",
  );
}

export function dismissOpportunityAction(ctx: RadarActionContext): OperatorActionDescriptor {
  return mutationAction(
    ctx,
    "dismiss",
    "Dismiss",
    "Records a dismiss and removes the opportunity from the active queue. This does not submit an order.",
  );
}

export function openWorkspaceAction(ctx: RadarActionContext): OperatorActionDescriptor {
  const title = ctx.surface === "queue" ? "Workspace" : "Open workspace";
  const base = {
    id: "radar.open-workspace",
    domain: "radar.handoff",
    title,
    description: "Opens Workspace for this opportunity. Opening is not authorization to execute.",
    consequence: NAV,
    target: ctx.row ? target(ctx.row) : { label: "Workspace" },
  };
  const missing = sourceReason(ctx);
  if (missing || !ctx.row) {
    return {
      ...base,
      availability: "UNAVAILABLE",
      reason: missing ?? { code: "OPPORTUNITY_STATE_UNAVAILABLE", detail: "No opportunity is selected." },
    };
  }
  if (!ctx.row.instrument_id) {
    return {
      ...base,
      availability: "BLOCKED",
      reason: {
        code: "WORKSPACE_INSTRUMENT_MISSING",
        detail: "Workspace handoff needs an instrument on this opportunity.",
      },
    };
  }
  return { ...base, availability: "AVAILABLE" };
}

export function radarOpportunityActions(ctx: RadarActionContext): {
  review: OperatorActionDescriptor;
  watch: OperatorActionDescriptor;
  dismiss: OperatorActionDescriptor;
  openWorkspace: OperatorActionDescriptor;
} {
  return {
    review: reviewOpportunityAction(ctx),
    watch: watchOpportunityAction(ctx),
    dismiss: dismissOpportunityAction(ctx),
    openWorkspace: openWorkspaceAction(ctx),
  };
}

/** Maps the existing ack phase onto the shared result vocabulary. */
export function radarAckResult(
  phase: "idle" | "submitting" | "synchronizing" | "failed" | "completed" | "reconciliation_failed",
  reviewId?: string | null,
): OperatorActionResultState | null {
  if (phase === "failed") {
    return {
      kind: "REQUEST_FAILED",
      message: "Operator action failed. Previous durable review state was not changed by this attempt.",
    };
  }
  if (phase === "reconciliation_failed") {
    return {
      kind: "REFRESH_FAILED_AFTER_MUTATION",
      message: reviewId
        ? `Action was accepted (review ${reviewId}), but durable review retrieval failed.`
        : "Action was accepted, but durable review retrieval failed.",
    };
  }
  if (phase === "completed") {
    return {
      kind: "SUCCESS",
      message: "DecisionTrace and TradeReview were retrieved for this opportunity.",
    };
  }
  return null;
}
