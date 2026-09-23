import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { fetchJson } from "./fetchJson";
import { queryKeys } from "./hooks";

const TradeReviewItemSchema = z
  .object({
    review_id: z.string(),
    review_mode: z.string(),
    decision: z.string(),
    notes: z.string().optional(),
    reflection: z.string().optional(),
    tags: z.array(z.string()).optional(),
    mistakes: z.array(z.string()).optional(),
    derived_reflections: z.array(z.record(z.string(), z.unknown())).optional(),
  })
  .passthrough();

const TradeReviewsResponseSchema = z.object({
  opportunity_id: z.string(),
  acceptance_label: z.string().optional(),
  items: z.array(TradeReviewItemSchema),
});

export type TradeReviewItem = z.infer<typeof TradeReviewItemSchema>;
export type TradeReviewsResponse = z.infer<typeof TradeReviewsResponseSchema>;

export function getTradeReviewsForOpportunity(opportunityId: string) {
  const query = new URLSearchParams({ opportunity_id: opportunityId });
  return fetchJson(`/intelligence/trade-reviews?${query}`, TradeReviewsResponseSchema);
}

export function useTradeReviewsQuery(opportunityId: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.tradeReviews(String(opportunityId ?? "")),
    queryFn: () => getTradeReviewsForOpportunity(String(opportunityId)),
    enabled: Boolean(opportunityId) && enabled,
  });
}
