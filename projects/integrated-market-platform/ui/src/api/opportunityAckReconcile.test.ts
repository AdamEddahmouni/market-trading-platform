import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "./hooks";
import { reconcileOpportunityAckQueries, type OpportunityAckResponse } from "./opportunityClient";

describe("reconcileOpportunityAckQueries", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("invalidates opportunities summary and trade-reviews for all related ids", async () => {
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue(undefined);
    const data: OpportunityAckResponse = {
      summary_id: "sum-1",
      opportunity_id: "opp-1",
      action: "WATCHED",
      trade_review_id: "tr-1",
    };

    await reconcileOpportunityAckQueries(client, data, "opp-1");

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.opportunitiesSummary });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tradeReviews("opp-1") });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tradeReviews("sum-1") });
  });

  it("still invalidates trade-reviews when only rowId is known", async () => {
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue(undefined);
    const data: OpportunityAckResponse = {
      summary_id: "row-only",
      action: "DISMISSED",
    };

    await reconcileOpportunityAckQueries(client, data, "row-only");

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tradeReviews("row-only") });
  });
});
