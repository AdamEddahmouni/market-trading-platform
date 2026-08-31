import { useEffect, useState } from "react";
import { useLocation, useNavigate, useNavigationType, useParams } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID } from "../api/client";
import { useInstrumentQuery, useWorkspaceSqueezeQuery } from "../api/hooks";
import { WorkspacePage } from "./WorkspacePage";
import type { Mode } from "./mode-session/types";
import { parsePaperOrderDraft } from "./paper-now/paperOrderDraft";

type Props = {
  mode: Mode;
  paperActionsPermitted: boolean;
  onScrub: (index: number) => void;
  onExplain: (ref: string) => void;
  onInspect: (ref: string) => void;
  onOpenSqueezeHistory?: (symbol: string) => void;
  cursorIndex: number;
  maxIndex: number;
};

export function WorkspaceRoute({
  mode,
  paperActionsPermitted,
  onScrub,
  onExplain,
  onInspect,
  onOpenSqueezeHistory,
  cursorIndex,
  maxIndex,
}: Props) {
  const { symbol } = useParams<{ symbol: string }>();
  const instrumentId = symbol?.toUpperCase() ?? ADMITTED_REPLAY_INSTRUMENT_ID;
  const location = useLocation();
  const navigate = useNavigate();
  const navigationType = useNavigationType();
  const [initialPaperOrderDraft] = useState(() =>
    navigationType === "PUSH" ? parsePaperOrderDraft(location.state, instrumentId) : undefined,
  );
  const replayChartAvailable = instrumentId === ADMITTED_REPLAY_INSTRUMENT_ID;

  useEffect(() => {
    if (location.state !== null) navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  const instrumentQuery = useInstrumentQuery(instrumentId, replayChartAvailable);
  const squeezeQuery = useWorkspaceSqueezeQuery(instrumentId);

  if (replayChartAvailable && instrumentQuery.isLoading) {
    return <div className="app-loading">Loading instrument…</div>;
  }
  if (replayChartAvailable && (instrumentQuery.error || !instrumentQuery.data)) {
    return (
      <div className="app-loading">
        Instrument overview unavailable for {instrumentId}. Ensure the UI API is running.
      </div>
    );
  }

  return (
    <WorkspacePage
      mode={mode}
      paperActionsPermitted={paperActionsPermitted}
      initialPaperOrderDraft={initialPaperOrderDraft}
      instrumentId={instrumentId}
      bars={instrumentQuery.data?.bars ?? []}
      features={instrumentQuery.data?.features ?? []}
      squeeze={squeezeQuery.data ?? null}
      squeezeLoading={squeezeQuery.isLoading}
      replayChartAvailable={replayChartAvailable}
      cursorIndex={cursorIndex}
      maxIndex={
        replayChartAvailable && instrumentQuery.data
          ? Math.max(maxIndex, instrumentQuery.data.bars.length - 1)
          : maxIndex
      }
      onScrub={onScrub}
      onExplain={onExplain}
      onInspect={onInspect}
      onOpenSqueezeHistory={onOpenSqueezeHistory}
    />
  );
}
