export type ReplayProgress = {
  cursorIndex: number;
  ordinal: number;
  eventCount: number;
  percent: number;
  hasPrevious: boolean;
  hasNext: boolean;
};

export function deriveReplayProgress(cursorIndex: number, eventCount: number | undefined): ReplayProgress | null {
  if (!Number.isInteger(cursorIndex) || eventCount === undefined || !Number.isInteger(eventCount) || eventCount < 0) {
    return null;
  }
  if (eventCount === 0) {
    return { cursorIndex: 0, ordinal: 0, eventCount: 0, percent: 0, hasPrevious: false, hasNext: false };
  }
  const boundedCursor = Math.min(Math.max(cursorIndex, 0), eventCount - 1);
  const ordinal = boundedCursor + 1;
  return {
    cursorIndex: boundedCursor,
    ordinal,
    eventCount,
    percent: Math.round((ordinal / eventCount) * 100),
    hasPrevious: boundedCursor > 0,
    hasNext: boundedCursor < eventCount - 1,
  };
}

type Props = {
  cursorIndex: number;
  eventCount?: number;
  state: "loading" | "ready" | "error";
  scrubState: "idle" | "pending" | "error";
  onScrub: (index: number) => void;
  onOpenTimeline: () => void;
};

export function DemoReplayOverview({ cursorIndex, eventCount, state, scrubState, onScrub, onOpenTimeline }: Props) {
  const progress = state === "ready" ? deriveReplayProgress(cursorIndex, eventCount) : null;
  const controlsDisabled = scrubState === "pending" || !progress || progress.eventCount === 0;

  return (
    <section className="demo-now-panel demo-replay-panel" aria-labelledby="demo-replay-title">
      <div className="demo-panel-heading">
        <div>
          <p className="demo-eyebrow">Historical scenario</p>
          <h2 id="demo-replay-title">Replay overview</h2>
        </div>
        <span className="demo-state-badge">Read-only replay</span>
      </div>
      <div className="demo-scenario-card">
        <strong>BIYA admitted replay</strong>
        <span>Known historical sequence · No execution risk</span>
        <span className="demo-scenario-note">Scenario switching is not available in this Demo build.</span>
      </div>
      {state === "loading" ? <p role="status">Loading replay status…</p> : null}
      {state === "error" || (state === "ready" && !progress) ? (
        <p className="unavailable">Replay status unavailable.</p>
      ) : null}
      {progress ? (
        <>
          <div className="demo-replay-progress-copy">
            <strong>{progress.eventCount === 0 ? "0 events" : `Event ${progress.ordinal} of ${progress.eventCount}`}</strong>
            <span>{progress.percent}% observed</span>
          </div>
          {progress.eventCount > 0 ? (
            <div
              className="demo-replay-progress"
              role="progressbar"
              aria-label="Replay progress"
              aria-valuemin={1}
              aria-valuemax={progress.eventCount}
              aria-valuenow={progress.ordinal}
              aria-valuetext={`Event ${progress.ordinal} of ${progress.eventCount}`}
            >
              <span style={{ width: `${progress.percent}%` }} />
            </div>
          ) : null}
          <div className="demo-replay-actions">
            <button
              type="button"
              disabled={controlsDisabled || !progress.hasPrevious}
              onClick={() => onScrub(progress.cursorIndex - 1)}
            >
              Previous
            </button>
            <button
              className="primary"
              type="button"
              disabled={controlsDisabled || !progress.hasNext}
              onClick={() => onScrub(progress.cursorIndex + 1)}
            >
              Next event
            </button>
            <button type="button" onClick={onOpenTimeline}>
              Open full timeline
            </button>
          </div>
        </>
      ) : null}
      {scrubState === "pending" ? <p role="status">Moving to the requested replay event…</p> : null}
      {scrubState === "error" ? (
        <p role="status">Replay could not move. The last confirmed event remains visible.</p>
      ) : null}
    </section>
  );
}
