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
import { resolveSemanticState } from "../../state/semanticState";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { EmptyState, ErrorState } from "../imp-ui/FeedbackStates";
import { LoadingState } from "../shared/LoadingState";
import { stableOpportunityKey } from "../imp-product/progressiveOpportunityModel";
import type { Mode } from "../mode-session/types";
import { OpportunityDetailCard } from "./OpportunityDetailCard";
import { RadarQueueTable } from "./RadarQueueTable";

type Props = {
  mode: Mode;
  readOnly?: boolean;
  paperAccountId?: string;
  paperActions?: boolean;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

function controlHref(nextAction?: string): string {
  if (!nextAction) return "/control";
  if (nextAction.startsWith("/")) return nextAction;
  return "/control";
}

/**
 * Radar Opportunities tab: feed status as human language, the ranked queue,
 * and the selected opportunity's progressive-disclosure detail.
 */
export function RadarOpportunitiesPanel({
  mode,
  readOnly = false,
  paperAccountId,
  paperActions = false,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: Props) {
  const query = useOpportunitiesSummaryQuery(true);
  const ackMutation = useOpportunityAckMutation();
  const state = query.isLoading ? "loading" : query.isError || !query.data ? "error" : "ready";
  const items = query.data?.items ?? [];
  const feedStatus = query.data?.feed_status;
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
  const evidencePhase = evidenceQuery.isLoading
    ? "loading"
    : evidenceQuery.isError
      ? "error"
      : evidenceQuery.data
        ? "ready"
        : "idle";

  const handleSelectRow = useCallback((row: OpportunityReviewRow) => {
    setSelectedKey(stableOpportunityKey(row));
  }, []);

  const handleAck = useCallback(
    (row: OpportunityReviewRow, action: OpportunityAckAction) => {
      ackMutation.mutate({ rowId: row.opportunity_id || row.summary_id, action });
    },
    [ackMutation],
  );

  if (state === "loading") {
    return <LoadingState label="Loading ranked opportunities…" />;
  }

  if (state === "error") {
    return (
      <ErrorState
        title="Opportunity ranking is unavailable."
        affects="The ranked queue cannot be loaded. Screeners and workspace evidence remain available."
        onRetry={() => void query.refetch()}
      />
    );
  }

  if (feedStatus === "UNREADY") {
    const unready = resolveSemanticState("research", "UNREADY", {
      params: { reason: query.data?.unready_reason },
    });
    return (
      <AttentionBanner
        tone={unready.tone}
        affects={unready.affects}
        action={{ label: "Open Control", href: controlHref(query.data?.next_action) }}
      >
        {unready.sentence ?? unready.label}
        {query.data?.unready_reason ? (
          <span className="imp-radar-muted"> ({query.data.unready_reason})</span>
        ) : null}
      </AttentionBanner>
    );
  }

  if (feedStatus === "UNAVAILABLE") {
    // Live: UNAVAILABLE is by design (no opportunity engine in Live). Other
    // modes: the feed should exist, so point the operator at Control.
    if (mode === "LIVE") {
      return (
        <EmptyState
          title="Opportunity feed unavailable"
          reason="Live mode has no opportunity engine — use the Screeners tab and workspace evidence to investigate instruments."
        />
      );
    }
    const unavailable = resolveSemanticState("research", "UNAVAILABLE");
    return (
      <EmptyState
        title={unavailable.label}
        reason={unavailable.sentence ?? "The opportunity feed is unavailable."}
        action={{ label: "Open Control", href: controlHref(query.data?.next_action) }}
      />
    );
  }

  if (!items.length) {
    return (
      <EmptyState
        title="No opportunities right now"
        reason="An empty queue is valid: nothing has been minted for the current coverage. The mixed live screener on the Screeners tab shows what discovery is seeing."
      />
    );
  }

  return (
    <div className="imp-radar-opportunities" data-testid="imp-radar-opportunities">
      <section className="imp-radar-queue-section" aria-label="Ranked opportunity queue">
        <RadarQueueTable
          items={items}
          selectedStableKey={selectedRow ? stableOpportunityKey(selectedRow) : null}
          readOnly={readOnly}
          onSelectRow={handleSelectRow}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      </section>
      <section className="imp-radar-detail-section" aria-label="Selected opportunity">
        {selectedRow ? (
          <OpportunityDetailCard
            row={selectedRow}
            evidence={evidenceQuery.data}
            evidencePhase={evidencePhase}
            paperAccountId={paperAccountId}
            paperActions={paperActions}
            readOnly={readOnly}
            onExplain={onExplain}
            onInspect={onInspect}
            onOpenWorkspace={onOpenWorkspace}
            onAck={paperActions && !readOnly ? handleAck : undefined}
          />
        ) : (
          <p className="imp-radar-muted">Select a ranked row to open the opportunity detail.</p>
        )}
      </section>
    </div>
  );
}
