import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { fetchJson } from "./fetchJson";
import { queryKeys } from "./hooks";

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
        authority: z.string(),
        reason_codes: z.array(z.string()).optional(),
      })
      .passthrough()
      .optional(),
  })
  .passthrough();

export const OpportunitiesSummaryResponseSchema = z.object({
  as_of_context: z.object({ mode: z.string() }).passthrough(),
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
