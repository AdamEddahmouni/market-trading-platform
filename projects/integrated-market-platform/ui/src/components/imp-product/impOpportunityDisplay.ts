import type { OpportunityReviewRow } from "../../api/opportunityClient";

export function opportunityTags(row: OpportunityReviewRow, limit = 3): string[] {
  const fromDimensions =
    row.ranking_vector?.dimensions
      ?.filter((d) => d.status === "PRESENT" && d.name)
      .map((d) => d.name.replace(/_/g, " "))
      .slice(0, limit) ?? [];
  if (fromDimensions.length) return fromDimensions;
  if (row.lifecycle_state) return [row.lifecycle_state];
  if (row.identity_kind) return [row.identity_kind.replace(/_/g, " ")];
  return [];
}

export function opportunityRankLabel(row: OpportunityReviewRow): string | null {
  if (row.rank_order == null) return null;
  return `#${row.rank_order}`;
}

export function opportunitySymbol(row: OpportunityReviewRow): string {
  if (row.instrument_id?.trim()) return row.instrument_id.trim();
  return "—";
}
