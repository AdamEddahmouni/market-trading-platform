import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import { queryKeys } from "./hooks";
import { AsOfContextSchema } from "./schemas";

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
    data_quality: z.record(z.string(), z.unknown()).nullable().optional(),
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
  })
  .passthrough();

export type OpportunityAckAction = "watch" | "dismiss" | "review";

export function postOpportunityAck(rowId: string, action: OpportunityAckAction) {
  return postJson(`/opportunities/${rowId}/${action}`, {}, OpportunityAckSchema);
}

export function useOpportunityAckMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ rowId, action }: { rowId: string; action: OpportunityAckAction }) =>
      postOpportunityAck(rowId, action),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.opportunitiesSummary });
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
    data_quality: z.record(z.string(), z.unknown()).nullable().optional(),
    ranking_basis: z.string().nullable().optional(),
    created_at_ns: z.number().nullable().optional(),
    duplicates: z.array(z.unknown()).optional(),
    supersession_reason: z.string().nullable().optional(),
    unavailable_fields: z.array(z.string()).optional(),
    lineage_refs: z.array(z.unknown()).optional(),
    items: z.array(z.unknown()).optional(),
    copy: z.string().nullable().optional(),
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
    queryKey: ["opportunities", "evidence", rowId],
    queryFn: () => getOpportunityEvidence(rowId as string),
    enabled: enabled && Boolean(rowId),
  });
}
