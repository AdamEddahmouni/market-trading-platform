import { useCallback, useEffect, useMemo, useState } from "react";
import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import { useOpportunityEvidenceQuery, useOpportunitiesSummaryQuery } from "../../api/opportunityClient";
import { stableOpportunityKey } from "./progressiveOpportunityModel";
import { OpportunityFeedStatusBanner } from "./OpportunityFeedStatusBanner";
import { OpportunityRadarDensePanel } from "./OpportunityRadarDensePanel";
import { ProgressiveOpportunityCard } from "./ProgressiveOpportunityCard";

type Props = {
  readOnly?: boolean;
  paperAccountId?: string;
  paperActions?: boolean;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

export function OpportunityRadarCockpit({
  readOnly = false,
  paperAccountId,
  paperActions = false,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: Props) {
  const query = useOpportunitiesSummaryQuery(true);
  const state = query.isLoading ? "loading" : query.isError || !query.data ? "error" : "ready";
  const items = query.data?.items ?? [];
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const selectedRow = useMemo(() => {
    if (!items.length) return null;
    if (selectedKey) {
      const match = items.find((row) => stableOpportunityKey(row) === selectedKey);
      if (match) return match;
    }
    return items[0] ?? null;
  }, [items, selectedKey]);

  useEffect(() => {
    if (!selectedRow && items[0]) {
      setSelectedKey(stableOpportunityKey(items[0]));
    }
  }, [items, selectedRow]);

  const evidenceQuery = useOpportunityEvidenceQuery(
    selectedRow ? selectedRow.summary_id : null,
    state === "ready",
  );
  const evidencePhase =
    evidenceQuery.isLoading ? "loading" : evidenceQuery.isError ? "error" : evidenceQuery.data ? "ready" : "idle";

  const handleSelectRow = useCallback((row: OpportunityReviewRow) => {
    setSelectedKey(stableOpportunityKey(row));
  }, []);

  return (
    <div className="imp-opportunity-radar-cockpit">
      <OpportunityRadarDensePanel
        readOnly={readOnly}
        hideFeedBanner
        selectedStableKey={selectedRow ? stableOpportunityKey(selectedRow) : null}
        onSelectRow={handleSelectRow}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
      />
      <aside className="imp-opportunity-cockpit-detail" aria-label="Progressive opportunity card">
        <header className="imp-opportunity-cockpit-detail-header">
          <p className="imp-section-eyebrow">Decision workspace entry</p>
          <h2>Progressive opportunity</h2>
        </header>
        <OpportunityFeedStatusBanner
          state={state}
          feedStatus={query.data?.feed_status}
          unreadyReason={query.data?.unready_reason}
          nextAction={query.data?.next_action}
        />
        {state === "ready" && selectedRow && query.data?.feed_status !== "UNREADY" ? (
          <ProgressiveOpportunityCard
            row={selectedRow}
            evidence={evidenceQuery.data}
            evidencePhase={evidencePhase}
            paperAccountId={paperAccountId}
            paperActions={paperActions}
            readOnly={readOnly}
            density="cockpit"
            onExplain={onExplain}
            onInspect={onInspect}
            onOpenWorkspace={onOpenWorkspace}
            onAck={onAck}
          />
        ) : null}
        {state === "ready" && !selectedRow && query.data?.feed_status !== "UNREADY" ? (
          <p className="unavailable">Select a ranked row to open the progressive card.</p>
        ) : null}
      </aside>
    </div>
  );
}
