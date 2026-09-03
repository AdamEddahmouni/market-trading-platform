"use strict";

/* Shared utilities for the Short Squeeze Research Screener.
 *
 * This module contains no metric computation, no rule evaluation, no score,
 * no probability, and no ranking. It provides only DOM helpers, fetch utilities,
 * and presentation-only formatting shared across views.
 */

const MISSING = "\u2014";
const N_A = "N/A";

const newsCache = {};

const CLASS_COLORS = {
  PRIME: "#56d68b",
  SUBPRIME: "#6fa8ff",
  WATCH: "#ffca57",
  NOT_QUALIFIED: "#ff7d7d",
  UNEVALUABLE: "#8b98a9",
  CONFLICTED: "#cbb6f0",
  REFERENCE_DEFINITION_INCOMPLETE: "#9aa8bc",
};

const PRESSURE_COLORS = {
  high: "#56d68b",
  mid: "#ffca57",
  low: "#ff7d7d",
  none: "#8b98a9",
};

function pressureColor(v) {
  if (v == null) return PRESSURE_COLORS.none;
  if (v >= 70) return PRESSURE_COLORS.high;
  if (v >= 50) return PRESSURE_COLORS.mid;
  return PRESSURE_COLORS.low;
}

const el = (id) => document.getElementById(id);
const text = (node, value) => { node.textContent = value; return node; };

async function getJSON(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function setStatus(message, isError) {
  const node = el("status-line");
  if (!node) return;
  const isScanner = document.body && document.body.classList.contains("scanner");
  const msg = String(message || "");
  let show = true;
  if (isScanner) {
    show = !!(
      msg
      && (isError
        || /loading|refreshing|awaiting|discovering|unavailable|error|ready but/i.test(msg))
    );
    if (!show) {
      node.textContent = "";
      node.setAttribute("hidden", "");
      return;
    }
    node.removeAttribute("hidden");
  }
  node.textContent = msg;
  node.style.color = isError ? "#ff9d9d" : "";
}

function ago(iso) {
  if (!iso) return null;
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return Math.round(diff) + "s ago";
    if (diff < 3600) return Math.round(diff / 60) + "m ago";
    if (diff < 86400) return Math.round(diff / 3600) + "h ago";
    return Math.round(diff / 86400) + "d ago";
  } catch (e) {
    return iso;
  }
}

async function getCachedNews(symbol) {
  const cached = newsCache[symbol];
  if (cached && (Date.now() - cached.at < 60000)) return cached.data;
  try {
    const newsUrl = "/api/news/symbol?symbol=" + encodeURIComponent(symbol);
    const payload = await getJSON(newsUrl);
    const data = payload && payload.data != null ? payload.data : payload;
    newsCache[symbol] = { data: data, at: Date.now() };
    return data;
  } catch (e) {
    return null;
  }
}

function csvEscape(value) {
  if (value == null || value === "") return "";
  const s = String(value);
  if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function downloadBlob(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType || "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportTimestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return (
    d.getFullYear()
    + pad(d.getMonth() + 1)
    + pad(d.getDate())
    + "T"
    + pad(d.getHours())
    + pad(d.getMinutes())
    + pad(d.getSeconds())
    + "Z"
  );
}

const RESEARCH_CSV_FIELD_NAMES = [
  "reference_price", "percentage_change", "relative_volume", "float_shares",
  "short_float", "short_ratio", "shares_outstanding",
  "borrow_fee", "borrow_availability", "catalyst", "news_count", "sentiment",
  "sentiment_positive_count", "sentiment_neutral_count", "sentiment_negative_count",
  "sentiment_model_id", "latest_news_at", "latest_headline",
  "last", "bid", "ask", "previous_close", "open", "high", "low",
  "historical_close", "provider_volume", "shortable",
  "published_short_interest", "days_to_cover",
];

const RESEARCH_CSV_COLUMNS = [
  "symbol", "data_mode", "mode_label", "case_id", "candidate_id", "event_timestamp",
  "provider", "discovery_profile", "market_data_mode", "first_seen_at", "snapshot_at",
  "stale", "stale_reason", "reference_price", "reference_price_status",
  "reference_price_missing_reason", "last", "last_status", "bid", "bid_status", "ask",
  "ask_status", "previous_close", "previous_close_status", "open", "open_status", "high",
  "high_status", "low", "low_status", "historical_close", "historical_close_status",
  "provider_volume", "provider_volume_status", "shortable", "shortable_status",
  "published_short_interest", "published_short_interest_status", "days_to_cover",
  "days_to_cover_status", "percentage_change", "percentage_change_status",
  "percentage_change_missing_reason", "relative_volume", "relative_volume_status",
  "float_shares", "float_shares_status", "short_float", "short_float_status",
  "short_ratio", "short_ratio_status", "shares_outstanding", "shares_outstanding_status",
  "borrow_fee", "borrow_fee_status", "borrow_availability", "borrow_availability_status",
  "catalyst", "catalyst_status", "news_count", "news_count_status", "latest_news_at",
  "latest_news_at_status", "latest_headline", "latest_headline_status", "sentiment",
  "sentiment_status", "sentiment_positive_count", "sentiment_positive_count_status",
  "sentiment_neutral_count", "sentiment_neutral_count_status", "sentiment_negative_count",
  "sentiment_negative_count_status", "sentiment_model_id", "sentiment_model_id_status",
  "pass_count", "fail_count", "unknown_count", "evidence_coverage", "research_detection",
  "outcome_status", "freshness", "global_preflight_status", "phase3a_request_id",
  "phase3a_result_id",
];

function researchField(row, name) {
  return (row.fields || {})[name] || {};
}

function researchRowToCsvRecord(row) {
  const counts = (row.phase3a && row.phase3a.counts) || {};
  const pctField = researchField(row, "percentage_change");
  const record = {
    symbol: row.symbol,
    data_mode: row.data_mode,
    mode_label: row.mode_label || "",
    case_id: row.case_id || "",
    candidate_id: row.candidate_id || "",
    event_timestamp: row.last_updated || "",
    provider: pctField.provider || row.provider || "",
    discovery_profile: row.discovery_profile || "",
    market_data_mode: row.market_data_mode || "",
    first_seen_at: row.first_seen_at || "",
    snapshot_at: row.snapshot_at || "",
    stale: row.stale == null ? "" : String(Boolean(row.stale)),
    stale_reason: row.stale_reason || "",
    pass_count: counts.PASS || 0,
    fail_count: counts.FAIL || 0,
    unknown_count: counts.UNKNOWN || 0,
    evidence_coverage: (row.evidence_coverage && row.evidence_coverage.label) || "",
    research_detection: (row.research_detection && row.research_detection.status) || "",
    outcome_status: (row.outcome && row.outcome.status) || "",
    freshness: row.freshness || "",
    global_preflight_status: row.global_preflight_status || "",
    phase3a_request_id: "",
    phase3a_result_id: "",
  };
  RESEARCH_CSV_FIELD_NAMES.forEach((name) => {
    const field = researchField(row, name);
    record[name] = field.value == null ? "" : field.value;
    record[name + "_status"] = field.status || "";
    if (name === "percentage_change") {
      record.percentage_change_missing_reason = field.missing_reason || "";
    }
    if (name === "reference_price") {
      record.reference_price_missing_reason = field.missing_reason || "";
    }
  });
  return record;
}

function researchRowsToCsv(rows) {
  const lines = [RESEARCH_CSV_COLUMNS.join(",")];
  rows.forEach((row) => {
    const record = researchRowToCsvRecord(row);
    lines.push(RESEARCH_CSV_COLUMNS.map((col) => csvEscape(record[col])).join(","));
  });
  return lines.join("\n");
}

function showToast(message, isError, durationMs) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  toast.style.cssText = [
    "padding:10px 16px;border-radius:4px;font-size:13px;max-width:400px;",
    "box-shadow:0 2px 12px rgba(0,0,0,.4);animation:toast-in .25s ease-out;",
    isError ? "background:#2a1616;color:#ff9d9d;border:1px solid #cc4b4b;" : "background:#12291d;color:#7fe0a6;border:1px solid #2f9e5e;"
  ].join("");
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity .3s";
    setTimeout(() => toast.remove(), 300);
  }, durationMs || 4000);
}

const styleSheet = document.createElement("style");
styleSheet.textContent = "@keyframes toast-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}";
document.head.appendChild(styleSheet);
