import { useEffect, useMemo, useRef, useState } from "react";
import {
  applyIncrementalTick,
  backfillOlderBars,
  createGovernedFeed,
  type GovernedFeedState,
} from "./governedSyntheticFeed";
import { ImpVelaChartAdapter } from "./ImpVelaChartAdapter";
import { sampleImpMarkers } from "./impSemanticAnnotations";
import "../../styles/imp-vela-chart-lab.css";

/**
 * Lane F lab surface — lazy route only. Exercises ImpVelaChartAdapter without
 * replacing workspace lightweight-charts.
 */
export function ImpVelaChartLabPage() {
  const [feed, setFeed] = useState<GovernedFeedState>(() =>
    createGovernedFeed("IMP:ADMITTED:ES", "5m", 120),
  );
  const [liveSim, setLiveSim] = useState(false);
  const tickTimerRef = useRef<number | undefined>(undefined);

  const markers = useMemo(() => sampleImpMarkers(feed.bars), [feed.bars]);

  useEffect(() => {
    if (!liveSim) {
      if (tickTimerRef.current != null) {
        window.clearInterval(tickTimerRef.current);
        tickTimerRef.current = undefined;
      }
      return;
    }
    tickTimerRef.current = window.setInterval(() => {
      setFeed((current) => applyIncrementalTick(current, 8));
    }, 700);
    return () => {
      if (tickTimerRef.current != null) window.clearInterval(tickTimerRef.current);
    };
  }, [liveSim]);

  return (
    <section className="imp-vela-chart-lab" aria-labelledby="imp-vela-lab-title">
      <header className="imp-vela-chart-lab-header">
        <h3 id="imp-vela-lab-title">Vela chart adapter (Lane F)</h3>
        <p>
          IMP-owned bar identity with lazy <code>@luxalgo/vela</code> rendering. No PineTS; workspace
          lightweight-charts unchanged.
        </p>
      </header>
      <div className="imp-vela-chart-lab-controls">
        <button
          type="button"
          aria-pressed={liveSim}
          onClick={() => setLiveSim((on) => !on)}
        >
          {liveSim ? "Stop live tick sim" : "Start live tick sim"}
        </button>
        <button
          type="button"
          onClick={() => setFeed((current) => backfillOlderBars(current, 50))}
        >
          Backfill +50 bars
        </button>
      </div>
      <ImpVelaChartAdapter bars={feed.bars} markers={markers} theme="dark" />
      <p className="imp-vela-chart-lab-meta" role="status">
        {feed.bars.length} governed bars · instrument {feed.instrumentId} · timeframe {feed.timeframe}
      </p>
    </section>
  );
}
