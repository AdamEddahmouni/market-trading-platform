import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
import { queryKeys } from "../../api/hooks";
import {
  getTradeReviewsForOpportunity,
} from "../../api/tradeReviewClient";
import { BP_MD } from "../../lib/breakpoints";
import { useMediaQuery } from "../../lib/useMediaQuery";
import type { TradeReviewAckPhase } from "../imp-product/TradeReviewLearningPanel";
import { OpportunityFeedState } from "../opportunity/OpportunityFeedState";
import {
  canAckOpportunity,
  stableOpportunityKey,
} from "../opportunity/opportunityPresentation";
import type { Mode } from "../mode-session/types";
import {
  DecisionClosureBanner,
  type DecisionClosureRecord,
} from "./DecisionClosureBanner";
import { OpportunityDetailCard } from "./OpportunityDetailCard";
import { RadarDetailSheet } from "./RadarDetailSheet";
import { RadarFeedTruthStrip } from "./RadarFeedTruthStrip";
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

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

/**
 * Radar Opportunities tab: feed truth strip, ranked queue, and selected
 * opportunity detail. Keyboard: ↑/↓ or j/k move selection (preserving
 * context), w/d post watch/dismiss via the existing ack API when paper-gated,
 * Escape closes the narrow detail sheet.
 *
 * After Watch/Dismiss succeeds, deliberately reconciles opportunities summary
 * and trade-review queries so durable DecisionTrace/TradeReview appears without
 * manual refresh. Does not fabricate review rows in the client.
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
  const queryClient = useQueryClient();
  const query = useOpportunitiesSummaryQuery(true);
  const ackMutation = useOpportunityAckMutation();
  const state = query.isLoading ? "loading" : query.isError || !query.data ? "error" : "ready";
  const items = query.data?.items ?? [];
  const feedStatus = query.data?.feed_status;
  const sheetLayout = useMediaQuery(`(max-width: ${BP_MD}px)`);
  const [selectedKey, setSelectedKey] = useState<string | null>(initialSelectedKey);
  const [sheetOpen, setSheetOpen] = useState(() => Boolean(initialSelectedKey) && sheetLayout);
  const [ackPhase, setAckPhase] = useState<TradeReviewAckPhase>("idle");
  const [closure, setClosure] = useState<DecisionClosureRecord | null>(null);
  const [activeAckKey, setActiveAckKey] = useState<string | null>(null);
  const ackInFlightRef = useRef(false);
  const queueRegionRef = useRef<HTMLDivElement | null>(null);

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

  // When Dismiss removes the selected row, fall through without keeping a ghost
  // in the active queue; selection resolves to items[0] via selectedRow memo.
  useEffect(() => {
    if (!selectedKey || !items.length) return;
    const stillPresent = items.some((row) => stableOpportunityKey(row) === selectedKey);
    if (!stillPresent && selectedRow) {
      setSelectedKey(stableOpportunityKey(selectedRow));
    }
  }, [items, selectedKey, selectedRow]);

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

  useEffect(() => {
    if (!sheetLayout) setSheetOpen(false);
  }, [sheetLayout]);

  const reconcileTradeReviews = useCallback(
    async (opportunityId: string, expectedReviewId?: string) => {
      const result = await queryClient.fetchQuery({
        queryKey: queryKeys.tradeReviews(opportunityId),
        queryFn: () => getTradeReviewsForOpportunity(opportunityId),
      });
      const found = (result.items ?? []).some(
        (item) => !expectedReviewId || item.review_id === expectedReviewId,
      );
      if (expectedReviewId && !found) {
        setAckPhase("reconciliation_failed");
        return false;
      }
      setAckPhase("completed");
      return true;
    },
    [queryClient],
  );

  const handleAck = useCallback(
    async (row: OpportunityReviewRow, action: OpportunityAckAction) => {
      if (ackInFlightRef.current) {
        return;
      }
      ackInFlightRef.current = true;
      const rowId = row.opportunity_id || row.summary_id;
      const key = stableOpportunityKey(row);
      setActiveAckKey(key);
      setAckPhase("submitting");
      setClosure(null);
      let data;
      try {
        data = await ackMutation.mutateAsync({ rowId, action });
      } catch {
        setAckPhase("failed");
        setClosure(null);
        ackInFlightRef.current = false;
        return;
      }
      setAckPhase("synchronizing");
      const opportunityId = String(data.opportunity_id || row.opportunity_id || row.summary_id);
      const leftActiveQueue = action === "dismiss";
      const nextClosure: DecisionClosureRecord = {
        opportunityId,
        summaryId: data.summary_id || row.summary_id,
        instrumentId: row.instrument_id ?? null,
        headline: row.headline,
        action,
        tradeReviewId: data.trade_review_id,
        decisionTraceMode: data.decision_trace_mode,
        leftActiveQueue,
      };
      setClosure(nextClosure);
      try {
        await reconcileTradeReviews(opportunityId, data.trade_review_id);
      } catch {
        setAckPhase("reconciliation_failed");
      } finally {
        ackInFlightRef.current = false;
      }
    },
    [ackMutation, reconcileTradeReviews],
  );

  const handleRetryReconcile = useCallback(() => {
    if (!closure) return;
    setAckPhase("synchronizing");
    void reconcileTradeReviews(closure.opportunityId, closure.tradeReviewId);
  }, [closure, reconcileTradeReviews]);

  const acksEnabled = Boolean(paperActions && !readOnly && paperAccountId);
  const selectedAckPhase =
    selectedRow && activeAckKey === stableOpportunityKey(selectedRow) ? ackPhase : "idle";
  const selectedExpectedReviewId =
    selectedRow &&
    closure &&
    (closure.opportunityId === (selectedRow.opportunity_id || selectedRow.summary_id) ||
      closure.summaryId === selectedRow.summary_id)
      ? closure.tradeReviewId ?? null
      : null;
  // Show dismiss closure banner whenever last action left the active queue so
  // durable decision evidence remains inspectable without keeping a ghost row.
  const showPostDismissBanner = Boolean(closure?.leftActiveQueue);

  const moveSelection = useCallback(
    (delta: number) => {
      if (!items.length) return;
      const currentKey = selectedRow ? stableOpportunityKey(selectedRow) : null;
      const currentIndex = currentKey
        ? items.findIndex((row) => stableOpportunityKey(row) === currentKey)
        : 0;
      const nextIndex = Math.min(items.length - 1, Math.max(0, (currentIndex < 0 ? 0 : currentIndex) + delta));
      const next = items[nextIndex];
      if (!next) return;
      setSelectedKey(stableOpportunityKey(next));
      if (sheetLayout) setSheetOpen(true);
      const el = queueRegionRef.current?.querySelector(
        `[data-stable-key="${stableOpportunityKey(next).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"]`,
      );
      if (el instanceof HTMLElement) el.focus();
    },
    [items, selectedRow, sheetLayout],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;
      if (event.key === "Escape" && sheetLayout && sheetOpen) {
        event.preventDefault();
        setSheetOpen(false);
        return;
      }
      if (!items.length) return;

      if (event.key === "ArrowDown" || event.key === "j") {
        event.preventDefault();
        moveSelection(1);
        return;
      }
      if (event.key === "ArrowUp" || event.key === "k") {
        event.preventDefault();
        moveSelection(-1);
        return;
      }
      if (
        !selectedRow ||
        !acksEnabled ||
        !canAckOpportunity(selectedRow) ||
        ackPhase === "submitting" ||
        ackPhase === "synchronizing"
      ) {
        return;
      }
      if (event.key === "w" || event.key === "W") {
        event.preventDefault();
        void handleAck(selectedRow, "watch");
        return;
      }
      if (event.key === "d" || event.key === "D") {
        event.preventDefault();
        void handleAck(selectedRow, "dismiss");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    acksEnabled,
    ackPhase,
    handleAck,
    items.length,
    moveSelection,
    selectedRow,
    sheetLayout,
    sheetOpen,
  ]);

  const detailCard = selectedRow ? (
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
      ackPhase={selectedAckPhase}
      expectedReviewId={selectedExpectedReviewId}
      onRetryReconcile={
        selectedAckPhase === "reconciliation_failed" || selectedExpectedReviewId
          ? handleRetryReconcile
          : undefined
      }
      onExplain={onExplain}
      onInspect={onInspect}
      onOpenWorkspace={onOpenWorkspace}
      onAck={acksEnabled ? (row, action) => void handleAck(row, action) : undefined}
    />
  ) : null;

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
        <div className="imp-radar-opportunities-main" ref={queueRegionRef}>
          <RadarFeedTruthStrip
            feedStatus={feedStatus}
            itemCount={items.length}
            feed={query.data?.as_of_context ?? null}
            qualityState={query.data?.quality_summary?.state}
          />
          <section className="imp-radar-queue-section" aria-label="Ranked opportunity queue">
            <RadarQueueTable
              items={items}
              selectedStableKey={selectedRow ? stableOpportunityKey(selectedRow) : null}
              selectedEvidence={evidenceQuery.data ?? null}
              feed={query.data?.as_of_context ?? null}
              readOnly={readOnly}
              paperActions={paperActions}
              paperAccountId={paperAccountId}
              onSelectRow={handleSelectRow}
              onExplain={onExplain}
              onInspect={onInspect}
              onOpenWorkspace={onOpenWorkspace}
              onAck={acksEnabled ? (row, action) => void handleAck(row, action) : undefined}
              acksBusy={ackPhase === "submitting" || ackPhase === "synchronizing"}
            />
          </section>
        </div>
        {!sheetLayout ? (
          <section className="imp-radar-detail-section" aria-label="Selected opportunity">
            {showPostDismissBanner && closure ? (
              <DecisionClosureBanner
                closure={closure}
                phase={ackPhase}
                onRetryReconcile={
                  ackPhase === "reconciliation_failed" ? handleRetryReconcile : undefined
                }
                onDismissBanner={() => setClosure(null)}
              />
            ) : null}
            {detailCard ?? (
              <p className="imp-radar-muted">Select a ranked row to open the opportunity detail.</p>
            )}
          </section>
        ) : null}
      </div>
      {sheetLayout ? (
        <RadarDetailSheet open={sheetOpen && Boolean(selectedRow)} onClose={() => setSheetOpen(false)}>
          {showPostDismissBanner && closure ? (
            <DecisionClosureBanner
              closure={closure}
              phase={ackPhase}
              onRetryReconcile={
                ackPhase === "reconciliation_failed" ? handleRetryReconcile : undefined
              }
              onDismissBanner={() => setClosure(null)}
            />
          ) : null}
          {detailCard}
        </RadarDetailSheet>
      ) : null}
    </OpportunityFeedState>
  );
}
