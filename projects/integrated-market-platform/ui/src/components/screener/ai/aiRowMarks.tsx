import { useEffect, useMemo, useState } from "react";
import { aiScopeKey, type AiScreenerRun, type AiScreenerScope } from "../../../api/screenerAi";
import { etClock } from "../panels/shared";

export type AiRowMarks = { ranks: Map<string, number>; intake: Set<string>; expired: boolean; finishedAt: string | null };

/**
 * Which Screener rows the latest AI Screener pass was shown and which it selected. Marks exist only for a finished
 * pass that answered the Screener query now on screen; a pass for another query marks nothing.
 */
export function useAiRowMarks(latest: AiScreenerRun | null | undefined, scope: AiScreenerScope): AiRowMarks | null {
  const summary = latest?.state === "COMPLETED" ? latest.summary : null;
  const usable = summary && (summary.state === "CURRENT" || summary.state === "NO_GROUNDED_CANDIDATES") && aiScopeKey(latest!.scope) === aiScopeKey(scope) ? summary : null;
  const validUntil = usable?.valid_until ? Date.parse(usable.valid_until) : null;
  const [expired, setExpired] = useState(() => validUntil !== null && validUntil <= Date.now());
  // One timer at the expiry instant, not a ticking clock: the table re-renders once when evidence expires.
  useEffect(() => {
    if (validUntil === null) { setExpired(false); return; }
    const left = validUntil - Date.now();
    setExpired(left <= 0);
    if (left <= 0) return;
    const timer = window.setTimeout(() => setExpired(true), Math.min(left, 2_147_000_000));
    return () => window.clearTimeout(timer);
  }, [validUntil]);
  return useMemo(() => usable ? { ranks: new Map(usable.selected.map((pick) => [pick.instrument_id, pick.rank])), intake: new Set(usable.intake ?? []),
    expired, finishedAt: latest!.finished_at } : null,
  // The run id identifies the summary; its contents never change once a run has finished.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [latest?.run_id, Boolean(usable), expired]);
}

/** The mark beside a row's symbol: the model's rank, or that the row was shown to the model and not selected. */
export function AiRowBadge({ marks, instrumentId }: { marks: AiRowMarks | null; instrumentId: string }) {
  if (!marks) return null;
  const rank = marks.ranks.get(instrumentId);
  const pass = `pass finished ${etClock(marks.finishedAt)}`;
  if (rank !== undefined) return <span className={`ai-row-badge${marks.expired ? " expired" : ""}`}
    title={`Selected by the AI Screener, rank ${rank} · ${pass}${marks.expired ? " · its evidence has expired: rerun before relying on it" : ""}. A candidate for review, not an instruction to trade.`}>AI {rank}</span>;
  if (marks.intake.has(instrumentId)) return <span className={`ai-row-seen${marks.expired ? " expired" : ""}`}
    title={`Shown to the AI Screener and not selected · ${pass}${marks.expired ? " · evidence expired" : ""}.`}>AI</span>;
  return null;
}
