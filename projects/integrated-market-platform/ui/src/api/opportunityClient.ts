import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import { queryKeys } from "./hooks";
import { AsOfContextSchema } from "./schemas";

export const OpportunityDataQualitySchema = z
  .object({
    status: z.string().optional(),
    freshness: z.string().optional(),
    entitlement: z.string().optional(),
    connection: z.string().optional(),
    source: z.string().optional(),
    reason_codes: z.array(z.string()).optional(),
    /** Backend-owned Command flag. Do not re-derive STALE/DEGRADED/INVALID in the UI. */
    operator_surface_flag: z.enum(["OK", "STALE_OR_DEGRADED"]).optional(),
  })
  .passthrough();

export const OpportunityReviewRowSchema = z
  .object({
    schema_version: z.string().optional(),
    summary_id: z.string(),
    instrument_id: z.string().nullable().optional(),
    headline: z.string(),
    opportunity_id: z.string().nullable().optional(),
    identity_kind: z.string().optional(),
    eligibility_state: z.string().nullable().optional(),
    lifecycle_state: z.string().nullable().optional(),
    next_safe_action: z.string().optional(),
    rank_order: z.number().nullable().optional(),
    unavailable_fields: z.array(z.string()).optional(),
    explanation_ref: z.string().optional(),
    ranking_vector: z
      .object({
        basis: z.string(),
        dimensions: z.array(
          z.object({
            name: z.string(),
            status: z.string(),
            value: z.unknown().optional(),
            unit: z.string().nullable().optional(),
            reason_code: z.string().nullable().optional(),
          }),
        ),
        rank_order: z.number().nullable().optional(),
      })
      .nullable()
      .optional(),
    data_quality: OpportunityDataQualitySchema.nullable().optional(),
    /**
     * Backend-translated provider-linkage warning phrases from quality.flags.
     * Render as supplied — do not map flags or infer ticker contradictions here.
     */
    provider_linkage_warnings: z.array(z.string()).optional(),
    decision_support: z
      .object({
        authority: z.string().optional(),
        kill_switch: z.string().optional(),
        reason_codes: z.array(z.string()).optional(),
      })
      .passthrough()
      .optional(),
  })
  .passthrough();

export const OpportunitiesSummaryResponseSchema = z.object({
  as_of_context: AsOfContextSchema,
  quality_summary: z.object({ state: z.string() }).passthrough(),
  feed_status: z.string(),
  reason: z.string().optional(),
  unready_reason: z.string().optional(),
  next_action: z.string().optional(),
  items: z.array(OpportunityReviewRowSchema),
  next_cursor: z.string().nullable().optional(),
  /** Present when live ranked rows exist but the receive clock is missing. */
  withheld_ranked_count: z.number().int().nonnegative().optional(),
  book_honesty: z.string().optional(),
});

export type OpportunityReviewRow = z.infer<typeof OpportunityReviewRowSchema>;
export type OpportunitiesSummaryResponse = z.infer<typeof OpportunitiesSummaryResponseSchema>;

export function getOpportunitiesSummary() {
  return fetchJson("/opportunities/summary", OpportunitiesSummaryResponseSchema);
}

export function useOpportunitiesSummaryQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.opportunitiesSummary,
    queryFn: getOpportunitiesSummary,
    enabled,
  });
}

const OpportunityAckSchema = z
  .object({
    summary_id: z.string(),
    action: z.string(),
    opportunity_id: z.string().nullable().optional(),
    paper_account_id: z.string().optional(),
    created_at_ns: z.number().optional(),
    /** Present when Watch/Dismiss materialized a durable TradeReview in the same request. */
    trade_review_id: z.string().optional(),
    decision_trace_mode: z.string().optional(),
  })
  .passthrough();

export type OpportunityAckAction = "watch" | "dismiss" | "review";
export type OpportunityAckResponse = z.infer<typeof OpportunityAckSchema>;

export function postOpportunityAck(rowId: string, action: OpportunityAckAction) {
  return postJson(`/opportunities/${rowId}/${action}`, {}, OpportunityAckSchema);
}

/**
 * After a successful operator ack, deliberately reconcile authoritative backend
 * state: ranked queue (lifecycle / dismiss filtering) and durable trade reviews.
 * Does not fabricate review rows in the client.
 */
export async function reconcileOpportunityAckQueries(
  client: QueryClient,
  data: OpportunityAckResponse,
  rowId: string,
): Promise<void> {
  const ids = new Set<string>();
  ids.add(rowId);
  if (data.summary_id) ids.add(data.summary_id);
  if (data.opportunity_id) ids.add(data.opportunity_id);
  await client.invalidateQueries({ queryKey: queryKeys.opportunitiesSummary });
  await Promise.all(
    [...ids].map((id) => client.invalidateQueries({ queryKey: queryKeys.tradeReviews(id) })),
  );
}

export function useOpportunityAckMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ rowId, action }: { rowId: string; action: OpportunityAckAction }) =>
      postOpportunityAck(rowId, action),
    onSuccess: async (data, variables) => {
      await reconcileOpportunityAckQueries(client, data, variables.rowId);
    },
  });
}

export const OpportunityEvidenceResponseSchema = z
  .object({
    identity_kind: z.string().optional(),
    evidence_class: z.string().nullable().optional(),
    evidence_promotion_reason: z.string().nullable().optional(),
    family_admission_status: z.string().nullable().optional(),
    family_admission_reason: z.string().nullable().optional(),
    data_quality: OpportunityDataQualitySchema.nullable().optional(),
    ranking_basis: z.string().nullable().optional(),
    /** Epoch nanoseconds. Distinct from operator `created_at` unix seconds. */
    created_at_ns: z.number().nullable().optional(),
    duplicates: z.array(z.unknown()).optional(),
    supersession_reason: z.string().nullable().optional(),
    unavailable_fields: z.array(z.string()).optional(),
    lineage_refs: z.array(z.unknown()).optional(),
    items: z.array(z.unknown()).optional(),
    copy: z.string().nullable().optional(),
    research_artifact_evidence: z
      .object({
        authority_class: z.string().optional(),
        readiness: z.string().optional(),
        attachments: z.array(z.record(z.string(), z.unknown())).optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
  })
  .passthrough();

export type OpportunityEvidenceResponse = z.infer<typeof OpportunityEvidenceResponseSchema>;

export const OpportunityDetailResponseSchema = OpportunityReviewRowSchema.extend({
  preview_href: z.string().optional(),
  agent_enrichment_records: z.array(z.unknown()).optional(),
  lineage_refs: z.array(z.unknown()).optional(),
}).passthrough();

export type OpportunityDetailResponse = z.infer<typeof OpportunityDetailResponseSchema>;

export function getOpportunityDetail(rowId: string) {
  return fetchJson(`/opportunities/${rowId}`, OpportunityDetailResponseSchema);
}

export function getOpportunityEvidence(rowId: string) {
  return fetchJson(`/opportunities/${rowId}/evidence`, OpportunityEvidenceResponseSchema);
}

export function useOpportunityEvidenceQuery(rowId: string | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.opportunityEvidence(rowId as string),
    queryFn: () => getOpportunityEvidence(rowId as string),
    enabled: enabled && Boolean(rowId),
  });
}
