"use strict";

/* Short Squeeze Research Screener — browser view.
 *
 * This script renders what the server sends. It computes no metric, evaluates no rule,
 * and derives no score, probability or ranking. A field with no value renders an em dash
 * plus its status and reason; it is never rendered as 0.
 */

/* getJSON, setStatus, MISSING, el, text, ago, showToast — provided by shared.js */

const state = {
  mode: "FROZEN_RESEARCH",
  rows: [],
  selected: null,
  symbols: "",
  profiles: [],
  autoTimer: null,
  summary: null,
  comparisonRows: [],
};

/* ------------------------------------------------------------------ fetching */
/* getJSON, setStatus — provided by shared.js */

/* Column layouts. Missing columns are never dropped: the user must see what is absent. */
const FROZEN_COLUMNS = [
  ["Symbol", "symbol"], ["Data mode", "data_mode"],
  ["Reference price", "f:reference_price"], ["% change", "f:percentage_change"],
  ["Rel. volume", "f:relative_volume"], ["Float", "f:float_shares"],
  ["Short float", "f:short_float"], ["Borrow fee", "f:borrow_fee"],
  ["Borrow avail.", "f:borrow_availability"],
  ["News", "f:news_count"], ["Latest headline", "f:latest_headline"],
  ["News / catalyst", "f:catalyst"],
  ["Sentiment", "f:sentiment"], ["Phase 3A", "phase3a"],
  ["Research detection", "detection"], ["Outcome", "outcome"],
  ["Evidence coverage", "coverage"], ["Freshness", "freshness"], ["Last updated", "updated"],
];

const CURRENT_COLUMNS = [
  ["Symbol", "symbol"], ["Discovery source", "discovery"], ["Market mode", "market_mode"],
  ["Last", "f:last"], ["Bid", "f:bid"], ["Ask", "f:ask"],
  ["Prev close", "f:previous_close"], ["% change", "f:percentage_change"],
  ["Rel. volume", "f:relative_volume"], ["Float", "f:float_shares"],
  ["Shares out.", "f:shares_outstanding"],   ["Short float", "f:short_float"],
  ["Short ratio", "f:short_ratio"], ["Days to cover", "f:days_to_cover"],
  ["Published SI", "f:published_short_interest"],
  ["Borrow fee", "f:borrow_fee"], ["Shortability", "f:shortable"],
  ["Shortable shares", "f:borrow_availability"], ["News", "f:news_count"],
  ["Latest headline", "f:latest_headline"], ["Latest HN", "f:latest_news_at"],
  ["Catalyst", "f:catalyst"], ["Sentiment", "f:sentiment"], ["Phase 3A", "phase3a"],
  ["Research detection", "detection"], ["Evidence coverage", "coverage"],
  ["Freshness", "freshness"], ["Updated", "updated"],
];

const columns = () => (state.mode === "CURRENT" ? CURRENT_COLUMNS : FROZEN_COLUMNS);

function pillClass(outcome) {
  switch (outcome) {
    case "PASS": return "pill pill-pass";
    case "FAIL": return "pill pill-fail";
    case "UNKNOWN": return "pill pill-unknown";
    case "CONFLICTED":
    case "INSUFFICIENT_DATA":
    case "NOT_APPLICABLE": return "pill pill-blocked";
    default: return "pill pill-neutral";
  }
}

/* A field cell. Missing always shows the dash AND the status label. */
function fieldCell(field) {
  const td = document.createElement("td");
  if (!field) { td.className = "missing"; td.textContent = MISSING; return td; }
  if (field.status === "KNOWN") {
    td.textContent = field.unit ? `${field.value} ${field.unit}` : String(field.value);
    const bits = [];
    if (field.provider) bits.push(`provider ${field.provider}`);
    if (field.event_time) bits.push(`event ${field.event_time}`);
    if (field.data_mode) bits.push(`mode ${field.data_mode}`);
    if (field.readiness) bits.push(field.readiness);
    td.title = bits.join(" · ");
    return td;
  }
  td.className = "missing";
  const dash = document.createElement("span");
  dash.textContent = MISSING + " ";
  const label = document.createElement("span");
  label.className = "pill pill-unknown";
  label.textContent = field.status.replace(/_/g, " ");
  td.append(dash, label);
  td.title = field.missing_reason || "";
  return td;
}

function statusCell(value, cls, title) {
  const td = document.createElement("td");
  const span = document.createElement("span");
  span.className = cls || "pill pill-neutral";
  span.textContent = value;
  td.appendChild(span);
  if (title) td.title = title;
  return td;
}

function detectionClass(status) {
  if (status === "DETECTED") return "pill pill-pass";
  if (status === "NOT_DETECTED") return "pill pill-fail";
  return "pill pill-unknown";
}

/* getJSON, setStatus, showToast — provided by shared.js */

/* ---------------------------------------------------------------- readiness */

function renderReadiness(readiness) {
  if (!readiness) return;
  const demo = el("demo-ready");
  demo.textContent = readiness.demo_ready ? "DEMO READY" : "DEMO NOT READY";
  demo.className = "ready-badge " + (readiness.demo_ready ? "ok" : "bad");
  demo.title = (readiness.demo_checks || [])
    .map((c) => `${c.ok ? "OK" : "NO"} — ${c.check}: ${c.detail}`).join("\n")
    + "\n\n" + (readiness.demo_note || "");

  const live = el("live-ready");
  live.textContent = readiness.live_sources_ready ? "LIVE SOURCES READY" : "LIVE SOURCES NOT READY";
  live.className = "ready-badge " + (readiness.live_sources_ready ? "ok" : "none");
  live.title = (readiness.live_checks || [])
    .map((c) => `${c.ok ? "OK" : "NO"} — ${c.check}: ${c.detail}`).join("\n");
}

/* ------------------------------------------------------------------ providers */

async function loadHealth() {
  const strip = el("provider-strip");
  strip.textContent = "Probing…";
  try {
    const health = await getJSON("/api/health");
    strip.textContent = "";
    const entries = (health.providers || []).concat(
      (health.provider_calls || []).map((call) => ({
        name: call.name,
        state: call.state,
        detail: [call.detail, call.last_success_at ? `last success ${call.last_success_at}` : null]
          .filter(Boolean).join(" · "),
      })),
    );
    const seen = new Set();
    entries.forEach((provider) => {
      const key = `${provider.name}|${provider.state}`;
      if (seen.has(key)) return;
      seen.add(key);
      const box = document.createElement("div");
      const good = ["CONNECTED", "AVAILABLE", "OK"].includes(provider.state);
      const bad = ["DISCONNECTED", "UNAVAILABLE", "FAILED", "PERMISSION_UNAVAILABLE"]
        .includes(provider.state);
      box.className = `provider ${good ? "ok" : bad ? "bad" : "none"}`;
      box.title = provider.detail || "";
      const dot = document.createElement("span"); dot.className = "dot";
      const name = document.createElement("span"); name.textContent = provider.name;
      const st = document.createElement("span"); st.className = "state"; st.textContent = provider.state;
      box.append(dot, name, st);
      strip.appendChild(box);
    });
    renderReadiness(health.readiness);
  } catch (error) {
    strip.textContent = `Provider probe failed: ${error.message}`;
  }
}

/* ------------------------------------------------------------------ screener */

function renderBanners(header, extra) {
  const holder = el("banners");
  holder.textContent = "";
  const banners = (header && header.banners) || [];
  banners.concat(extra || []).forEach((message) => {
    const div = document.createElement("div");
    div.className = "banner" + (/PREVIEW|EXPERIMENTAL/.test(message) ? " preview" : "");
    div.textContent = message;
    holder.appendChild(div);
  });
}

function renderHeader(header) {
  const badge = el("mode-badge");
  badge.textContent = header.mode_label || header.mode;
  badge.classList.toggle("current", header.mode === "CURRENT");
}

function renderHead() {
  const head = el("screener-head");
  head.textContent = "";
  columns().forEach(([label]) => {
    const th = document.createElement("th");
    th.textContent = label;
    head.appendChild(th);
  });
}

function cellFor(row, key) {
  if (key.startsWith("f:")) return fieldCell(row.fields[key.slice(2)]);
  switch (key) {
    case "symbol": {
      const td = document.createElement("td");
      const strong = document.createElement("strong");
      strong.textContent = row.symbol;
      td.appendChild(strong);
      if (row.scan_membership_label) {
        const tag = document.createElement("span");
        tag.className = "pill pill-neutral";
        tag.style.marginLeft = "6px";
        tag.textContent = "OFF SCAN";
        tag.title = row.scan_membership_label;
        td.appendChild(tag);
      }
      return td;
    }
    case "data_mode":
      return statusCell(String(row.data_mode).replace(/_/g, " "), "pill pill-neutral");
    case "market_mode":
      return statusCell(row.market_data_mode || "UNKNOWN", "pill pill-neutral",
        "Reported by the provider's own market-data type callback, never inferred.");
    case "discovery": {
      const td = document.createElement("td");
      td.textContent = row.discovery_source || row.discovery_profile || MISSING;
      if (row.provider_scanner_order !== null && row.provider_scanner_order !== undefined) {
        const tag = document.createElement("span");
        tag.className = "muted";
        tag.style.marginLeft = "6px";
        tag.textContent = `#${row.provider_scanner_order}`;
        tag.title = "Provider scanner order.";
        td.appendChild(tag);
      }
      return td;
    }
    case "phase3a": {
      const td = document.createElement("td");
      const counts = row.phase3a.counts;
      [["PASS", counts.PASS], ["FAIL", counts.FAIL], ["UNKNOWN", counts.UNKNOWN]]
        .forEach(([k, v]) => {
          const span = document.createElement("span");
          span.className = pillClass(k);
          span.style.marginRight = "4px";
          span.textContent = `${v} ${k}`;
          td.appendChild(span);
        });
      return td;
    }
    case "detection":
      return statusCell(row.research_detection.status,
        detectionClass(row.research_detection.status),
        (row.research_detection.reasons || []).join(" "));
    case "outcome":
      return statusCell(row.outcome.status, "pill pill-unknown",
        (row.outcome.reasons || []).join(" "));
    case "coverage":
      return text(document.createElement("td"), row.evidence_coverage.label);
    case "freshness": {
      const bits = [];
      if (row.age_seconds !== null && row.age_seconds !== undefined) {
        bits.push(`observation age ${row.age_seconds}s (${row.age_basis || "observation"})`);
      }
      if (row.retrieval_age_seconds !== null && row.retrieval_age_seconds !== undefined) {
        bits.push(`retrieved ${row.retrieval_age_seconds}s ago`);
      }
      return statusCell(row.freshness, "pill pill-neutral", bits.join(" · "));
    }
    case "updated":
      return text(document.createElement("td"), row.last_updated || MISSING);
    default:
      return text(document.createElement("td"), MISSING);
  }
}

function renderRows(rows) {
  const body = el("screener-body");
  body.textContent = "";
  el("row-count").textContent = `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns().length; td.className = "muted"; td.textContent = "No rows.";
    tr.appendChild(td); body.appendChild(tr);
    return;
  }
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.className = "clickable";
    if (state.selected === row.symbol) tr.classList.add("selected");
    tr.addEventListener("click", () => selectSymbol(row.symbol));
    columns().forEach(([, key]) => tr.appendChild(cellFor(row, key)));
    body.appendChild(tr);
  });
}

function filterParams(params) {
  const map = {
    detection: "filter-detection",
    market_mode: "filter-market-mode",
    freshness: "filter-freshness",
    profile: "filter-profile",
    min_price: "filter-min-price",
    max_price: "filter-max-price",
    min_change: "filter-min-change",
    min_relvol: "filter-min-relvol",
    min_pass: "filter-min-pass",
    max_unknown: "filter-max-unknown",
    min_coverage: "filter-min-coverage",
  };
  Object.entries(map).forEach(([name, id]) => {
    const node = el(id);
    if (node && node.value !== "") params.set(name, node.value);
  });
}

function renderRefreshClock() {
  const summary = state.summary;
  const node = el("refresh-clock");
  if (!summary) { node.textContent = ""; return; }
  const bits = [];
  bits.push(`Last refreshed: ${summary.last_refresh_at || MISSING}`);
  if (summary.auto_refresh) {
    bits.push(`next in ~${summary.quote_refresh_seconds}s`);
  } else {
    bits.push("auto refresh off");
  }
  if (summary.last_refresh_error) bits.push(`last error: ${summary.last_refresh_error}`);
  node.textContent = bits.join(" · ");
}

async function loadScreener() {
  setStatus("Loading screener…");
  const params = new URLSearchParams({
    mode: state.mode,
    sort: el("sort-key").value,
    desc: el("sort-desc").checked ? "true" : "false",
  });
  const filter = el("filter-symbol").value.trim();
  if (filter) params.set("symbol", filter);
  filterParams(params);

  try {
    const payload = await getJSON(`/api/screener?${params.toString()}`);
    state.rows = payload.rows;
    state.summary = payload.summary || null;
    renderHeader(payload.header);
    const extra = [];
    if (payload.available === false && payload.reason) extra.push(payload.reason);
    (payload.errors || []).forEach((e) => extra.push(`${e.input}: ${e.error}`));
    if (payload.summary && payload.summary.disclaimer) extra.push(payload.summary.disclaimer);
    renderBanners(payload.header, extra);
    renderHead();
    renderRows(payload.rows);
    renderRefreshClock();
    const hidden = (payload.unfiltered_row_count || 0) - payload.row_count;
    setStatus(
      `Retrieved at ${payload.header.generated_at} (application retrieval time, not `
      + `market-data time).${hidden > 0 ? ` ${hidden} row(s) hidden by filters.` : ""}`,
    );
  } catch (error) {
    renderHead();
    renderRows([]);
    setStatus(`Screener unavailable: ${error.message}`, true);
  }
}

/* ------------------------------------------------------------------ discovery */

async function loadProfiles() {
  try {
    const payload = await getJSON("/api/discovery/profiles");
    state.profiles = payload.profiles || [];
    const select = el("discovery-profile");
    select.textContent = "";
    const filterSelect = el("filter-profile");
    filterSelect.textContent = "";
    const any = document.createElement("option");
    any.value = ""; any.textContent = "any";
    filterSelect.appendChild(any);
    state.profiles.forEach((profile) => {
      const option = document.createElement("option");
      option.value = profile.profile_id;
      option.textContent = profile.title;
      option.title = `${profile.purpose}\n\n${profile.criteria.join("\n")}\n\n`
        + `Ordering: ${profile.ordering}\n${profile.disclaimer}`;
      if (profile.profile_id === payload.selected) option.selected = true;
      select.appendChild(option);
      const f = document.createElement("option");
      f.value = profile.profile_id; f.textContent = profile.title;
      filterSelect.appendChild(f);
    });
    renderProfileCriteria();
  } catch (error) {
    setStatus(`Discovery profiles unavailable: ${error.message}`, true);
  }
}

function renderProfileCriteria() {
  const chosen = state.profiles.find((p) => p.profile_id === el("discovery-profile").value);
  if (!chosen) return;
  const holder = el("banners");
  const div = document.createElement("div");
  div.className = "banner preview";
  div.textContent = `${chosen.label} · ${chosen.title}: ${chosen.criteria.join(" ")}`;
  holder.appendChild(div);
}

async function runDiscovery() {
  setStatus("Running provider discovery…");
  try {
    const params = new URLSearchParams({ profile: el("discovery-profile").value });
    const result = await getJSON(`/api/discovery/refresh?${params.toString()}`, { method: "POST" });
    if (result.error) {
      setStatus(`Discovery unavailable: ${result.error}. Existing candidates were kept.`, true);
    } else {
      setStatus(`Discovered ${result.discovered} candidate(s). Refreshing evidence…`);
      await refreshNow();
      return;
    }
  } catch (error) {
    setStatus(`Discovery failed: ${error.message}`, true);
  }
  await loadScreener();
  await loadHealth();
}

async function refreshNow() {
  setStatus("Refreshing current evidence…");
  try {
    await getJSON("/api/live/refresh", { method: "POST" });
  } catch (error) {
    setStatus(`Refresh failed: ${error.message}. The previous snapshot was retained.`, true);
  }
  await loadScreener();
  await loadHealth();
  if (state.selected) await selectSymbol(state.selected);
}

async function setAutoRefresh(enabled) {
  try {
    const params = new URLSearchParams({ enabled: enabled ? "true" : "false" });
    state.summary = await getJSON(`/api/live/auto?${params.toString()}`, { method: "POST" });
    renderRefreshClock();
  } catch (error) {
    setStatus(`Auto refresh could not be changed: ${error.message}`, true);
  }
  if (state.autoTimer) { clearInterval(state.autoTimer); state.autoTimer = null; }
  if (enabled) {
    const seconds = (state.summary && state.summary.quote_refresh_seconds) || 30;
    // The server refreshes on its own schedule; the browser only re-reads the result.
    state.autoTimer = setInterval(() => {
      if (state.mode === "CURRENT") { loadScreener(); loadHealth(); }
    }, seconds * 1000);
  }
}

/* -------------------------------------------------------------------- detail */

function kv(key, value, why) {
  const box = document.createElement("div");
  box.className = "kv";
  const k = document.createElement("div"); k.className = "k"; k.textContent = key;
  const v = document.createElement("div"); v.className = "v";
  v.textContent = (value === null || value === undefined || value === "") ? MISSING : String(value);
  box.append(k, v);
  if (why) { const w = document.createElement("div"); w.className = "why"; w.textContent = why; box.appendChild(w); }
  return box;
}

function fieldKv(label, field) {
  if (!field) return kv(label, null, "No field record.");
  if (field.status === "KNOWN") {
    const parts = [];
    if (field.provider) parts.push(`provider ${field.provider}`);
    if (field.event_time) parts.push(`event ${field.event_time}`);
    if (field.received_time) parts.push(`received ${field.received_time}`);
    parts.push(`freshness ${field.freshness}`);
    if (field.data_mode) parts.push(`mode ${field.data_mode}`);
    if (field.evidence_id) parts.push(`evidence ${field.evidence_id}`);
    if (field.readiness) parts.push(`readiness ${field.readiness}`);
    if (field.provider_field) parts.push(`provider field ${field.provider_field}`);
    if (field.selection_reason) parts.push(`selected ${field.selection_reason}`);
    if (field.research_admissibility) {
      parts.push(`research ${field.research_admissibility}`);
    }
    return kv(label, field.unit ? `${field.value} ${field.unit}` : field.value, parts.join(" · "));
  }
  return kv(label, `${MISSING} ${field.status.replace(/_/g, " ")}`, field.missing_reason);
}

function section(title) {
  const h = document.createElement("h3");
  h.textContent = title;
  return h;
}

function grid(children) {
  const div = document.createElement("div");
  div.className = "detail-grid";
  children.forEach((child) => div.appendChild(child));
  return div;
}

function buildChart(chart) {
  const wrap = document.createElement("div");
  wrap.className = "chart-wrap";
  if (!chart || !chart.available || !chart.points.length) {
    wrap.className = "chart-wrap muted";
    wrap.textContent = (chart && chart.reason) || "No chart available.";
    return wrap;
  }
  const points = chart.points;
  const w = 900, h = 220, padL = 46, padR = 12, padT = 12, padB = 24;
  const closes = points.map((p) => p.close);
  const min = Math.min(...closes), max = Math.max(...closes);
  const span = (max - min) || 1;
  const x = (i) => padL + (i / Math.max(1, points.length - 1)) * (w - padL - padR);
  const y = (v) => padT + (1 - (v - min) / span) * (h - padT - padB);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "chart");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("preserveAspectRatio", "none");

  const path = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  path.setAttribute("class", "line");
  path.setAttribute("points", points.map((p, i) => `${x(i).toFixed(1)},${y(p.close).toFixed(1)}`).join(" "));
  svg.appendChild(path);

  /* A boundary line is drawn only when one actually exists. A current candidate has no
   * frozen detection boundary, so its marker is the snapshot instant instead. */
  const markerLabel = chart.boundary_label || chart.snapshot_label;
  if (markerLabel) {
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "line");
    marker.setAttribute("class", chart.boundary_label ? "boundary" : "snapshot");
    marker.setAttribute("x1", w - padR); marker.setAttribute("x2", w - padR);
    marker.setAttribute("y1", padT); marker.setAttribute("y2", h - padB);
    svg.appendChild(marker);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", w - padR - 6); label.setAttribute("y", padT + 10);
    label.setAttribute("text-anchor", "end");
    label.textContent = markerLabel;
    svg.appendChild(label);
  }

  /* The latest observed point, marked so it is visible as an actual observation. */
  const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  dot.setAttribute("class", "latest");
  dot.setAttribute("cx", x(points.length - 1).toFixed(1));
  dot.setAttribute("cy", y(points[points.length - 1].close).toFixed(1));
  dot.setAttribute("r", "3.5");
  svg.appendChild(dot);

  [[max, padT + 8], [min, h - padB - 2]].forEach(([value, yy]) => {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", 6); t.setAttribute("y", yy);
    t.textContent = value.toFixed(2);
    svg.appendChild(t);
  });

  wrap.appendChild(svg);
  const caption = document.createElement("p");
  caption.className = "chart-note";
  const times = `${points[0].t} → ${points[points.length - 1].t}`;
  caption.textContent = `${chart.series_label} · ${chart.point_count_plotted} of `
    + `${chart.point_count_total} bars plotted · ${times} · provider ${chart.provider}`;
  wrap.appendChild(caption);
  (chart.notes || []).forEach((note) => {
    const p = document.createElement("p");
    p.className = "chart-note";
    p.textContent = note;
    wrap.appendChild(p);
  });
  return wrap;
}

function buildRuleTable(rules) {
  const scroll = document.createElement("div");
  scroll.className = "table-scroll";
  const table = document.createElement("table");
  table.innerHTML = `<thead><tr>
    <th>Rule</th><th>Category</th><th>Outcome</th><th>Observed value</th>
    <th>Threshold</th><th>Evidence</th><th class="wrap">Reason</th></tr></thead>`;
  const body = document.createElement("tbody");
  rules.forEach((rule) => {
    const tr = document.createElement("tr");
    tr.appendChild(text(document.createElement("td"), rule.rule_id));
    tr.appendChild(text(document.createElement("td"), rule.category));
    tr.appendChild(statusCell(rule.outcome, pillClass(rule.outcome)));
    tr.appendChild(text(document.createElement("td"), rule.observed_display));
    tr.appendChild(text(document.createElement("td"), rule.threshold));
    const ev = text(document.createElement("td"), rule.evidence_display);
    if (rule.evidence_ids && rule.evidence_ids.length) ev.title = rule.evidence_ids.join("\n");
    tr.appendChild(ev);
    const why = text(document.createElement("td"), rule.reason);
    why.className = "wrap";
    tr.appendChild(why);
    body.appendChild(tr);
  });
  table.appendChild(body);
  scroll.appendChild(table);
  return scroll;
}

function buildMethodologyComparison(rows) {
  const scroll = document.createElement("div");
  scroll.className = "table-scroll";
  const table = document.createElement("table");
  table.innerHTML = `<thead><tr>
    <th>Methodology</th><th>Pressure</th><th>Ignition</th><th>Coverage</th>
    <th>Classification</th><th>Evaluable?</th><th class="wrap">Supporting Evidence</th>
    <th class="wrap">Missing Evidence</th><th class="wrap">Reason</th></tr></thead>`;
  const body = document.createElement("tbody");
  rows.forEach((item) => {
    const coverage = item.evidence_coverage || {};
    const coverageDisplay = coverage.percent == null
      ? (coverage.label || coverage.category || MISSING)
      : `${coverage.percent}% · ${String(coverage.category || "").replace(/_/g, " ")}`;
    const evidence = (item.supporting_evidence || []).map((value) =>
      `${value.key || value.provider_field || "field"} (${value.provider || "unknown provider"})`
    ).join("; ");
    const reasons = [
      ...(item.blocking_reasons || []),
      ...(item.conflict_reasons || []),
    ].join(" ");
    const values = [
      item.methodology_label,
      item.pressure,
      item.ignition,
      coverageDisplay,
      item.classification,
      item.evaluable ? "YES" : "NO",
      evidence,
      (item.missing_inputs || []).join(", "),
      reasons,
    ];
    const tr = document.createElement("tr");
    values.forEach((value, index) => {
      const td = text(
        document.createElement("td"),
        value === null || value === undefined || value === "" ? MISSING : value,
      );
      if (index >= 6) td.className = "wrap";
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
  table.appendChild(body);
  scroll.appendChild(table);
  return scroll;
}

function buildList(items, renderer) {
  const ul = document.createElement("ul");
  ul.className = "plain-list";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = renderer(item);
    ul.appendChild(li);
  });
  return ul;
}

/* ------------------------------------------------ methodology comparison */

function methodology(row, id) {
  return (row.methodologies || []).find((item) => item.methodology_id === id) || {};
}

function knownValue(row, field) {
  const item = (row.fields || {})[field];
  return item && item.status === "KNOWN" ? item.value : null;
}

function comparisonValue(row, key) {
  const adam = methodology(row, "adam_evidence_gated_prime.v1");
  if (key === "classification") return adam.classification;
  if (key === "pressure") return row.pressure;
  if (key === "ignition") return row.ignition;
  if (key === "coverage") return (row.coverage || {}).percent;
  if (key === "percentage_change") return knownValue(row, "percentage_change");
  if (key === "relative_volume") return knownValue(row, "relative_volume");
  if (key === "float") return knownValue(row, "float_shares");
  if (key === "short_float") return knownValue(row, "short_float");
  if (key === "freshness") return row.freshness;
  if (key === "trend") return (row.trend || {}).state;
  return row.symbol;
}

function compareComparisonValues(av, bv, descending) {
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const aNum = Number(av);
  const bNum = Number(bv);
  if (Number.isFinite(aNum) && Number.isFinite(bNum)) {
    return descending ? bNum - aNum : aNum - bNum;
  }
  const order = String(av).localeCompare(String(bv));
  return descending ? -order : order;
}

function comparisonRowsForView() {
  const classification = el("comparison-classification").value;
  const trendFilter = el("comparison-trend").value;
  const key = el("comparison-sort").value;
  const descending = el("comparison-desc").checked;
  const rows = state.comparisonRows.filter((row) => {
    const adam = methodology(row, "adam_evidence_gated_prime.v1");
    return (!classification || adam.classification === classification)
      && (!trendFilter || (row.trend || {}).state === trendFilter);
  });
  const known = rows.filter((row) => comparisonValue(row, key) != null);
  const missing = rows.filter((row) => comparisonValue(row, key) == null);
  known.sort((a, b) => compareComparisonValues(
    comparisonValue(a, key),
    comparisonValue(b, key),
    descending,
  ));
  missing.sort((a, b) => a.symbol.localeCompare(b.symbol));
  return known.concat(missing);
}

function methodologyDisplay(row, id) {
  const item = methodology(row, id);
  return item.classification || MISSING;
}

function renderMethodologyTable(rows) {
  const body = el("methodology-body");
  body.textContent = "";
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = text(document.createElement("td"), "No comparison rows match the filters.");
    td.colSpan = 21;
    td.className = "muted";
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }
  rows.forEach((row) => {
    const values = [
      row.symbol,
      methodologyDisplay(row, "legacy_prime_setup"),
      methodologyDisplay(row, "peer_reference_methodology"),
      methodologyDisplay(row, "adam_evidence_gated_prime.v1"),
      (row.why_listed || []).join("; ") || MISSING,
      row.pressure,
      row.ignition,
      (row.coverage || {}).percent == null ? null : `${row.coverage.percent}%`,
      knownValue(row, "percentage_change"),
      knownValue(row, "relative_volume"),
      knownValue(row, "float_shares"),
      knownValue(row, "short_float"),
      ((row.phase3a || {}).counts || {}).PASS,
      ((row.phase3a || {}).counts || {}).FAIL,
      ((row.phase3a || {}).counts || {}).UNKNOWN,
      (row.research_detection || {}).status,
      (row.trend || {}).state,
      ((row.fields || {}).last || {}).provider || MISSING,
      row.freshness,
      row.updated,
    ];
    const tr = document.createElement("tr");
    tr.setAttribute("data-symbol", row.symbol);
    tr.className = "clickable";
    tr.addEventListener("click", () => {
      state.selected = row.symbol;
      synchronizeComparisonSelection();
    });
    values.forEach((value) => {
      tr.appendChild(text(
        document.createElement("td"),
        value === null || value === undefined || value === "" ? MISSING : value,
      ));
    });
    body.appendChild(tr);
  });
}

function synchronizeComparisonSelection() {
  document.querySelectorAll("#methodology-body tr[data-symbol]").forEach((row) => {
    row.classList.toggle("selected", row.getAttribute("data-symbol") === state.selected);
  });
  document.querySelectorAll("#research-landscape circle[data-symbol]").forEach((point) => {
    const selected = point.getAttribute("data-symbol") === state.selected;
    point.setAttribute("stroke", selected ? "#ffffff" : "#0d1117");
    point.setAttribute("stroke-width", selected ? "3" : "1.5");
  });
}

function svgElement(name) {
  return document.createElementNS("http://www.w3.org/2000/svg", name);
}

function renderResearchLandscape(rows) {
  const svg = el("research-landscape");
  const tooltip = el("methodology-tooltip");
  svg.textContent = "";
  const w = 900, h = 430, left = 60, right = 24, top = 24, bottom = 48;
  const x = (value) => left + (Number(value) / 100) * (w - left - right);
  const y = (value) => h - bottom - (Number(value) / 100) * (h - top - bottom);

  [0, 25, 50, 75, 100].forEach((tick) => {
    const vertical = svgElement("line");
    vertical.setAttribute("class", "grid");
    vertical.setAttribute("x1", x(tick)); vertical.setAttribute("x2", x(tick));
    vertical.setAttribute("y1", top); vertical.setAttribute("y2", h - bottom);
    svg.appendChild(vertical);
    const horizontal = svgElement("line");
    horizontal.setAttribute("class", "grid");
    horizontal.setAttribute("x1", left); horizontal.setAttribute("x2", w - right);
    horizontal.setAttribute("y1", y(tick)); horizontal.setAttribute("y2", y(tick));
    svg.appendChild(horizontal);
  });

  const xAxis = svgElement("line");
  xAxis.setAttribute("class", "axis");
  xAxis.setAttribute("x1", left); xAxis.setAttribute("x2", w - right);
  xAxis.setAttribute("y1", h - bottom); xAxis.setAttribute("y2", h - bottom);
  svg.appendChild(xAxis);
  const yAxis = svgElement("line");
  yAxis.setAttribute("class", "axis");
  yAxis.setAttribute("x1", left); yAxis.setAttribute("x2", left);
  yAxis.setAttribute("y1", top); yAxis.setAttribute("y2", h - bottom);
  svg.appendChild(yAxis);

  const xLabel = svgElement("text");
  xLabel.setAttribute("x", (left + w - right) / 2);
  xLabel.setAttribute("y", h - 12);
  xLabel.setAttribute("text-anchor", "middle");
  xLabel.textContent = "Pressure";
  svg.appendChild(xLabel);
  const yLabel = svgElement("text");
  yLabel.setAttribute("x", 16);
  yLabel.setAttribute("y", (top + h - bottom) / 2);
  yLabel.setAttribute("transform", `rotate(-90 16 ${(top + h - bottom) / 2})`);
  yLabel.setAttribute("text-anchor", "middle");
  yLabel.textContent = "Ignition";
  svg.appendChild(yLabel);

  const colors = {
    PRIME: "#56d68b", SUBPRIME: "#6fa8ff", WATCH: "#ffca57",
    NOT_QUALIFIED: "#ff7d7d", UNEVALUABLE: "#8b98a9", CONFLICTED: "#cbb6f0",
    REFERENCE_DEFINITION_INCOMPLETE: "#8b98a9",
  };
  let plotted = 0;
  let unplotted = 0;
  rows.forEach((point) => {
    if (point.pressure == null || point.ignition == null) {
      unplotted += 1;
      return;
    }
    plotted += 1;
    const adam = methodology(point, "adam_evidence_gated_prime.v1");
    const coverage = Number((point.coverage || {}).percent || 0);
    const circle = svgElement("circle");
    circle.setAttribute("data-symbol", point.symbol);
    circle.setAttribute("cx", x(point.pressure));
    circle.setAttribute("cy", y(point.ignition));
    circle.setAttribute("r", String(5 + Math.min(8, coverage / 15)));
    circle.setAttribute("fill", colors[adam.classification] || colors.UNEVALUABLE);
    circle.setAttribute("fill-opacity", String(0.35 + Math.min(0.6, coverage / 160)));
    circle.addEventListener("mouseenter", (event) => {
      tooltip.hidden = false;
      tooltip.style.left = `${event.offsetX + 14}px`;
      tooltip.style.top = `${event.offsetY + 14}px`;
      tooltip.textContent = [
        point.symbol,
        `Evidence-Gated: ${adam.classification || MISSING}`,
        `Pressure: ${point.pressure}`,
        `Ignition: ${point.ignition}`,
        `Coverage: ${(point.coverage || {}).percent ?? MISSING}%`,
        `Provider status: ${((point.fields || {}).last || {}).status || MISSING}`,
        `% change: ${knownValue(point, "percentage_change") ?? MISSING}`,
        `Relative volume: ${knownValue(point, "relative_volume") ?? MISSING}`,
        `Trend: ${(point.trend || {}).state || MISSING}`,
      ].join("\n");
    });
    circle.addEventListener("mouseleave", () => { tooltip.hidden = true; });
    circle.addEventListener("click", () => {
      state.selected = point.symbol;
      synchronizeComparisonSelection();
    });
    svg.appendChild(circle);
  });
  el("plotted-count").textContent = `${plotted} plotted`;
  el("unplotted-count").textContent =
    `${unplotted} unplotted because Pressure or Ignition evidence is missing`;
  synchronizeComparisonSelection();
}

function renderComparison() {
  const rows = comparisonRowsForView();
  renderMethodologyTable(rows);
  renderResearchLandscape(rows);
}

async function loadComparison() {
  const panel = el("comparison-panel");
  panel.hidden = false;
  setStatus("Loading methodology comparison…");
  try {
    const payload = await getJSON("/api/methodologies");
    state.comparisonRows = (payload.data && payload.data.rows) || [];
    renderComparison();
    setStatus(`Loaded ${state.comparisonRows.length} server-evaluated candidate comparison(s).`);
  } catch (error) {
    state.comparisonRows = [];
    renderComparison();
    setStatus(`Methodology comparison unavailable: ${error.message}`, true);
  }
}

function statBlock(items) {
  const row = document.createElement("div");
  row.className = "summary-row";
  items.forEach(([n, l]) => {
    const box = document.createElement("div");
    box.className = "stat";
    const num = document.createElement("div"); num.className = "n"; num.textContent = n;
    const lab = document.createElement("div"); lab.className = "l"; lab.textContent = l;
    box.append(num, lab);
    row.appendChild(box);
  });
  return row;
}

async function selectSymbol(symbol) {
  state.selected = symbol;
  const panel = el("detail-panel");
  panel.hidden = false;
  panel.textContent = "";
  panel.appendChild(text(document.createElement("h2"), `Loading ${symbol}…`));
  renderRows(state.rows);

  let detail;
  try {
    detail = await getJSON(`/api/symbol?symbol=${encodeURIComponent(symbol)}&mode=${state.mode}`);
  } catch (error) {
    panel.textContent = "";
    panel.appendChild(text(document.createElement("h2"), `${symbol}`));
    panel.appendChild(text(document.createElement("p"), `Detail unavailable: ${error.message}`));
    return;
  }
  panel.textContent = "";
  if (detail.error) {
    panel.appendChild(text(document.createElement("h2"), symbol));
    panel.appendChild(text(document.createElement("p"), detail.error));
    return;
  }

  const id = detail.identity;
  const md = detail.market_data || {};
  const isCurrent = state.mode === "CURRENT";
  panel.appendChild(text(document.createElement("h2"), `${id.symbol} — symbol detail`));

  panel.appendChild(section("Snapshot"));
  panel.appendChild(grid(isCurrent ? [
    kv("Symbol", id.symbol),
    kv("Contract", id.contract ? `conId ${id.contract.con_id || MISSING} · ${id.contract.long_name || ""}` : null,
       id.contract ? `${id.contract.primary_exchange || ""} ${id.contract.currency || ""}` : ""),
    kv("Discovery profile", id.discovery_profile),
    kv("Discovery time", id.discovery_time),
    kv("First seen", id.first_seen_at),
    kv("As-of time", id.as_of_time, "The completion instant of the latest completed bar."),
    kv("Snapshot time", id.snapshot_at),
    kv("Market mode", id.market_data_mode, "Reported by the provider, never inferred."),
    kv("Freshness", id.freshness),
  ] : [
    kv("Symbol", id.symbol),
    kv("Case ID", id.case_id),
    kv("Candidate ID", id.candidate_id),
    kv("Boundary / as-of", id.boundary_time || id.retrieved_at),
    kv("Provider", id.provider),
    kv("Data mode", id.mode_label || id.data_mode),
  ]));

  if (isCurrent) {
    panel.appendChild(section("Quote"));
    panel.appendChild(grid([
      fieldKv("Last", md.last),
      fieldKv("Bid", md.bid),
      fieldKv("Ask", md.ask),
      fieldKv("Previous close", md.previous_close),
      fieldKv("Open", md.open),
      fieldKv("High", md.high),
      fieldKv("Low", md.low),
      fieldKv("Historical close (bar)", md.historical_close),
    ]));

    panel.appendChild(section("Activity"));
    panel.appendChild(grid([
      fieldKv("Percentage change", md.percentage_change),
      fieldKv("Relative volume", md.relative_volume),
      fieldKv("Provider volume (raw)", md.provider_volume),
    ]));
  } else {
    panel.appendChild(section("Market data"));
    panel.appendChild(grid([
      fieldKv("Reference price", md.reference_price),
      fieldKv("Percentage change", md.percentage_change),
      fieldKv("Relative volume", md.relative_volume),
    ]));
  }

  if (detail.metric_record) {
    const m = detail.metric_record;
    panel.appendChild(grid([
      kv("Metric", `${m.metric_name} = ${m.value} ${m.unit}`,
         `${m.calculation_policy_version} · ${m.price_field} · ${m.source_interval} · ${m.provider_scope}`),
      kv("Bar coverage", `${m.input_bar_boundaries.length} boundary bars`,
         m.input_bar_boundaries.map((b) => `${b.bar_start} → ${b.bar_end}`).join(" | ")),
      kv("Metric evidence ID", m.deterministic_id, `quality ${m.quality_state}`),
    ]));
  }

  panel.appendChild(section("Short-pressure evidence"));
  panel.appendChild(grid([
    fieldKv("Float", md.float_shares),
    fieldKv("Shares outstanding", md.shares_outstanding),
    fieldKv("Short float", md.short_float),
    fieldKv("Short ratio", md.short_ratio),
    fieldKv("Published short interest", md.published_short_interest),
    fieldKv("Borrow fee", md.borrow_fee),
    fieldKv("Borrow availability", md.borrow_availability),
    fieldKv("Days to cover", md.days_to_cover),
    fieldKv("Shortable (provider indicator)", md.shortable),
  ]));

  panel.appendChild(section("Catalyst evidence"));
  panel.appendChild(grid([
    fieldKv("News", md.news_count),
    fieldKv("News / filings / halts", md.catalyst),
    fieldKv("Sentiment", md.sentiment),
    fieldKv("Positive headlines", md.sentiment_positive_count),
    fieldKv("Neutral headlines", md.sentiment_neutral_count),
    fieldKv("Negative headlines", md.sentiment_negative_count),
    fieldKv("Sentiment model", md.sentiment_model_id),
  ]));

  if (md.sentiment && md.sentiment.status === "KNOWN") {
    panel.appendChild(section("EXPERIMENTAL NEWS SENTIMENT"));
    const sPanel = document.createElement("div");
    sPanel.className = "banner preview";
    sPanel.textContent = "Sentiment analysis powered by FinBERT.";
    panel.appendChild(sPanel);
    panel.appendChild(grid([
      kv("Dominant label", md.sentiment.value),
      kv("Positive / Neutral / Negative",
         `${md.sentiment_positive_count ? md.sentiment_positive_count.value : "—"} / ` +
         `${md.sentiment_neutral_count ? md.sentiment_neutral_count.value : "—"} / ` +
         `${md.sentiment_negative_count ? md.sentiment_negative_count.value : "—"}`),
      kv("Model ID", md.sentiment_model_id ? md.sentiment_model_id.value : MISSING),
    ]));
  }

  panel.appendChild(section("Research status"));
  const counts = (detail.phase3a && detail.phase3a.counts) || { PASS: 0, FAIL: 0, UNKNOWN: 0 };
  panel.appendChild(statBlock([
    [detail.evidence_coverage ? detail.evidence_coverage.supported : 0, "Evidence-supported rules"],
    [counts.PASS, "PASS"],
    [counts.FAIL, "FAIL"],
    [counts.UNKNOWN, "UNKNOWN"],
  ]));
  panel.appendChild(grid([
    kv("Research detection", detail.research_detection ? detail.research_detection.status : MISSING,
       detail.research_detection ? (detail.research_detection.reasons || []).join(" ") : ""),
    kv("Outcome", detail.outcome ? detail.outcome.status : MISSING,
       detail.outcome ? (detail.outcome.reasons || []).join(" ") : ""),
    kv("Evidence coverage", detail.evidence_coverage ? detail.evidence_coverage.label : MISSING),
  ]));
  if (detail.research_detection && detail.research_detection.preview_banner) {
    const b = document.createElement("div");
    b.className = "banner preview";
    b.textContent = detail.research_detection.preview_banner;
    panel.appendChild(b);
  }

  if (detail.methodology_comparison && detail.methodology_comparison.length) {
    panel.appendChild(section("Methodology comparison"));
    panel.appendChild(buildMethodologyComparison(detail.methodology_comparison));
    const note = document.createElement("p");
    note.className = "chart-note";
    note.textContent = "Separate descriptive methods.";
    panel.appendChild(note);
  }

  if (detail.chart) {
    panel.appendChild(section(isCurrent ? "Current session price" : "Detection-context price"));
    panel.appendChild(buildChart(detail.chart));
  }

  panel.appendChild(section("Phase 3A rules (all 25, canonical order)"));
  panel.appendChild(buildRuleTable(detail.rules || []));

  if (detail.missing_evidence && detail.missing_evidence.length) {
    panel.appendChild(section("Missing evidence"));
    panel.appendChild(buildList(detail.missing_evidence,
      (m) => `${m.field}: ${m.status}${m.reason_code ? ` (${m.reason_code})` : ""} — ${m.reason}`));
  }

  if (detail.transitions && detail.transitions.length) {
    panel.appendChild(section("Research-state changes this session"));
    panel.appendChild(buildList(detail.transitions, (t) => [
      `${t.changed_at} · ${t.rule_id}: ${t.previous_outcome} → ${t.current_outcome}`,
      t.evidence_provider ? `provider ${t.evidence_provider}` : "",
      t.evidence_id ? `evidence ${t.evidence_id}` : "",
      t.reason ? `reason ${t.reason}` : "",
    ].filter(Boolean).join(" · ")));
  }

  if (detail.evidence_notes && detail.evidence_notes.length) {
    panel.appendChild(section("Evidence selection"));
    panel.appendChild(buildList(detail.evidence_notes, (n) => n));
  }

  if (detail.provenance) {
    panel.appendChild(section("Provenance"));
    const p = detail.provenance;
    const cells = [
      kv("Phase 3A request ID", p.phase3a_request_id),
      kv("Phase 3A result ID", p.phase3a_result_id),
      kv("Policy version", p.policy_version),
      kv("Evaluation version", p.evaluation_version),
    ];
    if (isCurrent) {
      cells.push(
        kv("Provider scope", (p.provider_scope || []).join(", ")),
        kv("Absolute price status", p.absolute_price_status, p.absolute_price_rationale),
        kv("Absolute price constraints", (p.absolute_price_constraints || []).length + " constraint(s)",
           (p.absolute_price_constraints || []).join(" ")),
        kv("Volume status", p.volume_status, p.volume_rationale),
        kv("Percentage-return window", "canonical", p.percentage_return_window),
        kv("Note", p.note),
      );
    } else {
      cells.push(
        kv("Result SHA-256", p.phase3a_result_sha256),
        kv("Evidence association", p.evidence_association_id),
        kv("Freeze status", p.freeze_status),
        kv("Leakage audit", p.leakage_audit_status),
        kv("Global preflight", p.global_preflight_status),
        kv("Forward OHLCV accessed", p.forward_ohlcv_accessed === undefined ? null : String(p.forward_ohlcv_accessed)),
        kv("Outcome accessed", p.outcome_accessed === undefined ? null : String(p.outcome_accessed)),
        kv("Detection-context artifact", p.detection_context_artifact_name, p.detection_context_artifact_sha256),
        kv("Note", p.note),
      );
    }
    panel.appendChild(grid(cells));
  }
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ----------------------------------------------------------- research summary */

async function loadResearchSummary() {
  const panel = el("research-summary-panel");
  panel.hidden = false;
  panel.textContent = "";
  panel.appendChild(text(document.createElement("h2"), "Research summary"));
  try {
    const payload = await getJSON("/api/research-summary");
    const s = payload.historical_research || payload;
    const c = payload.current_operational_screen || {};

    panel.appendChild(section("Panel 1 — Frozen research results"));
    panel.appendChild(statBlock([
      [s.case_count, "Real cases"],
      [s.rule_case_pairs, "Rule-case evaluations"],
      [s.outcome_totals.PASS, "PASS"],
      [s.outcome_totals.FAIL, "FAIL"],
      [s.outcome_totals.UNKNOWN, "UNKNOWN"],
    ]));
    const pct = s.percentage_change_split || {};
    panel.appendChild(grid([
      kv("Boundary", s.boundary_time),
      kv("Rules evaluable across all cases", s.evaluable_rules_across_all_cases.join(", ")),
      kv("PERCENTAGE_CHANGE_MINIMUM — PASS", (pct.PASS || []).join(", "), `${(pct.PASS || []).length} case(s)`),
      kv("PERCENTAGE_CHANGE_MINIMUM — FAIL", (pct.FAIL || []).join(", "), `${(pct.FAIL || []).length} case(s)`),
      kv("Research detection", Object.entries(s.research_detection_counts).map(([k, v]) => `${v} × ${k}`).join(", ")),
      kv("Outcome", Object.entries(s.outcome_counts).map(([k, v]) => `${v} × ${k}`).join(", ")),
      kv("Global preflight", s.global_preflight_verdict),
      kv("Phase 3B published", String(s.phase3b_published)),
      kv("Phase 3E started", String(s.phase3e_started)),
    ]));

    panel.appendChild(section("Panel 2 — Current operational screen"));
    panel.appendChild(statBlock([
      [c.candidate_count === undefined ? 0 : c.candidate_count, "Current candidates"],
      [c.evaluable_rule_count === undefined ? 0 : c.evaluable_rule_count, "Rules currently evaluable"],
      [c.partial_evidence_candidates === undefined ? 0 : c.partial_evidence_candidates, "Partial-evidence candidates"],
    ]));
    panel.appendChild(grid([
      kv("Discovery profile", c.discovery_profile),
      kv("Market-data mode", c.market_data_mode),
      kv("Research detection", Object.entries(c.research_detection_counts || {}).map(([k, v]) => `${v} × ${k}`).join(", ")),
      kv("Currently evaluable rules", (c.evaluable_rules || []).join(", ")),
      kv("Last discovery", c.last_discovery_at),
      kv("Last refresh", c.last_refresh_at),
      kv("Auto refresh", String(c.auto_refresh)),
      kv("Last refresh error", c.last_refresh_error),
    ]));

    if (payload.separation_note) {
      const sep = document.createElement("div");
      sep.className = "banner preview";
      sep.textContent = payload.separation_note;
      panel.appendChild(sep);
    }
    const preview = document.createElement("div");
    preview.className = "banner preview";
    preview.textContent = s.preview_banner;
    panel.appendChild(preview);
    (s.notes || []).forEach((note) => {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = note;
      panel.appendChild(p);
    });
  } catch (error) {
    panel.appendChild(text(document.createElement("p"), `Summary unavailable: ${error.message}`));
  }
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* -------------------------------------------------------------------- export */

async function doExport() {
  setStatus("Exporting…");
  const params = new URLSearchParams({ mode: state.mode });
  try {
    const result = await getJSON(`/api/export?${params.toString()}`, { method: "POST" });
    setStatus(`Exported ${result.row_count} row(s): ${result.written.json} and ${result.written.csv}`);
  } catch (error) {
    setStatus(`Export failed: ${error.message}`, true);
  }
}

function doExportCsv() {
  if (!state.rows.length) {
    setStatus("No rows to export.", true);
    return;
  }
  const stem = `research-screener-${state.mode.toLowerCase()}-${exportTimestamp()}`;
  downloadBlob(stem + ".csv", researchRowsToCsv(state.rows), "text/csv;charset=utf-8");
  setStatus(`Downloaded CSV (${state.rows.length} row(s).`);
}

/* ---------------------------------------------------------------------- wire */

function setMode(mode) {
  state.mode = mode;
  state.selected = null;
  el("detail-panel").hidden = true;
  el("comparison-panel").hidden = true;
  el("research-summary-panel").hidden = true;
  el("btn-frozen").classList.toggle("active", mode === "FROZEN_RESEARCH");
  el("btn-current").classList.toggle("active", mode === "CURRENT");
  el("btn-research-summary").classList.remove("active");
  el("btn-comparison").classList.remove("active");
  el("current-controls").hidden = mode !== "CURRENT";
  el("refresh-controls").hidden = mode !== "CURRENT";
  loadScreener();
}

function clearFilters() {
  ["filter-detection", "filter-market-mode", "filter-freshness", "filter-profile",
   "filter-min-price", "filter-max-price", "filter-min-change", "filter-min-relvol",
   "filter-min-pass", "filter-max-unknown", "filter-min-coverage"]
    .forEach((id) => { const node = el(id); if (node) node.value = ""; });
  loadScreener();
}

function init() {
  el("btn-frozen").addEventListener("click", () => setMode("FROZEN_RESEARCH"));
  el("btn-current").addEventListener("click", () => setMode("CURRENT"));
  el("btn-comparison").addEventListener("click", () => {
    el("detail-panel").hidden = true;
    el("research-summary-panel").hidden = true;
    el("comparison-panel").hidden = false;
    el("btn-frozen").classList.remove("active");
    el("btn-current").classList.remove("active");
    el("btn-comparison").classList.add("active");
    el("btn-research-summary").classList.remove("active");
    loadComparison();
  });
  el("btn-research-summary").addEventListener("click", () => {
    el("comparison-panel").hidden = true;
    el("btn-comparison").classList.remove("active");
    el("btn-research-summary").classList.add("active");
    loadResearchSummary();
  });
  el("btn-load-current").addEventListener("click", async () => {
    state.symbols = el("manual-symbols").value.trim();
    if (!state.symbols) return;
    const params = new URLSearchParams({ mode: "CURRENT", symbols: state.symbols, refresh: "true" });
    setStatus("Retrieving current evidence…");
    try {
      await getJSON(`/api/screener?${params.toString()}`);
    } catch (error) {
      setStatus(`Could not add symbols: ${error.message}`, true);
    }
    await loadScreener();
    await loadHealth();
  });
  el("manual-symbols").addEventListener("keydown", (event) => {
    if (event.key === "Enter") el("btn-load-current").click();
  });
  el("btn-clear-current").addEventListener("click", async () => {
    await getJSON("/api/live/clear", { method: "POST" }).catch(() => ({}));
    loadScreener();
  });
  el("btn-discover").addEventListener("click", runDiscovery);
  el("discovery-profile").addEventListener("change", () => {
    renderBanners(null, []);
    renderProfileCriteria();
  });
  el("btn-refresh-now").addEventListener("click", refreshNow);
  el("auto-refresh").addEventListener("change", (event) => setAutoRefresh(event.target.checked));
  el("btn-refresh").addEventListener("click", () => { loadHealth(); loadScreener(); });
  el("btn-export").addEventListener("click", doExport);
  el("btn-export-csv").addEventListener("click", doExportCsv);
  el("btn-more-filters").addEventListener("click", () => {
    const node = el("advanced-filters");
    node.hidden = !node.hidden;
  });
  el("btn-clear-filters").addEventListener("click", clearFilters);
  el("filter-symbol").addEventListener("input", loadScreener);
  el("sort-key").addEventListener("change", loadScreener);
  el("sort-desc").addEventListener("change", loadScreener);
  ["comparison-classification", "comparison-trend", "comparison-sort", "comparison-desc"]
    .forEach((id) => el(id).addEventListener("change", renderComparison));
  ["filter-detection", "filter-market-mode", "filter-freshness", "filter-profile",
   "filter-min-price", "filter-max-price", "filter-min-change", "filter-min-relvol",
   "filter-min-pass", "filter-max-unknown", "filter-min-coverage"]
    .forEach((id) => { const node = el(id); if (node) node.addEventListener("change", loadScreener); });

  /* Frozen mode is rendered first and never waits on a provider. */
  renderHead();
  loadScreener();
  loadHealth();
  loadProfiles();
}

document.addEventListener("DOMContentLoaded", init);
