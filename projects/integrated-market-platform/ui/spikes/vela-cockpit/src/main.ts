import { applyImpHostTokens } from "./impDarkTheme";
import {
  applyImpMarkers,
  sampleImpMarkers,
} from "./impSemanticAnnotations";
import {
  applyIncrementalTick,
  backfillOlderBars,
  createGovernedFeed,
  type GovernedFeedState,
  velaSeriesFromFeed,
} from "./governedSyntheticFeed";

type VelaChart = {
  ready: () => Promise<void>;
  destroy: () => void;
  resize: () => void;
  setMarket: (next: { bars?: ReturnType<typeof velaSeriesFromFeed> }) => Promise<unknown>;
  setTheme: (theme: "dark" | "light") => unknown;
  on: (event: string, handler: (...args: unknown[]) => void) => () => void;
  addNativeIndicator: (type: string, options?: Record<string, unknown>) => {
    on: (event: string, handler: (...args: unknown[]) => void) => void;
  };
  drawings: {
    supported: boolean;
    add: (type: string, init: Record<string, unknown>) => { id: string };
    remove: (id: string) => void;
  };
  renderer: {
    set: (opts: Record<string, unknown>) => void;
    supports: (feature: string) => boolean;
  };
};

function logLine(container: HTMLElement, text: string): void {
  const p = document.createElement("p");
  p.textContent = text;
  container.prepend(p);
  while (container.childElementCount > 24) {
    container.lastElementChild?.remove();
  }
}

function makeToggleButton(
  label: string,
  getPressed: () => boolean,
  onClick: () => void,
): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = label;
  const sync = () => btn.setAttribute("aria-pressed", getPressed() ? "true" : "false");
  sync();
  btn.addEventListener("click", () => {
    onClick();
    sync();
  });
  return btn;
}

async function boot(): Promise<void> {
  const chartEl = document.getElementById("chart");
  const controls = document.getElementById("imp-spike-controls");
  const log = document.getElementById("imp-spike-log");
  if (!chartEl || !controls || !log) throw new Error("Spike shell missing DOM nodes");

  applyImpHostTokens(chartEl);

  const loadStarted = performance.now();
  const { Vela } = await import("@luxalgo/vela");
  const lazyMs = Math.round(performance.now() - loadStarted);
  logLine(log, `Lazy-loaded @luxalgo/vela in ${lazyMs}ms`);

  let feed: GovernedFeedState = createGovernedFeed("IMP:ADMITTED:ES", "5m", 120);
  const initialSeries = velaSeriesFromFeed(feed);

  const chart = new Vela(chartEl, {
    data: initialSeries,
    timeframe: "5",
    theme: "dark",
    live: false,
  }) as VelaChart;

  await chart.ready();
  logLine(log, `Chart ready with ${feed.bars.length} governed bars`);

  chart.addNativeIndicator("sma", { inputs: { length: 20 }, overlay: true, title: "SMA(20)" });
  chart.addNativeIndicator("rsi", { inputs: { length: 14 }, title: "RSI(14)" });

  const markers = sampleImpMarkers(feed.bars);
  const markerDrawingIds = applyImpMarkers(chart, markers, feed.bars);
  logLine(log, `Applied ${markerDrawingIds.length} IMP semantic drawing projections`);

  let liveSim = false;
  let tickTimer: number | undefined;
  let markerIds = markerDrawingIds;

  const pushFeedToChart = async (reason: string) => {
    await chart.setMarket({ bars: velaSeriesFromFeed(feed) });
    logLine(log, `${reason} → ${feed.bars.length} bars`);
  };

  controls.appendChild(
    makeToggleButton("Live tick sim", () => liveSim, () => {
      liveSim = !liveSim;
      if (liveSim) {
        tickTimer = window.setInterval(() => {
          feed = applyIncrementalTick(feed, 8);
          void pushFeedToChart("Incremental tick");
        }, 700);
        logLine(log, "Live tick simulation ON (governed synthetic only)");
      } else if (tickTimer) {
        window.clearInterval(tickTimer);
        tickTimer = undefined;
        logLine(log, "Live tick simulation OFF");
      }
    }),
  );

  const backfillBtn = document.createElement("button");
  backfillBtn.type = "button";
  backfillBtn.textContent = "Backfill +50 bars";
  backfillBtn.addEventListener("click", () => {
    feed = backfillOlderBars(feed, 50);
    void pushFeedToChart("History backfill");
  });
  controls.appendChild(backfillBtn);

  const densityBtn = document.createElement("button");
  densityBtn.type = "button";
  densityBtn.textContent = "Toggle grid density";
  let dense = false;
  densityBtn.addEventListener("click", () => {
    dense = !dense;
    chart.renderer.set({ gridlines: true, crosshair: true, barSpacing: dense ? 4 : 8 });
    logLine(log, `Renderer density: barSpacing=${dense ? 4 : 8}`);
  });
  controls.appendChild(densityBtn);

  const themeBtn = document.createElement("button");
  themeBtn.type = "button";
  themeBtn.textContent = "Flip theme";
  let dark = true;
  themeBtn.addEventListener("click", () => {
    dark = !dark;
    chart.setTheme(dark ? "dark" : "light");
    logLine(log, `Theme → ${dark ? "dark" : "light"} (IMP host tokens unchanged)`);
  });
  controls.appendChild(themeBtn);

  chart.on("bar", () => {
    logLine(log, "Vela bar event (forming / append)");
  });

  const ro = new ResizeObserver(() => {
    chart.resize();
  });
  ro.observe(chartEl);

  window.addEventListener("beforeunload", () => {
    ro.disconnect();
    if (tickTimer) window.clearInterval(tickTimer);
    for (const id of markerIds) chart.drawings.remove(id);
    chart.destroy();
  });

  logLine(
    log,
    "Gaps (honest): no IMP bar_id in Vela model; markers via drawings not first-class events; Pine/native catalog only for indicators; multi-pane workspace not wired.",
  );
}

boot().catch((error) => {
  console.error(error);
  const log = document.getElementById("imp-spike-log");
  if (log) logLine(log, `Spike failed: ${error instanceof Error ? error.message : String(error)}`);
});
