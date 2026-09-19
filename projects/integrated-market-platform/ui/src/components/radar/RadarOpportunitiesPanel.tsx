import { useCallback, useEffect, useMemo, useState } from "react";
import type { AttentionItem } from "../../api/client";
import type {
  OpportunityAckAction,
  OpportunityReviewRow,
} from "../../api/opportunityClient";
import {
  useOpportunityAckMutation,
  useOpportunityEvidenceQuery,
  useOpportunitiesSummaryQuery,
} from "../../api/opportunityClient";
import { BP_MD } from "../../lib/breakpoints";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { OpportunityFeedState } from "../opportunity/OpportunityFeedState";
import { stableOpportunityKey } from "../opportunity/opportunityPresentation";
import type { Mode } from "../mode-session/types";
import { OpportunityDetailCard } from "./OpportunityDetailCard";
import { RadarDetailSheet } from "./RadarDetailSheet";
import { RadarQueueTable } from "./RadarQueueTable";

type Props = {
  mode: Mode;
  readOnly?: boolean;
  paperAccountId?: string;
  paperActions?: boolean;
  /** Deep-link selection (`/radar?selected=<stable key>`) from the Command bridge. */
  initialSelectedKey?: string | null;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

/**
 * Radar Opportunities tab: feed status as human language, the ranked queue,
 * and the selected opportunity's progressive-disclosure detail. Below BP_MD
 * the grid collapses and detail opens in an overlay sheet so the queue stays
 * scannable and selection never destroys operator context.
 */
export function RadarOpportunitiesPanel({
  mode,
  readOnly = false,
  paperAccountId,
  paperActions = false,
  initialSelectedKey = null,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: Props) {
  const query = useOpportunitiesSummaryQuery(true);
  const ackMutation = useOpportunityAckMutation();
  const state = query.isLoading ? "loading" : query.isError || !query.data ? "error" : "ready";
  const items = query.data?.items ?? [];
  const feedStatus = query.data?.feed_status;
  const sheetLayout = useMediaQuery(`(max-width: ${BP_MD}px)`);
  const [selectedKey, setSelectedKey] = useState<string | null>(initialSelectedKey);
  const [sheetOpen, setSheetOpen] = useState(() => Boolean(initialSelectedKey) && sheetLayout);

  // A deep-linked selection takes effect when it changes (e.g. following a
  // Command bridge link while already on Radar).
  useEffect(() => {
    if (!initialSelectedKey) return;
    setSelectedKey(initialSelectedKey);
    if (sheetLayout) setSheetOpen(true);
  }, [initialSelectedKey, sheetLayout]);

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
  const evidencePhase = evidenceQuery.isLoading
    ? "loading"
    : evidenceQuery.isError
      ? "error"
      : evidenceQuery.data
        ? "ready"
        : "idle";

  const handleSelectRow = useCallback(
    (row: OpportunityReviewRow) => {
      setSelectedKey(stableOpportunityKey(row));
      if (sheetLayout) setSheetOpen(true);
    },
    [sheetLayout],
  );

  // Leaving the sheet layout dismisses the overlay; the inline detail takes over.
  useEffect(() => {
    if (!sheetLayout) setSheetOpen(false);
  }, [sheetLayout]);

  const handleAck = useCallback(
    (row: OpportunityReviewRow, action: OpportunityAckAction) => {
      ackMutation.mutate({ rowId: row.opportunity_id || row.summary_id, action });
    },
    [ackMutation],
  );

  return (
    <OpportunityFeedState
      state={state}
      feedStatus={feedStatus}
      unreadyReason={query.data?.unready_reason}
      nextAction={query.data?.next_action}
      mode={mode}
      itemCount={items.length}
      withheldRankedCount={query.data?.withheld_ranked_count}
      bookHonesty={query.data?.book_honesty}
      onRetry={() => void query.refetch()}
      emptyReason="An empty queue is valid: nothing has been minted for the current coverage. The investigation screener on the Screeners tab shows what discovery is seeing."
    >
    <div className="imp-radar-opportunities" data-testid="imp-radar-opportunities">
      <section className="imp-radar-queue-section" aria-label="Ranked opportunity queue">
        <RadarQueueTable
          items={items}
          selectedStableKey={selectedRow ? stableOpportunityKey(selectedRow) : null}
          readOnly={readOnly}
          paperActions={paperActions}
          onSelectRow={handleSelectRow}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      </section>
      {!sheetLayout ? (
      <section className="imp-radar-detail-section" aria-label="Selected opportunity">
        {selectedRow ? (
          <OpportunityDetailCard
            row={selectedRow}
            evidence={evidenceQuery.data}
            evidencePhase={evidencePhase}
            paperAccountId={paperAccountId}
            paperActions={paperActions}
            readOnly={readOnly}
            feed={query.data?.as_of_context ?? null}
            withheldRankedCount={query.data?.withheld_ranked_count}
            bookHonesty={query.data?.book_honesty}
            unreadyReason={query.data?.unready_reason}
            onExplain={onExplain}
            onInspect={onInspect}
            onOpenWorkspace={onOpenWorkspace}
            onAck={paperActions && !readOnly ? handleAck : undefined}
          />
        ) : (
          <p className="imp-radar-muted">Select a ranked row to open the opportunity detail.</p>
        )}
      </section>
      ) : null}
    </div>
    {sheetLayout ? (
      <RadarDetailSheet open={sheetOpen && Boolean(selectedRow)} onClose={() => setSheetOpen(false)}>
        {selectedRow ? (
          <OpportunityDetailCard
            row={selectedRow}
            evidence={evidenceQuery.data}
            evidencePhase={evidencePhase}
            paperAccountId={paperAccountId}
            paperActions={paperActions}
            readOnly={readOnly}
            feed={query.data?.as_of_context ?? null}
            withheldRankedCount={query.data?.withheld_ranked_count}
            bookHonesty={query.data?.book_honesty}
            unreadyReason={query.data?.unready_reason}
            onExplain={onExplain}
            onInspect={onInspect}
            onOpenWorkspace={onOpenWorkspace}
            onAck={paperActions && !readOnly ? handleAck : undefined}
          />
        ) : null}
      </RadarDetailSheet>
    ) : null}
    </OpportunityFeedState>
  );
}
