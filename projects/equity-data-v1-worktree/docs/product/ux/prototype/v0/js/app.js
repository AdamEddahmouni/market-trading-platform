import {
  AS_OF_DISPLAY,
  REGIME,
  ATTENTION_ITEMS,
  WATCHLIST_PULSE,
  INSTRUMENTS,
  COMMAND_ITEMS,
  INSPECTOR_TABS,
  REPLAY_SESSION,
  REPLAY_SNAPSHOTS,
  SYSTEM_QUALITY,
  CVD_DERIVATION,
  EXPLORE_DATA,
} from "./mock-data.js";

const state = {
  route: "#/now",
  mode: "LIVE",
  replayTime: REPLAY_SESSION.defaultReplay,
  inspectorOpen: false,
  inspectorTab: "SUMMARY",
  inspectorTarget: null,
  drawerOpen: false,
  drawerContent: null,
  drawerMode: "explain",
  drawerSymbol: null,
  drawerAttention: null,
  qualityPanelOpen: false,
  qualitySymbol: null,
  replayPlaying: false,
  commandOpen: false,
  attentionPage: 0,
  attentionPageSize: 10,
  cockpitTab: "overview",
  storyExpanded: false,
  focusedAttentionId: null,
  lastInspectTarget: null,
  exploreScreen: EXPLORE_DATA.defaultScreen,
  exploreWhySymbol: null,
  shortcutsOpen: false,
};

const PAGE_SIZE = 10;
const MOBILE_MQ = "(max-width: 900px)";
const REPLAY_PLAY_MS = 1400;
let replayTimer = null;

/** Keyboard shortcut reference — V0.6 overlay content. */
const SHORTCUT_SECTIONS = [
  {
    title: "Global",
    items: [
      { keys: "Ctrl / ⌘ K", action: "Open command palette", status: "active" },
      { keys: "?", action: "Show keyboard shortcuts", status: "active" },
      { keys: "Esc", action: "Close topmost overlay (shortcuts, palette, quality, drawer, inspector)", status: "active" },
    ],
  },
  {
    title: "Explainability",
    items: [
      { keys: "E", action: "Explain focused attention card (or NVDA default)", status: "active" },
      { keys: "I", action: "Open Evidence Inspector (last target or default)", status: "active" },
      { keys: "Shift + click", action: "Alignment row → Inspector DERIVATION tab", status: "active" },
    ],
  },
  {
    title: "Navigation (proposed)",
    items: [
      { keys: "J / K", action: "Next / previous attention item", status: "planned" },
      { keys: "1 – 9", action: "Switch workspace module tab", status: "planned" },
      { keys: "A", action: "Toggle AI sidecar", status: "planned" },
      { keys: "C", action: "Focus chart", status: "planned" },
    ],
  },
  {
    title: "Replay (proposed)",
    items: [
      { keys: "Space", action: "Play / pause replay scrubber", status: "planned" },
      { keys: ", / .", action: "Step replay backward / forward", status: "planned" },
    ],
  },
];

function isMobileViewport() {
  return window.matchMedia(MOBILE_MQ).matches;
}

function isTextInputFocused() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
}

function openShortcutsOverlay() {
  state.shortcutsOpen = true;
  render();
}

function closeShortcutsOverlay() {
  state.shortcutsOpen = false;
  render();
}

function renderTimelineBody(target) {
  const events = target.timeline;
  if (!events?.length) {
    return `<p style="color:var(--text-muted)">No timeline events in fixture.</p>`;
  }
  return `<div class="timeline-list">${events
    .map((e) => {
      const cls = [
        "timeline-event",
        e.changed ? "timeline-event--changed" : "",
        e.type === "milestone" ? "timeline-event--milestone" : "",
        e.type === "quality" ? "timeline-event--quality" : "",
      ]
        .filter(Boolean)
        .join(" ");
      const stateBadge = e.state ? `<span class="badge badge--partial">${e.state}</span>` : "";
      const mockBadge = e.mock ? '<span class="badge badge--partial">MOCK</span>' : "";
      return `<div class="${cls}"><span class="timeline-event__time">${e.time}</span><span class="timeline-event__label">${e.label}</span>${stateBadge}${mockBadge}</div>`;
    })
    .join("")}</div>`;
}

function renderDerivationBody(target) {
  const d = target.derivation;
  if (!d) {
    if (target.epistemicClass === "OBSERVED") {
      return `<p style="color:var(--text-muted)">Not applicable — <strong>OBSERVED</strong> value with no derivation chain.</p>`;
    }
    return `<p style="color:var(--text-muted)">No derivation metadata in fixture.</p>`;
  }

  const inputs = (d.inputs || [])
    .map(
      (inp) =>
        `<tr><td>${inp.name}</td><td><code>${inp.value}</code></td><td>${qualityBadge(inp.quality)}</td></tr>`
    )
    .join("");

  const trades = d.inputTrades?.length
    ? `<div class="inspector-field" style="margin-top:14px">
        <div class="inspector-field__label">Input trades</div>
        <table class="derivation-table">
          <thead><tr><th>ID</th><th>Time</th><th>Price</th><th>Size</th><th>Side</th></tr></thead>
          <tbody>${d.inputTrades
            .map(
              (t) =>
                `<tr><td><code>${t.id}</code></td><td>${t.time}</td><td>$${t.price}</td><td>${t.size}</td><td>${t.side}</td></tr>`
            )
            .join("")}</tbody>
        </table>
        <button type="button" class="btn btn--sm" id="derivation-to-provenance" style="margin-top:10px">View provenance</button>
      </div>`
    : "";

  const note = d.qualityNote
    ? `<div class="inspector-field"><div class="inspector-field__label">Quality note</div><p style="margin:0;color:var(--warning)">${d.qualityNote}</p></div>`
    : "";

  return `
    <div class="inspector-field"><div class="inspector-field__label">Method</div><code>${d.method}</code> <span class="badge badge--partial">${d.version}</span></div>
    <div class="inspector-field"><div class="inspector-field__label">Formula</div><code style="font-size:12px">${d.formula}</code></div>
    <div class="inspector-field"><div class="inspector-field__label">Inputs</div>
      <table class="derivation-table"><thead><tr><th>Input</th><th>Value</th><th>Quality</th></tr></thead><tbody>${inputs}</tbody></table>
    </div>
    ${note}
    ${trades}
  `;
}

function renderQualityBody(target) {
  const q = target.quality;
  if (!q) {
    return `<p style="color:var(--text-muted)">No quality metadata on this object. Open system quality panel from context bar.</p>`;
  }
  const symbols = q.affectedSymbols?.length
    ? `<div class="inspector-field"><div class="inspector-field__label">Affected symbols</div>${q.affectedSymbols.join(", ")}</div>`
    : "";
  return `
    <div class="inspector-field"><div class="inspector-field__label">State</div>${qualityBadge(q.state)}</div>
    ${q.gapType ? `<div class="inspector-field"><div class="inspector-field__label">Gap type</div>${q.gapType}</div>` : ""}
    ${q.timeRange ? `<div class="inspector-field"><div class="inspector-field__label">Time range</div><span style="font-family:var(--font-mono)">${q.timeRange}</span></div>` : ""}
    ${symbols}
    ${q.reason ? `<div class="inspector-field"><div class="inspector-field__label">Reason</div>${q.reason}</div>` : ""}
    ${q.affectedInputs ? `<div class="inspector-field"><div class="inspector-field__label">Affected inputs</div>${q.affectedInputs.join(", ")}</div>` : ""}
    ${q.observedLayer ? `<div class="inspector-field"><div class="inspector-field__label">OBSERVED layer</div>${q.observedLayer}</div>` : ""}
    ${q.freshness ? `<div class="inspector-field"><div class="inspector-field__label">Freshness</div>${q.freshness}</div>` : ""}
    ${q.corrections ? `<div class="inspector-field"><div class="inspector-field__label">Corrections</div>${q.corrections}</div>` : ""}
  `;
}

function renderUsedByBody(target) {
  const consumers = target.usedBy;
  if (!consumers?.length) {
    return `<p style="color:var(--text-muted)">No downstream consumers recorded for this object in the fixture.</p>`;
  }
  const typeLabel = (t) => {
    const map = { feature: "Feature", screener: "Screener", watchlist: "Watchlist", alert: "Alert", strategy: "Strategy" };
    return map[t] || t;
  };
  const rows = consumers
    .map((c) => {
      const mockBadge = c.mock ? ' <span class="badge badge--partial">MOCK</span>' : "";
      const routeBtn = c.route
        ? `<button type="button" class="btn btn--sm btn--ghost used-by-row__nav" data-used-by-route="${c.route}">Open</button>`
        : "";
      return `<div class="used-by-row">
        <div class="used-by-row__main">
          <span class="used-by-row__type">${typeLabel(c.type)}</span>
          <strong class="used-by-row__name">${c.name}</strong>
          <span class="used-by-row__detail">${c.detail}${mockBadge}</span>
        </div>
        ${routeBtn}
      </div>`;
    })
    .join("");
  return `<div class="used-by-list">${rows}</div>`;
}

function renderQualityPanel() {
  if (!state.qualityPanelOpen) return "";
  const q = SYSTEM_QUALITY;

  if (state.qualitySymbol && q.symbolDrilldown[state.qualitySymbol]) {
    const sym = state.qualitySymbol;
    const drill = q.symbolDrilldown[sym];
    const modules = drill.modules
      .map(
        (m) =>
          `<tr><td>${m.name}</td><td>${epistemicBadge(m.epistemic)}</td><td>${qualityBadge(m.quality)}</td><td style="color:var(--text-secondary);font-size:12px">${m.note}</td></tr>`
      )
      .join("");
    return `
      <div class="quality-panel-overlay" id="quality-panel-overlay" role="dialog" aria-modal="true" aria-label="Symbol quality detail">
        <div class="quality-panel">
          <div class="quality-panel__header">
            <div>
              <button type="button" class="btn btn--sm btn--ghost" id="quality-drill-back">← Back</button>
              <h2>${sym} quality</h2>
              <p class="quality-panel__subtitle">Symbol drill-down · gap ${q.timeRange.start} – ${q.timeRange.end}</p>
            </div>
            <button type="button" class="btn btn--sm btn--ghost" id="close-quality-panel" aria-label="Close">✕</button>
          </div>
          <div class="quality-panel__summary">
            ${qualityBadge(q.state)}
            <span style="margin-left:8px;color:var(--text-secondary);font-size:13px">${drill.summary}</span>
          </div>
          <div class="quality-panel__section">
            <h3>Per-module quality</h3>
            <table class="derivation-table"><thead><tr><th>Module</th><th>Class</th><th>Quality</th><th>Note</th></tr></thead><tbody>${modules}</tbody></table>
          </div>
          <div class="quality-panel__actions">
            <button type="button" class="btn btn--primary" id="quality-open-cockpit" data-symbol="${sym}">Open ${sym} cockpit</button>
            <button type="button" class="btn btn--ghost" id="close-quality-panel-btn">Dismiss</button>
          </div>
        </div>
      </div>
    `;
  }

  const modules = q.modules
    .map(
      (m) =>
        `<tr><td>${m.name}</td><td>${epistemicBadge(m.epistemic)}</td><td>${qualityBadge(m.quality)}</td><td style="color:var(--text-secondary);font-size:12px">${m.note}</td></tr>`
    )
    .join("");
  const trust = q.trustGuidance
    .map(
      (t) =>
        `<div class="trust-row"><span class="trust-row__layer">${t.layer}</span>${qualityBadge(t.trust)}<span class="trust-row__detail">${t.detail}</span></div>`
    )
    .join("");

  return `
    <div class="quality-panel-overlay" id="quality-panel-overlay" role="dialog" aria-modal="true" aria-label="Data quality detail">
      <div class="quality-panel">
        <div class="quality-panel__header">
          <div>
            <h2>Data quality</h2>
            <p class="quality-panel__subtitle">${q.gapLabel} · ${q.timeRange.start} – ${q.timeRange.end}</p>
          </div>
          <button type="button" class="btn btn--sm btn--ghost" id="close-quality-panel" aria-label="Close">✕</button>
        </div>
        <div class="quality-panel__summary">
          ${qualityBadge(q.state)}
          <span style="margin-left:8px;color:var(--text-secondary);font-size:13px">${q.summary}</span>
        </div>
        <div class="quality-panel__section">
          <h3>Affected symbols</h3>
          <div class="quality-panel__symbols">
            ${q.affectedSymbols
              .map(
                (s) =>
                  `<button type="button" class="btn btn--sm quality-symbol-btn" data-quality-symbol="${s}">${s} →</button>`
              )
              .join("")}
          </div>
          <p style="margin-top:8px;color:var(--text-muted);font-size:12px">${q.timeRange.durationSec}s gap · click symbol for drill-down</p>
        </div>
        <div class="quality-panel__section">
          <h3>Per-module quality</h3>
          <table class="derivation-table"><thead><tr><th>Module</th><th>Class</th><th>Quality</th><th>Note</th></tr></thead><tbody>${modules}</tbody></table>
        </div>
        <div class="quality-panel__section">
          <h3>What you can still trust</h3>
          <div class="trust-guidance">${trust}</div>
        </div>
        <div class="quality-panel__actions">
          <button type="button" class="btn btn--primary" id="quality-to-inspector">Open in Inspector</button>
          <button type="button" class="btn btn--ghost" id="close-quality-panel-btn">Dismiss</button>
        </div>
      </div>
    </div>
  `;
}

function $(sel, root = document) {
  return root.querySelector(sel);
}

function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function epistemicBadge(cls) {
  const map = { OBSERVED: "obs", DERIVED: "der", INFERRED: "inf", MODEL: "mdl" };
  const key = map[cls] || "obs";
  const short = cls === "OBSERVED" ? "OBS" : cls === "DERIVED" ? "DER" : cls === "INFERRED" ? "INF" : cls.slice(0, 3);
  return `<span class="badge badge--${key}">${short}</span>`;
}

function qualityBadge(q) {
  const cls = q === "GOOD" ? "good" : q === "PARTIAL" ? "partial" : "unavailable";
  return `<span class="badge badge--${cls}">${q}</span>`;
}

function formatChange(pct) {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function getEffectiveAsOf() {
  if (state.mode === "REPLAY") {
    const snap = REPLAY_SNAPSHOTS[state.replayTime] || REPLAY_SNAPSHOTS[REPLAY_SESSION.defaultReplay];
    return snap?.asOfDisplay || `${state.replayTime}.000 ET`;
  }
  return AS_OF_DISPLAY;
}

function getReplaySnapshot() {
  if (state.mode !== "REPLAY") return null;
  return REPLAY_SNAPSHOTS[state.replayTime] || REPLAY_SNAPSHOTS[REPLAY_SESSION.defaultReplay];
}

function timeToMinutes(t) {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function filterStoryByReplay(events) {
  if (state.mode !== "REPLAY") return events;
  const snap = getReplaySnapshot();
  if (!snap?.marketStoryCutoff) return events;
  const cutoff = timeToMinutes(snap.marketStoryCutoff);
  return events.filter((e) => timeToMinutes(e.time) <= cutoff);
}

function enterReplay(time = REPLAY_SESSION.defaultReplay, navigateToNvda = true) {
  stopReplayPlay();
  state.mode = "REPLAY";
  state.replayTime = time;
  if (navigateToNvda) navigate("#/instrument/NVDA");
  else render();
}

function exitReplay() {
  stopReplayPlay();
  state.mode = "LIVE";
  state.replayTime = REPLAY_SESSION.defaultReplay;
  render();
}

function stopReplayPlay() {
  state.replayPlaying = false;
  if (replayTimer) {
    clearInterval(replayTimer);
    replayTimer = null;
  }
}

function toggleReplayPlay() {
  if (state.replayPlaying) {
    stopReplayPlay();
    render();
    return;
  }
  state.replayPlaying = true;
  replayTimer = setInterval(() => {
    const events = REPLAY_SESSION.events;
    const idx = events.findIndex((e) => e.time.startsWith(state.replayTime.slice(0, 5)));
    if (idx < events.length - 1) {
      state.replayTime = events[idx + 1].time;
      render();
    } else {
      stopReplayPlay();
      render();
    }
  }, REPLAY_PLAY_MS);
  render();
}

function parseRoute() {
  const hash = location.hash || "#/now";
  const prevRoute = state.route;
  state.route = hash;
  if (prevRoute !== hash) {
    state.qualityPanelOpen = false;
    state.qualitySymbol = null;
  }
  handleAlertDeepLink();
  return hash;
}

function handleAlertDeepLink() {
  const alertMatch = state.route.match(/#\/now\/alert\/([\w-]+)/);
  if (!alertMatch) {
    state.lastAlertId = null;
    return;
  }
  const id = alertMatch[1];
  if (state.lastAlertId === id) return;
  const att = ATTENTION_ITEMS.find((a) => a.id === id);
  if (att) {
    state.lastAlertId = id;
    openMobileAlert(att, false);
  }
}

function openQualityPanel() {
  state.qualityPanelOpen = true;
  state.qualitySymbol = null;
  render();
}

function closeQualityPanel() {
  state.qualityPanelOpen = false;
  state.qualitySymbol = null;
  render();
}

function openMobileAlert(att, shouldRender = true) {
  state.drawerOpen = true;
  state.drawerMode = "mobile";
  state.drawerContent = att.explanation;
  state.drawerSymbol = att.symbol !== "SYSTEM" ? att.symbol : null;
  state.drawerAttention = att;
  state._drawerInspect = att.inspect;
  if (shouldRender) render();
}

function navigate(target) {
  location.hash = target.replace(/^#/, "");
}

function renderSparkline(values) {
  const w = 400;
  const h = 80;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline fill="none" stroke="#5b8def" stroke-width="2" points="${pts}"/></svg>`;
}

function renderNow() {
  const pinned = ATTENTION_ITEMS.filter((a) => a.tier === 1);
  const rest = ATTENTION_ITEMS.filter((a) => a.tier !== 1);
  const pageStart = state.attentionPage * PAGE_SIZE;
  const pageItems = rest.slice(pageStart, pageStart + PAGE_SIZE);
  const displayItems = [...pinned, ...pageItems];
  const hasMore = pageStart + PAGE_SIZE < rest.length;

  const cards = displayItems
    .map((item) => {
      const transitionBtn = item.transitionDetail
        ? `<button type="button" class="btn btn--sm btn--ghost" data-action="transition" data-id="${item.id}">Explain transition</button>`
        : "";
      const actions = `
        <button type="button" class="btn btn--sm btn--ghost" data-action="why" data-id="${item.id}">Why here?</button>
        <button type="button" class="btn btn--sm" data-action="open" data-symbol="${item.symbol}">Open ${item.symbol === "SYSTEM" ? "inspect" : item.symbol}</button>
        <button type="button" class="btn btn--sm btn--ghost" data-action="explain" data-id="${item.id}">Explain</button>
        ${transitionBtn}
      `;
      const unchanged = item.unchanged
        ? `<div class="attention-card__unchanged">Unchanged: ${item.unchanged}</div>`
        : "";
      const tierCls = item.tier === 1 ? " card--tier-1" : "";
      return `
        <article class="card card--attention${tierCls}" tabindex="0" data-attention-id="${item.id}" aria-label="Attention: ${item.symbol}">
          <div class="attention-card__header">
            <div>
              <span class="attention-card__symbol">${item.symbol}</span>
              ${item.mock ? '<span class="badge badge--partial" style="margin-left:6px">MOCK</span>' : ""}
            </div>
            <div class="attention-card__transition">${item.transition} · ${item.ago}</div>
          </div>
          <ul class="attention-card__reasons">${item.reasons.map((r) => `<li>${r}</li>`).join("")}</ul>
          ${unchanged}
          <div class="attention-card__actions">${actions}</div>
        </article>
      `;
    })
    .join("");

  const pulse = WATCHLIST_PULSE.map((w) => {
    const cls = w.change > 0 ? "up" : w.change < 0 ? "down" : "flat";
    return `<span class="watchlist-pulse__item"><strong>${w.symbol}</strong> <span class="${cls}">${formatChange(w.change)}</span></span>`;
  }).join("");

  const loadMore =
    hasMore && state.attentionPage === 0
      ? `<div class="pagination"><button type="button" class="btn" id="load-more-attention">Load more</button></div>`
      : "";

  return `
    <header class="page-header">
      <h1>NOW</h1>
      <p>What deserves attention right now</p>
    </header>
    <div class="regime-strip">
      <div><span class="regime-strip__label">REGIME</span><br>${REGIME.summary} <span class="badge badge--partial">MOCK</span></div>
    </div>
    <section aria-label="Attention feed">
      <h2 style="font-size:14px;margin:0 0 10px;color:var(--text-secondary)">ATTENTION</h2>
      ${cards}
      ${loadMore}
    </section>
    <section class="watchlist-pulse" aria-label="Watchlist pulse">
      <span class="regime-strip__label" style="width:100%">WATCHLIST PULSE</span>
      ${pulse}
    </section>
  `;
}

function renderExplore() {
  const screenId = state.exploreScreen || EXPLORE_DATA.defaultScreen;
  const screen = EXPLORE_DATA.screens[screenId];
  const screens = EXPLORE_DATA.savedScreens
    .map((s) => {
      const cls = s.id === screenId ? "explore-tile explore-tile--active" : "explore-tile";
      return `<button type="button" class="${cls}" data-explore-screen="${s.id}">${s.label}</button>`;
    })
    .join("");
  const watchlists = EXPLORE_DATA.watchlists
    .map((w) => `<button type="button" class="explore-tile explore-tile--watchlist" disabled title="Watchlist management not in prototype">${w.label}</button>`)
    .join("");

  let resultsHtml = "";
  if (screen?.unavailable) {
    resultsHtml = `<div class="unavailable-panel explore-unavailable"><div class="unavailable-panel__icon" aria-hidden="true">⊘</div><h3>SCREEN UNAVAILABLE</h3><p>${screen.unavailable}</p></div>`;
  } else if (!screen?.results?.length) {
    resultsHtml = `<p style="color:var(--text-muted)">No matches in fixture for this screen.</p>`;
  } else {
    const rows = screen.results
      .map((r) => {
        const whyBtn = r.matched
          ? `<button type="button" class="btn btn--sm btn--ghost" data-action="why-match" data-symbol="${r.symbol}" title="Why matched?">?</button>`
          : "";
        return `<tr>
          <td><button type="button" class="explore-symbol-btn" data-action="open-explore-symbol" data-symbol="${r.symbol}">${r.symbol}</button>${r.mock ? ' <span class="badge badge--partial">MOCK</span>' : ""}</td>
          <td style="font-family:var(--font-mono)">${r.relVol}</td>
          <td>${r.summary}</td>
          <td>${whyBtn} <button type="button" class="btn btn--sm btn--ghost" data-action="inspect-explore" data-symbol="${r.symbol}">Inspect</button></td>
        </tr>`;
      })
      .join("");
    resultsHtml = `
      <table class="explore-results-table">
        <thead><tr><th>Symbol</th><th>Rel Vol</th><th>Match summary</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  const whyPopover =
    state.exploreWhySymbol && screen?.results
      ? (() => {
          const match = screen.results.find((r) => r.symbol === state.exploreWhySymbol);
          if (!match?.matched) return "";
          const criteria = match.matched
            .map((m) => `<li class="why-match__item${m.met ? " why-match__item--met" : " why-match__item--unmet"}">${m.met ? "✓" : "×"} ${m.criterion}</li>`)
            .join("");
          return `
            <div class="why-match-popover" id="why-match-popover" role="dialog" aria-label="Why matched">
              <div class="why-match-popover__header">
                <strong>${match.symbol} matched</strong>
                <button type="button" class="btn btn--sm btn--ghost" id="close-why-match" aria-label="Close">✕</button>
              </div>
              <ul class="why-match__list">${criteria}</ul>
              <button type="button" class="btn btn--sm" data-action="inspect-explore" data-symbol="${match.symbol}">Open in Inspector</button>
            </div>
          `;
        })()
      : "";

  return `
    <header class="page-header">
      <h1>EXPLORE</h1>
      <p>Discovery, screeners, and universe search — shell stub (V0.5)</p>
    </header>
    <div class="explore-search">
      <input type="search" class="explore-search__input" placeholder="Search symbols, screens, filings… (mock)" disabled aria-label="Explore search" />
      <span class="badge badge--partial">Search stubbed</span>
    </div>
    <div class="explore-panels">
      <section class="explore-panel" aria-label="Saved screens">
        <h2 class="explore-panel__title">SAVED SCREENS</h2>
        <div class="explore-tile-grid">${screens}</div>
      </section>
      <section class="explore-panel" aria-label="Watchlists">
        <h2 class="explore-panel__title">WATCHLISTS</h2>
        <div class="explore-tile-grid">${watchlists}</div>
      </section>
    </div>
    <section class="explore-results" aria-label="Screener results">
      <h2 class="explore-panel__title">RESULTS — ${screen?.title || screenId}</h2>
      ${resultsHtml}
      ${whyPopover}
    </section>
  `;
}

function renderCockpit(symbol) {
  const inst = INSTRUMENTS[symbol];
  if (!inst) {
    return `<div class="unavailable-panel"><h3>Unknown instrument</h3><p>${symbol} is not in the prototype fixture.</p><button class="btn" data-action="nav-now">Back to NOW</button></div>`;
  }

  const snap = symbol === "NVDA" ? getReplaySnapshot() : null;
  const price = snap ? snap.nvdaPrice : inst.price;
  const changePct = snap ? snap.nvdaChangePct : inst.changePct;
  const quality = snap?.quality || inst.quality;

  const changeCls = changePct >= 0 ? "up" : "down";
  const tabs = [
    { id: "overview", label: "Overview", unavailable: false },
    { id: "price", label: "Price", unavailable: false },
    { id: "orderFlow", label: "Order Flow", unavailable: !inst.modules.orderFlow },
    { id: "options", label: "Options", unavailable: !inst.modules.options },
    { id: "institutional", label: "Institutional", unavailable: !inst.modules.institutional },
  ];

  const tabHtml = tabs
    .map((t) => {
      const cls = [
        "module-tab",
        state.cockpitTab === t.id ? "is-active" : "",
        t.unavailable ? "is-unavailable" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return `<button type="button" class="${cls}" data-tab="${t.id}">${t.label}</button>`;
    })
    .join("");

  let moduleContent = "";

  if (state.cockpitTab === "overview" || state.cockpitTab === "price") {
    const alignment = inst.alignment
      .map((row, idx) => {
        let stateHtml = row.detail;
        if (row.state === "long") stateHtml = `<span class="alignment-row__state up">${row.detail}</span>`;
        else if (row.state === "short") stateHtml = `<span class="alignment-row__state down">${row.detail}</span>`;
        else if (row.state === "unavailable")
          stateHtml = `<span class="alignment-row__state unavailable">${row.detail}</span>`;
        const cls = row.inspect ? "alignment-row alignment-row--clickable" : "alignment-row";
        const attrs = row.inspect ? ` data-alignment-idx="${idx}" role="button" tabindex="0"` : "";
        return `<div class="${cls}"${attrs}><span>${row.module}</span>${stateHtml}</div>`;
      })
      .join("");

    const conflictHtml = inst.conflict
      ? `<div class="conflict-callout" data-action="conflict" role="button" tabindex="0" aria-label="Evidence conflict: ${inst.conflict.summary}">
          <span class="conflict-callout__icon" aria-hidden="true">⚡</span>
          <div>
            <strong>CONFLICT</strong>
            <p>${inst.conflict.summary}</p>
          </div>
          <span class="conflict-callout__cta">Compare →</span>
        </div>`
      : "";

    const storyEvents = filterStoryByReplay(inst.marketStory)
      .map(
        (e) =>
          `<div class="market-story__event" data-story-event data-symbol="${symbol}" data-time="${e.time}"><span class="market-story__time">${e.time}</span><span>${e.text}${e.mock ? " <span class='badge badge--partial'>MOCK</span>" : ""}</span></div>`
      )
      .join("");

    moduleContent = `
      <div class="instrument-header">
        <span class="instrument-header__symbol">${inst.symbol}</span>
        <span class="instrument-header__price">$${price.toFixed(2)}</span>
        <span class="instrument-header__change ${changeCls}">${formatChange(changePct)}</span>
        ${epistemicBadge(inst.epistemicClass)}
        ${qualityBadge(quality)}
        ${inst.mock ? '<span class="badge badge--partial">MOCK</span>' : ""}
        ${state.mode === "REPLAY" ? '<span class="badge badge--partial">REPLAY PIT</span>' : ""}
      </div>
      <h3 style="font-size:13px;color:var(--text-muted);margin:0 0 8px">EVIDENCE ALIGNMENT</h3>
      ${conflictHtml}
      <div class="alignment-panel">${alignment}</div>
      <div class="sparkline">
        <div class="sparkline__label">Price (1m) — MOCK sparkline on admitted fixture pattern</div>
        ${renderSparkline(inst.sparkline)}
      </div>
      <div class="market-story">
        <div class="market-story__header" id="story-toggle" role="button" tabindex="0" aria-expanded="${state.storyExpanded}">
          <span>MARKET STORY</span>
          <span>${state.storyExpanded ? "▼" : "▶"}</span>
        </div>
        ${state.storyExpanded ? `<div class="market-story__events">${storyEvents}</div>` : ""}
      </div>
    `;
  } else {
    const key =
      state.cockpitTab === "orderFlow"
        ? "orderFlow"
        : state.cockpitTab === "options"
          ? "options"
          : "institutional";
    const reason = inst.unavailableReasons[key];
    moduleContent = `
      <div class="unavailable-panel">
        <div class="unavailable-panel__icon" aria-hidden="true">⊘</div>
        <h3>${tabs.find((t) => t.id === state.cockpitTab)?.label} UNAVAILABLE</h3>
        <p>${reason}</p>
        <button type="button" class="btn" data-action="inspect-unavailable" data-module="${key}">Capability details</button>
        <button type="button" class="btn btn--ghost" data-action="explain-unavailable" data-module="${key}">Explain</button>
      </div>
    `;
  }

  return `
    <header class="page-header">
      <h1>Instrument Cockpit</h1>
      <p>Unified analysis shell — ${symbol}</p>
    </header>
    <nav class="module-tabs" aria-label="Module tabs">${tabHtml}</nav>
    ${moduleContent}
  `;
}

function renderInspector() {
  if (!state.inspectorOpen || !state.inspectorTarget) return "";

  const target = state.inspectorTarget;
  const tabs = INSPECTOR_TABS.map((tab) => {
    const cls = ["inspector-tab", state.inspectorTab === tab ? "is-active" : "", tab === "RAW" ? "inspector-tab--raw" : ""]
      .filter(Boolean)
      .join(" ");
    return `<button type="button" class="${cls}" data-inspector-tab="${tab}">${tab}</button>`;
  }).join("");

  let body = "";
  if (state.inspectorTab === "SUMMARY") {
    body = `
      <div class="inspector-field"><div class="inspector-field__label">Type</div>${target.type || target.title || "—"}</div>
      <div class="inspector-field"><div class="inspector-field__label">Epistemic class</div>${epistemicBadge(target.epistemicClass)}</div>
      <div class="inspector-field"><div class="inspector-field__label">Definition</div>${target.definition || target.meaning || "—"}</div>
      <div class="inspector-field"><div class="inspector-field__label">As of</div><span style="font-family:var(--font-mono)">${target.asOf || getEffectiveAsOf()}</span></div>
    `;
  } else if (state.inspectorTab === "EVIDENCE" && target.evidence) {
    body = `<ul style="margin:0;padding-left:18px;color:var(--text-secondary)">${target.evidence.map((e) => `<li>${e}</li>`).join("")}</ul>`;
  } else if (state.inspectorTab === "DERIVATION") {
    body = renderDerivationBody(target);
  } else if (state.inspectorTab === "QUALITY") {
    body = renderQualityBody(target);
  } else if (state.inspectorTab === "TIMELINE") {
    body = renderTimelineBody(target);
  } else if (state.inspectorTab === "PROVENANCE" && target.provenance) {
    body = `<div class="provenance-chain">${target.provenance.map((p) => `<div class="provenance-chain__node">${p}</div>`).join("")}<button type="button" class="btn btn--sm" id="provenance-to-raw" style="margin-top:12px">View RAW</button></div>`;
  } else if (state.inspectorTab === "USED BY") {
    body = renderUsedByBody(target);
  } else if (state.inspectorTab === "RAW" && target.raw) {
    body = `<pre style="font-size:11px;overflow:auto;background:var(--surface-0);padding:12px;border-radius:6px;color:var(--text-muted)">${JSON.stringify(target.raw, null, 2)}</pre>`;
  } else {
    body = `<p style="color:var(--text-muted)">Tab content not implemented in V0 prototype. Backend contract: <code>${state.inspectorTab}</code></p>`;
  }

  return `
    <aside class="inspector-panel" id="inspector" aria-label="Evidence Inspector">
      <div class="inspector-header">
        <strong>Evidence Inspector</strong>
        <button type="button" class="btn btn--sm btn--ghost" id="close-inspector" aria-label="Close inspector">✕</button>
      </div>
      <div class="inspector-tabs" role="tablist">${tabs}</div>
      <div class="inspector-body" role="tabpanel">${body}</div>
    </aside>
  `;
}

function renderDrawer() {
  if (!state.drawerOpen || !state.drawerContent) return "";
  const d = state.drawerContent;
  const asOf = getEffectiveAsOf();
  const modeLabel = state.mode === "REPLAY" ? "REPLAY" : "LIVE";

  if (state.drawerMode === "why") {
    const codes = (d.reasonCodes || [])
      .map((c) => `<li><code style="font-size:12px">${c}</code></li>`)
      .join("");
    return `
      <div class="drawer-overlay" id="drawer-overlay" role="dialog" aria-modal="true" aria-label="Why here">
        <div class="explanation-drawer explanation-drawer--compact">
          <div class="drawer-title">
            <h2>Why is ${d.symbol} here?</h2>
            <button type="button" class="btn btn--sm btn--ghost" id="close-drawer" aria-label="Close">✕</button>
          </div>
          <div class="drawer-meta">● ${modeLabel} · AS OF ${asOf}${d.symbol ? ` · ${d.symbol}` : ""}</div>
          <div class="drawer-section"><h3>Transition</h3><p>${d.transition}</p></div>
          <div class="drawer-section"><h3>Attention reason codes</h3><ul style="margin:0;padding-left:18px">${codes}</ul></div>
          <div style="display:flex;gap:8px;margin-top:16px">
            <button type="button" class="btn btn--primary" id="drawer-to-inspector">Open in Inspector</button>
            <button type="button" class="btn btn--ghost" id="why-to-explain">Full explanation</button>
          </div>
        </div>
      </div>
    `;
  }

  if (state.drawerMode === "transition") {
    const changed = (d.changed || [])
      .map(
        (c) =>
          `<div class="transition-row transition-row--changed"><span>${c.criterion}</span><span>${c.from} → <strong>${c.to}</strong>${c.mock ? " <span class='badge badge--partial'>MOCK</span>" : ""}</span></div>`
      )
      .join("");
    const unchanged = (d.unchanged || []).map((u) => `<li>${u}</li>`).join("");
    return `
      <div class="drawer-overlay" id="drawer-overlay" role="dialog" aria-modal="true" aria-label="Transition detail">
        <div class="explanation-drawer">
          <div class="drawer-title">
            <h2>${d.title}</h2>
            <button type="button" class="btn btn--sm btn--ghost" id="close-drawer" aria-label="Close">✕</button>
          </div>
          <div class="drawer-meta">● ${modeLabel} · AS OF ${asOf} · ${d.fromState} → ${d.toState}</div>
          <div class="drawer-section"><h3>Changed criteria</h3><div class="transition-diff">${changed}</div></div>
          <div class="drawer-section"><h3>Unchanged</h3><ul style="margin:0;padding-left:18px;color:var(--text-secondary)">${unchanged}</ul></div>
          <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap">
            <button type="button" class="btn btn--primary" id="drawer-to-inspector">Open in Inspector</button>
            <button type="button" class="btn btn--ghost" id="transition-to-timeline">View timeline</button>
            <button type="button" class="btn btn--ghost" id="transition-to-explain">Full explanation</button>
          </div>
        </div>
      </div>
    `;
  }

  const alignment =
    d.alignment && d.alignment.length
      ? `<div class="drawer-section"><h3>Alignment</h3><div class="alignment-mini">${d.alignment
          .map(
            (a) =>
              `<div class="alignment-mini__row"><span>${a.label}</span><span>${a.state} ${a.strength || ""}${a.mock ? " MOCK" : ""}</span></div>`
          )
          .join("")}</div></div>`
      : "";

  const mobile = state.drawerMode === "mobile" || (isMobileViewport() && state.drawerMode === "explain");
  if (mobile) {
    const att = state.drawerAttention;
    const symbol = state.drawerSymbol || att?.symbol || "";
    const compactAlignment =
      d.alignment && d.alignment.length
        ? `<div class="mobile-drawer__alignment">${d.alignment
            .map(
              (a) =>
                `<div class="mobile-drawer__align-row"><span>${a.label}</span><span>${a.state}</span></div>`
            )
            .join("")}</div>`
        : "";
    return `
      <div class="drawer-overlay drawer-overlay--mobile" id="drawer-overlay" role="dialog" aria-modal="true" aria-label="Mobile explanation">
        <div class="explanation-drawer explanation-drawer--mobile">
          <div class="mobile-drawer__handle" aria-hidden="true"></div>
          <div class="drawer-title">
            <h2>${d.title}</h2>
            <button type="button" class="btn btn--sm btn--ghost" id="close-drawer" aria-label="Close">✕</button>
          </div>
          <div class="drawer-meta">● ${modeLabel} · ${asOf}${symbol ? ` · ${symbol}` : ""}</div>
          <div class="mobile-drawer__summary">${d.meaning}</div>
          ${compactAlignment}
          <div class="mobile-drawer__quality">${qualityBadge(att?.quality || "PARTIAL")} <span>${d.qualityNote || ""}</span></div>
          <div class="mobile-drawer__actions">
            <button type="button" class="btn btn--primary" id="mobile-open-workspace" data-symbol="${symbol}">Open full workspace</button>
            <button type="button" class="btn" id="drawer-to-inspector">Inspector</button>
          </div>
        </div>
      </div>
    `;
  }

  return `
    <div class="drawer-overlay" id="drawer-overlay" role="dialog" aria-modal="true" aria-label="Explanation">
      <div class="explanation-drawer">
        <div class="drawer-title">
          <h2>${d.title}</h2>
          <button type="button" class="btn btn--sm btn--ghost" id="close-drawer" aria-label="Close">✕</button>
        </div>
        <div class="drawer-meta">● ${modeLabel} · AS OF ${asOf}${state.drawerSymbol ? ` · ${state.drawerSymbol}` : ""}</div>
        <div class="drawer-section"><h3>What it means</h3><p>${d.meaning}</p></div>
        <div class="drawer-section"><h3>Why it matters</h3><p>${d.why}</p></div>
        ${alignment}
        <div class="drawer-section"><h3>Quality</h3><p>${d.qualityNote}</p></div>
        <div style="display:flex;gap:8px;margin-top:16px">
          <button type="button" class="btn btn--primary" id="drawer-to-inspector">Open in Inspector</button>
          <button type="button" class="btn btn--ghost" disabled title="Not in prototype">Ask AI</button>
        </div>
      </div>
    </div>
  `;
}

function renderCommandPalette() {
  if (!state.commandOpen) return "";
  const items = COMMAND_ITEMS.map(
    (c, i) => `<div class="command-palette__item${i === 0 ? " is-selected" : ""}" data-cmd="${c.action}" data-target="${c.target}">${c.label}</div>`
  ).join("");
  return `
    <div class="command-palette" id="command-palette" role="dialog" aria-label="Command palette">
      <input type="text" placeholder="Type a command… (mock)" aria-label="Command search" />
      <div class="command-palette__results">${items}</div>
    </div>
  `;
}

function renderShortcutsOverlay() {
  if (!state.shortcutsOpen) return "";
  const sections = SHORTCUT_SECTIONS.map((section) => {
    const rows = section.items
      .map((item) => {
        const statusBadge =
          item.status === "active"
            ? '<span class="badge badge--good shortcuts-badge">Active</span>'
            : '<span class="badge badge--partial shortcuts-badge">Planned</span>';
        return `<tr class="shortcuts-row shortcuts-row--${item.status}">
          <td><kbd class="shortcut-kbd">${item.keys}</kbd></td>
          <td>${item.action}</td>
          <td>${statusBadge}</td>
        </tr>`;
      })
      .join("");
    return `
      <section class="shortcuts-section" aria-labelledby="shortcuts-${section.title.replace(/\s+/g, "-").toLowerCase()}">
        <h3 class="shortcuts-section__title" id="shortcuts-${section.title.replace(/\s+/g, "-").toLowerCase()}">${section.title}</h3>
        <table class="shortcuts-table">
          <thead><tr><th>Keys</th><th>Action</th><th>Status</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </section>
    `;
  }).join("");

  return `
    <div class="shortcuts-overlay" id="shortcuts-overlay" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
      <div class="shortcuts-panel">
        <div class="shortcuts-panel__header">
          <div>
            <h2>Keyboard shortcuts</h2>
            <p class="shortcuts-panel__subtitle">Expert workflow · standard navigation always available</p>
          </div>
          <button type="button" class="btn btn--sm btn--ghost" id="close-shortcuts" aria-label="Close shortcuts">✕</button>
        </div>
        <div class="shortcuts-panel__body">${sections}</div>
        <div class="shortcuts-panel__footer">
          <p>Press <kbd class="shortcut-kbd">?</kbd> or <kbd class="shortcut-kbd">Esc</kbd> to close · See <a href="../../navigation.md" style="color:var(--accent)">navigation.md</a> for full proposed set</p>
        </div>
      </div>
    </div>
  `;
}

function renderReplayBar() {
  if (state.mode !== "REPLAY") return "";
  const events = REPLAY_SESSION.events;
  const currentIdx = events.findIndex((e) => e.time.startsWith(state.replayTime.slice(0, 5)));
  const idx = currentIdx >= 0 ? currentIdx : events.length - 2;
  const pct = (idx / (events.length - 1)) * 100;

  const markers = events
    .map((e, i) => {
      const left = (i / (events.length - 1)) * 100;
      const isActive = e.time.startsWith(state.replayTime.slice(0, 5));
      return `<button type="button" class="replay-bar__marker${isActive ? " is-active" : ""}" style="left:${left}%" data-replay-jump="${e.time}" title="${e.time} — ${e.label}" aria-label="${e.label} at ${e.time}"></button>`;
    })
    .join("");

  return `
    <div class="replay-bar" id="replay-bar" aria-label="Replay controls">
      <div class="replay-bar__top">
        <span class="badge badge--replay">● REPLAY</span>
        <span class="replay-bar__time">AS OF <strong>${getEffectiveAsOf()}</strong></span>
        <span class="replay-bar__hint">All panels show knowable-at-time state</span>
        <button type="button" class="btn btn--sm btn--primary" id="return-to-live">Return to LIVE</button>
      </div>
      <div class="replay-bar__scrubber">
        <span class="replay-bar__session-start">${REPLAY_SESSION.sessionStart}</span>
        <div class="replay-bar__track">
          <div class="replay-bar__fill" style="width:${pct}%"></div>
          <div class="replay-bar__thumb" style="left:${pct}%"></div>
          ${markers}
        </div>
        <span class="replay-bar__session-end">${REPLAY_SESSION.sessionEnd}</span>
      </div>
      <div class="replay-bar__controls">
        <button type="button" class="btn btn--sm" id="replay-prev" title="Previous significant event">◀ Prev event</button>
        <button type="button" class="btn btn--sm${state.replayPlaying ? " btn--primary" : ""}" id="replay-play" title="Play/pause replay">${state.replayPlaying ? "❚❚ Pause" : "▶ Play"}</button>
        <button type="button" class="btn btn--sm" id="replay-next" title="Next significant event">Next event ▶</button>
      </div>
    </div>
  `;
}

function getSystemQuality() {
  const tier1 = ATTENTION_ITEMS.find((a) => a.tier === 1 && a.quality !== "GOOD");
  return tier1 ? tier1.quality : null;
}

function updateContextBar() {
  const symbolMatch = state.route.match(/instrument\/(\w+)/);
  let symbol = symbolMatch ? symbolMatch[1] : null;
  if (!symbol && state.drawerSymbol) symbol = state.drawerSymbol;
  const inst = symbol ? INSTRUMENTS[symbol] : null;
  const snap = symbol === "NVDA" ? getReplaySnapshot() : null;
  const systemQ = getSystemQuality();
  const quality = snap?.quality || (inst ? inst.quality : systemQ || "GOOD");

  const modeEl = $("#context-mode");
  if (modeEl) {
    if (state.mode === "REPLAY") {
      modeEl.className = "badge badge--replay";
      modeEl.textContent = "● REPLAY";
      modeEl.setAttribute("aria-label", "Mode: Replay");
    } else {
      modeEl.className = "badge badge--live";
      modeEl.textContent = "● LIVE";
      modeEl.setAttribute("aria-label", "Mode: Live");
    }
  }

  $("#context-as-of").textContent = getEffectiveAsOf();
  $("#context-symbol").textContent = symbol ? `· ${symbol}` : "";
  const qualityClickable = quality !== "GOOD" || getSystemQuality();
  $("#context-quality").innerHTML = qualityClickable
    ? `<button type="button" class="context-quality-btn" id="open-quality-panel" title="Data quality detail">${qualityBadge(quality)}</button>`
    : qualityBadge(quality);

  const replayBtn = $("#toggle-replay");
  if (replayBtn) {
    replayBtn.textContent = state.mode === "REPLAY" ? "Replay ●" : "Replay";
    replayBtn.classList.toggle("is-active", state.mode === "REPLAY");
  }

  document.body.classList.toggle("mode-replay", state.mode === "REPLAY");
}

function updateNavActive() {
  const hash = state.route || "#/now";
  const isNow = hash.startsWith("#/now") || hash === "#/";
  const isExplore = hash.startsWith("#/explore");
  const isInstrument = hash.startsWith("#/instrument/");
  document.querySelectorAll(".primary-nav__link").forEach((link) => {
    const nav = link.dataset.nav;
    const active =
      (nav === "now" && isNow) || (nav === "explore" && isExplore) || (nav === "workspace" && isInstrument);
    link.classList.toggle("is-active", active);
  });
}

function render() {
  parseRoute();
  const main = $("#main-content");
  const layout = $("#main-layout");

  let html = "";
  if (state.route.startsWith("#/instrument/")) {
    const symbol = state.route.split("/")[2];
    html = renderCockpit(symbol);
  } else if (state.route.startsWith("#/explore")) {
    html = renderExplore();
  } else if (state.route.startsWith("#/now")) {
    html = renderNow();
  } else {
    html = renderNow();
  }

  main.innerHTML = html;
  main.classList.toggle("with-inspector", state.inspectorOpen);

  const existingInspector = $("#inspector");
  if (existingInspector) existingInspector.remove();

  if (state.inspectorOpen) {
    layout.insertAdjacentHTML("beforeend", renderInspector());
  }

  const drawerHost = $("#drawer-host");
  drawerHost.innerHTML = renderDrawer();

  const replayHost = $("#replay-host");
  if (replayHost) replayHost.innerHTML = renderReplayBar();

  const cmdHost = $("#command-host");
  cmdHost.innerHTML = renderCommandPalette();

  const qualityHost = $("#quality-host");
  if (qualityHost) qualityHost.innerHTML = renderQualityPanel();

  const shortcutsHost = $("#shortcuts-host");
  if (shortcutsHost) shortcutsHost.innerHTML = renderShortcutsOverlay();

  updateContextBar();
  updateNavActive();
  bindEvents();
}

function openInspector(target, tab = "SUMMARY") {
  state.inspectorOpen = true;
  state.inspectorTab = tab;
  state.inspectorTarget = target;
  state.lastInspectTarget = target;
  render();
}

function openWhyDrawer(att) {
  state.drawerOpen = true;
  state.drawerMode = "why";
  state.drawerContent = att;
  state.drawerSymbol = att.symbol !== "SYSTEM" ? att.symbol : null;
  state._drawerInspect = att.inspect;
  render();
}

function openExplainDrawer(att) {
  state.drawerOpen = true;
  state.drawerMode = "explain";
  state.drawerContent = att.explanation;
  state.drawerSymbol = att.symbol !== "SYSTEM" ? att.symbol : null;
  state.drawerAttention = att;
  state._drawerInspect = att.inspect;
  render();
}

function openTransitionDrawer(att) {
  state.drawerOpen = true;
  state.drawerMode = "transition";
  state.drawerContent = att.transitionDetail;
  state.drawerSymbol = att.symbol;
  state._drawerInspect = att.transitionDetail?.inspect;
  render();
}

function closeDrawer() {
  state.drawerOpen = false;
  state.drawerContent = null;
  state.drawerSymbol = null;
  render();
}

function closeInspector() {
  state.inspectorOpen = false;
  state.inspectorTarget = null;
  render();
}

function bindEvents() {
  const storyToggle = $("#story-toggle");
  if (storyToggle) {
    storyToggle.addEventListener("click", () => {
      state.storyExpanded = !state.storyExpanded;
      render();
    });
  }

  $("#close-inspector")?.addEventListener("click", closeInspector);
  $("#close-drawer")?.addEventListener("click", closeDrawer);
  $("#drawer-to-inspector")?.addEventListener("click", () => {
    if (state._drawerInspect) {
      let tab = "SUMMARY";
      if (state.drawerMode === "transition" && state._drawerInspect.timeline) tab = "TIMELINE";
      closeDrawer();
      openInspector(state._drawerInspect, tab);
    }
  });
  $("#why-to-explain")?.addEventListener("click", () => {
    const att = ATTENTION_ITEMS.find((a) => a.id === state.drawerContent?.id);
    if (att) openExplainDrawer(att);
  });
  $("#transition-to-explain")?.addEventListener("click", () => {
    const att = ATTENTION_ITEMS.find((a) => a.symbol === state.drawerSymbol && a.transitionDetail);
    if (att) openExplainDrawer(att);
  });
  $("#transition-to-timeline")?.addEventListener("click", () => {
    if (state._drawerInspect?.timeline) {
      closeDrawer();
      openInspector(state._drawerInspect, "TIMELINE");
    }
  });
  $("#provenance-to-raw")?.addEventListener("click", () => {
    state.inspectorTab = "RAW";
    render();
  });
  $("#derivation-to-provenance")?.addEventListener("click", () => {
    state.inspectorTab = "PROVENANCE";
    render();
  });
  $("#open-quality-panel")?.addEventListener("click", openQualityPanel);
  $("#close-quality-panel")?.addEventListener("click", closeQualityPanel);
  $("#close-quality-panel-btn")?.addEventListener("click", closeQualityPanel);
  $("#quality-panel-overlay")?.addEventListener("click", (e) => {
    if (e.target.id === "quality-panel-overlay") closeQualityPanel();
  });
  $("#quality-to-inspector")?.addEventListener("click", () => {
    closeQualityPanel();
    openInspector(SYSTEM_QUALITY.inspect, "QUALITY");
  });
  document.querySelectorAll("[data-quality-symbol]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.qualitySymbol = btn.dataset.qualitySymbol;
      render();
    });
  });
  $("#quality-drill-back")?.addEventListener("click", () => {
    state.qualitySymbol = null;
    render();
  });
  $("#quality-open-cockpit")?.addEventListener("click", (e) => {
    const sym = e.currentTarget.dataset.symbol;
    closeQualityPanel();
    navigate(`#/instrument/${sym}`);
  });
  $("#mobile-open-workspace")?.addEventListener("click", (e) => {
    const sym = e.currentTarget.dataset.symbol;
    closeDrawer();
    if (sym && sym !== "SYSTEM") navigate(`#/instrument/${sym}`);
  });
  $("#drawer-overlay")?.addEventListener("click", (e) => {
    if (e.target.id === "drawer-overlay") closeDrawer();
  });

  document.querySelectorAll("[data-inspector-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.inspectorTab = btn.dataset.inspectorTab;
      render();
    });
  });

  $("#load-more-attention")?.addEventListener("click", () => {
    state.attentionPage += 1;
    render();
  });

  $("#open-command")?.addEventListener("click", () => {
    state.commandOpen = true;
    render();
    $("#command-palette input")?.focus();
  });

  $("#open-shortcuts")?.addEventListener("click", openShortcutsOverlay);
  $("#close-shortcuts")?.addEventListener("click", closeShortcutsOverlay);
  $("#shortcuts-overlay")?.addEventListener("click", (e) => {
    if (e.target.id === "shortcuts-overlay") closeShortcutsOverlay();
  });

  document.querySelectorAll(".command-palette__item").forEach((item) => {
    item.addEventListener("click", () => {
      const action = item.dataset.cmd;
      const target = item.dataset.target;
      state.commandOpen = false;
      if (action === "nav") navigate(target);
      else if (action === "explain") {
        const att = ATTENTION_ITEMS.find((a) => a.id === target);
        if (att) openExplainDrawer(att);
      } else if (action === "replay") {
        enterReplay(target);
      } else if (action === "live") {
        exitReplay();
      } else if (action === "alert") {
        navigate(`#/now/alert/${target}`);
      } else if (action === "quality") {
        openQualityPanel();
      } else if (action === "timeline") {
        const att = ATTENTION_ITEMS.find((a) => a.id === target);
        if (att?.transitionDetail?.inspect) openInspector(att.transitionDetail.inspect, "TIMELINE");
      } else if (action === "explore") {
        state.exploreScreen = target || EXPLORE_DATA.defaultScreen;
        navigate("#/explore");
      }
      render();
    });
  });

  $("#toggle-replay")?.addEventListener("click", () => {
    if (state.mode === "REPLAY") exitReplay();
    else enterReplay(REPLAY_SESSION.defaultReplay, false);
  });
  $("#return-to-live")?.addEventListener("click", exitReplay);
  $("#replay-prev")?.addEventListener("click", () => {
    stopReplayPlay();
    const events = REPLAY_SESSION.events;
    const idx = events.findIndex((e) => e.time.startsWith(state.replayTime.slice(0, 5)));
    const prev = idx > 0 ? events[idx - 1] : events[0];
    state.replayTime = prev.time;
    render();
  });
  $("#replay-next")?.addEventListener("click", () => {
    stopReplayPlay();
    const events = REPLAY_SESSION.events;
    const idx = events.findIndex((e) => e.time.startsWith(state.replayTime.slice(0, 5)));
    const next = idx < events.length - 1 ? events[idx + 1] : events[events.length - 1];
    state.replayTime = next.time;
    render();
  });
  document.querySelectorAll("[data-replay-jump]").forEach((btn) => {
    btn.addEventListener("click", () => {
      stopReplayPlay();
      state.replayTime = btn.dataset.replayJump;
      render();
    });
  });
  $("#replay-play")?.addEventListener("click", toggleReplayPlay);

  document.querySelectorAll("[data-explore-screen]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.exploreScreen = btn.dataset.exploreScreen;
      state.exploreWhySymbol = null;
      render();
    });
  });
  $("#close-why-match")?.addEventListener("click", () => {
    state.exploreWhySymbol = null;
    render();
  });
  document.querySelectorAll(".used-by-row__nav").forEach((btn) => {
    btn.addEventListener("click", () => {
      const route = btn.dataset.usedByRoute;
      if (route) navigate(route);
    });
  });
}

function getExploreMatch(symbol) {
  const screenId = state.exploreScreen || EXPLORE_DATA.defaultScreen;
  const screen = EXPLORE_DATA.screens[screenId];
  return screen?.results?.find((r) => r.symbol === symbol);
}

function onMainClick(e) {
  const tab = e.target.closest("[data-tab]");
  if (tab) {
    state.cockpitTab = tab.dataset.tab;
    render();
    return;
  }

  const story = e.target.closest("[data-story-event]");
  if (story) {
    const text = story.textContent || "";
    if (text.includes("CVD")) {
      openInspector(CVD_DERIVATION, "DERIVATION");
      return;
    }
    openInspector({
      type: "Market Story event",
      epistemicClass: "INFERRED",
      definition: `Timeline event at ${story.dataset.time}`,
      asOf: AS_OF_DISPLAY,
      provenance: ["Market Story aggregator (MOCK)", "→ session events"],
      raw: { time: story.dataset.time, symbol: story.dataset.symbol, mock: true },
    });
    return;
  }

  const alignRow = e.target.closest("[data-alignment-idx]");
  if (alignRow) {
    const symbol = state.route.split("/")[2];
    const inst = INSTRUMENTS[symbol];
    const row = inst?.alignment[Number(alignRow.dataset.alignmentIdx)];
    if (row?.inspect) {
      const tab = e.shiftKey && row.inspect.derivation ? "DERIVATION" : "EVIDENCE";
      openInspector(row.inspect, tab);
    }
    return;
  }

  const btn = e.target.closest("[data-action]");
  if (!btn) {
    const card = e.target.closest("[data-attention-id]");
    if (card) {
      const att = ATTENTION_ITEMS.find((a) => a.id === card.dataset.attentionId);
      if (att && att.symbol !== "SYSTEM") {
        state.storyExpanded = true;
        navigate(`#/instrument/${att.symbol}`);
      }
    }
    return;
  }

  const action = btn.dataset.action;
  if (action === "conflict") {
    const symbol = state.route.split("/")[2];
    const inst = INSTRUMENTS[symbol];
    if (inst?.conflict?.inspect) openInspector(inst.conflict.inspect, "EVIDENCE");
    return;
  }
  if (action === "why") {
    const att = ATTENTION_ITEMS.find((a) => a.id === btn.dataset.id);
    if (att) openWhyDrawer(att);
  } else if (action === "explain") {
    const att = ATTENTION_ITEMS.find((a) => a.id === btn.dataset.id);
    if (att) openExplainDrawer(att);
  } else if (action === "transition") {
    const att = ATTENTION_ITEMS.find((a) => a.id === btn.dataset.id);
    if (att?.transitionDetail) openTransitionDrawer(att);
  } else if (action === "open") {
    const sym = btn.dataset.symbol;
    if (sym === "SYSTEM") openInspector(ATTENTION_ITEMS.find((a) => a.id === "att-system-1").inspect);
    else navigate(`#/instrument/${sym}`);
  } else if (action === "nav-now") {
    navigate("#/now");
  } else if (action === "why-match") {
    state.exploreWhySymbol = btn.dataset.symbol;
    render();
  } else if (action === "open-explore-symbol") {
    navigate(`#/instrument/${btn.dataset.symbol}`);
  } else if (action === "inspect-explore") {
    const match = getExploreMatch(btn.dataset.symbol);
    if (match?.inspect) openInspector(match.inspect, "SUMMARY");
  } else if (action === "inspect-unavailable" || action === "explain-unavailable") {
    const symbol = state.route.split("/")[2];
    const inst = INSTRUMENTS[symbol];
    const mod = btn.dataset.module;
    openInspector({
      type: `Capability: ${mod}`,
      epistemicClass: "OBSERVED",
      definition: inst.unavailableReasons[mod],
      asOf: AS_OF_DISPLAY,
      provenance: ["Platform capability gate", "→ Phase 5 boundary", "→ ADR-WHALE-001 (institutional)"],
      raw: { capability: mod, available: false, symbol },
    });
  }
}

function bindGlobal() {
  window.addEventListener("hashchange", render);
  $("#main-content")?.addEventListener("click", onMainClick);

  document.getElementById("open-inspector-btn")?.addEventListener("click", () => {
    if (state.lastInspectTarget) openInspector(state.lastInspectTarget);
    else {
      const att = ATTENTION_ITEMS.find((a) => a.tier === 1) || ATTENTION_ITEMS[0];
      if (att) openInspector(att.inspect);
    }
  });

  document.querySelectorAll(".primary-nav__link").forEach((link) => {
    link.addEventListener("click", (e) => {
      if (link.classList.contains("is-disabled") && link.dataset.nav !== "explore") {
        e.preventDefault();
        alert("Not included in UX Prototype V0. See prototype/README.md for scope.");
      }
    });
  });

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      state.commandOpen = !state.commandOpen;
      if (state.commandOpen) state.shortcutsOpen = false;
      render();
    }
    if (e.key === "?" && !e.metaKey && !e.ctrlKey && !e.altKey && !isTextInputFocused()) {
      e.preventDefault();
      state.shortcutsOpen = !state.shortcutsOpen;
      if (state.shortcutsOpen) state.commandOpen = false;
      render();
    }
    if (e.key === "Escape") {
      if (state.shortcutsOpen) {
        closeShortcutsOverlay();
      } else if (state.commandOpen) {
        state.commandOpen = false;
        render();
      } else if (state.qualityPanelOpen) closeQualityPanel();
      else if (state.drawerOpen) closeDrawer();
      else if (state.inspectorOpen) closeInspector();
    }
    if (e.key === "e" && !e.metaKey && !e.ctrlKey && document.activeElement?.tagName !== "INPUT") {
      const focused = document.activeElement?.closest("[data-attention-id]");
      const att = focused
        ? ATTENTION_ITEMS.find((a) => a.id === focused.dataset.attentionId)
        : ATTENTION_ITEMS.find((a) => a.symbol === "NVDA");
      if (att) openExplainDrawer(att);
    }
    if (e.key === "i" && !e.metaKey && !e.ctrlKey && document.activeElement?.tagName !== "INPUT") {
      if (state.lastInspectTarget) openInspector(state.lastInspectTarget);
      else {
        const att = ATTENTION_ITEMS.find((a) => a.tier === 1) || ATTENTION_ITEMS[0];
        if (att) openInspector(att.inspect);
      }
    }
  });
}

bindGlobal();
render();
