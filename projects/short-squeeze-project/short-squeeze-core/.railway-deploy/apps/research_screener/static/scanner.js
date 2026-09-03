"use strict";

const state = {
  rows: [],
  filteredRows: [],
  selected: null,
  summary: null,
  providerCaps: null,
  autoTimer: null,
  sortKey: null,
  sortDesc: false,
  mode: "FROZEN",
  triageFilter: "",
  blockerFilter: null,
  blockerOpen: false,
  newsPanelMode: (function () {
    try {
      return localStorage.getItem("scannerNewsPanelMode") || "compact";
    } catch (e) {
      return "compact";
    }
  })(),
  newsMeta: null,
  diagnosticsOpen: false,
};

/* ------------------------------------------------------------------ fetching */
/* getJSON, setStatus, ago, CLASS_COLORS, PRESSURE_COLORS, pressureColor — provided by shared.js */

/* ------------------------------------------------------------------ render table */

function cv(row, name) {
  const cell = (row.fields || {})[name];
  return cell && cell.status === "KNOWN" ? cell.value : null;
}

function cf(row, name) {
  return (row.fields || {})[name] || null;
}

var DTC_FIELD_CASCADE = ["days_to_cover", "short_ratio", "short_ratio_provider"];

function finiteNumber(value) {
  if (value == null || value === "") return null;
  var n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function numericKnownValue(row, name) {
  var cell = cf(row, name);
  if (!cell || cell.status !== "KNOWN") return null;
  return finiteNumber(cell.value);
}

function daysToCoverValue(row) {
  for (var i = 0; i < DTC_FIELD_CASCADE.length; i++) {
    var n = numericKnownValue(row, DTC_FIELD_CASCADE[i]);
    if (n != null) return n;
  }
  return null;
}

function daysToCoverField(row) {
  for (var i = 0; i < DTC_FIELD_CASCADE.length; i++) {
    var cell = cf(row, DTC_FIELD_CASCADE[i]);
    if (cell && cell.status === "KNOWN" && finiteNumber(cell.value) != null) return cell;
  }
  return cf(row, "days_to_cover");
}

function isEvaluable(row) {
  var c = classification(row);
  return c !== "UNEVALUABLE" && c !== "CONFLICTED";
}

/** Matches backend summary.readiness.actionable_candidate_count (current-rule evaluable). */
function hasEvaluableRules(row) {
  return Number(dataQuality(row).evaluable_rule_count || 0) > 0;
}

function isActionableCandidate(row) {
  return hasEvaluableRules(row) || isEvaluable(row);
}

function actionableCountFromRows(rows) {
  var readiness = state.summary && state.summary.readiness;
  if (readiness && readiness.actionable_candidate_count != null) {
    return Number(readiness.actionable_candidate_count);
  }
  return rows.filter(hasEvaluableRules).length;
}

function transportReadiness() {
  if (state.mode !== "CURRENT") {
    return {
      live: false,
      detail: "Frozen research mode — live market transport is not used.",
    };
  }
  var conn = state.summary && state.summary.connection;
  var connStatus = conn ? String(conn.status || "").toUpperCase() : "";
  if (connStatus === "CONNECTED") {
    var port = conn.port != null ? conn.port : "?";
    return { live: true, detail: "IB Gateway connected (port " + port + ")." };
  }
  var caps = (state.providerCaps && state.providerCaps.providers) || {};
  var capLive = Object.keys(caps).filter(function (id) {
    return !!(caps[id] && caps[id].connected);
  });
  if (capLive.length) {
    return {
      live: true,
      detail: capLive.length + " configured provider(s) live: " + capLive.join(", ") + ".",
    };
  }
  var summaryProviders = (state.summary && state.summary.providers) || null;
  if (Array.isArray(summaryProviders)) {
    var ok = summaryProviders.filter(function (entry) {
      if (String(entry.state || "").toUpperCase() !== "OK") return false;
      var label = String(entry.surface || entry.name || "").toLowerCase();
      return (
        label.indexOf("gateway") !== -1 ||
        label.indexOf("scanner") !== -1 ||
        label.indexOf("quote") !== -1 ||
        label.indexOf("historical") !== -1
      );
    });
    if (ok.length) {
      return {
        live: true,
        detail: ok.map(function (e) { return e.surface || e.name; }).join(", ") + " OK.",
      };
    }
  } else if (summaryProviders && typeof summaryProviders === "object") {
    var connected = Object.keys(summaryProviders).filter(function (id) {
      var p = summaryProviders[id] || {};
      return !!(p.connected || p.connection_ready);
    });
    if (connected.length) {
      return {
        live: true,
        detail: connected.length + " provider surface(s) connected.",
      };
    }
  }
  return {
    live: false,
    detail: "Live data path not confirmed — check IB Gateway and provider configuration.",
  };
}

function fieldIsKnown(row, name) {
  var field = cf(row, name);
  return !!(field && field.status === "KNOWN");
}

function hasMissingCoreShortInterest(row) {
  // Borrow fee is optional in live mode; do not treat NOT_CONFIGURED as missing core SI.
  var hasPublishedSi = fieldIsKnown(row, "published_short_interest") || fieldIsKnown(row, "short_float");
  var hasDaysToCover = fieldIsKnown(row, "days_to_cover");
  return !hasPublishedSi || !hasDaysToCover;
}

function isInsufficient(row) {
  var cat = coverageCategory(row);
  if (cat === "insufficient" || cat === "none") return true;
  if (row.pressure == null || row.ignition == null) return true;
  return false;
}

function dataQuality(row) {
  return row && row.data_quality ? row.data_quality : {};
}

function bucketCountForRow(row, bucket) {
  var buckets = dataQuality(row).missing_evidence_buckets || [];
  for (var i = 0; i < buckets.length; i += 1) {
    if (buckets[i] && buckets[i].bucket === bucket) {
      return Number(buckets[i].missing_field_count || 0);
    }
  }
  return 0;
}

function hasCause(row, cause) {
  var causes = dataQuality(row).cause_summaries || [];
  return causes.indexOf(cause) !== -1;
}

function missingLabel(field, fallbackLabel) {
  if (!field) {
    return { label: fallbackLabel || "Missing", tip: "No evidence cell returned." };
  }
  if (field.status === "KNOWN") return null;
  var code = String(field.missing_reason_code || "").toUpperCase();
  var reason = String(field.missing_reason || "");
  var reasonLower = reason.toLowerCase();
  var label = field.status.replace(/_/g, " ");
  if (field.status === "NOT_CONFIGURED") {
    if (reasonLower.indexOf("not connected") !== -1 || reasonLower.indexOf("disconnected") !== -1) label = "Provider disconnected";
    else if (code.indexOf("NOT_AVAILABLE") !== -1 || code.indexOf("NOT_CONFIGURED") !== -1) label = "Field not published";
    else label = "Not configured";
  } else if (field.status === "UNAVAILABLE") {
    label = "Permission unavailable";
  } else if (field.status === "UNKNOWN") {
    if (code.indexOf("NO_BARS") !== -1 || code.indexOf("STALE") !== -1) label = "Stale snapshot";
    else label = "Awaiting ticks";
  } else if (field.status === "NOT_COLLECTED") {
    label = "Not collected";
  } else if (field.status === "BLOCKED") {
    label = "Blocked";
  }
  var bits = [];
  bits.push("Status: " + field.status);
  if (field.missing_reason) bits.push(field.missing_reason);
  if (field.missing_reason_code) bits.push("Code: " + field.missing_reason_code);
  if (field.provider) bits.push("Provider: " + field.provider);
  return { label: label, tip: bits.join(" \u00b7 ") };
}

function appendMissingLabel(td, field, fallbackLabel) {
  var m = missingLabel(field, fallbackLabel);
  if (!m) return false;
  var span = document.createElement("span");
  span.className = "muted missing-field-label";
  span.textContent = m.label;
  if (m.tip) span.title = m.tip;
  td.appendChild(span);
  return true;
}

function classification(row) {
  const methods = row.methodologies || [];
  const adam = methods.find(function (m) { return m.methodology_id === "adam_evidence_gated_prime.v1"; });
  return adam ? adam.classification : "UNEVALUABLE";
}

function methodologyCoverage(row) {
  return row.methodology_coverage || {};
}

function coverageFieldFraction(row) {
  var cov = methodologyCoverage(row);
  var avail = cov.total_fields_available;
  var req = cov.total_fields_required;
  if (avail != null && req != null && req > 0) {
    return { available: avail, required: req };
  }
  var pAvail = cov.pressure_fields_available;
  var pReq = cov.pressure_fields_required;
  var iAvail = cov.ignition_fields_available;
  var iReq = cov.ignition_fields_required;
  if (pAvail != null && pReq != null && iAvail != null && iReq != null && pReq + iReq > 0) {
    return { available: pAvail + iAvail, required: pReq + iReq };
  }
  return null;
}

function coveragePct(row) {
  var cov = methodologyCoverage(row);
  if (cov.percent != null) return cov.percent;
  if (cov.field_coverage_percent != null) return cov.field_coverage_percent;
  var frac = coverageFieldFraction(row);
  if (!frac || frac.required <= 0) return null;
  return Math.round(1000 * frac.available / frac.required) / 10;
}

function coverageCategoryShortName(category) {
  if (!category) return null;
  var c = String(category).toUpperCase();
  if (c === "HIGH_COVERAGE") return "HIGH";
  if (c === "MODERATE_COVERAGE") return "MODERATE";
  if (c === "LOW_COVERAGE") return "LOW";
  if (c === "INSUFFICIENT_EVIDENCE") return "INSUFFICIENT";
  if (c === "CONFLICTED") return "CONFLICTED";
  return c.replace(/_COVERAGE$/, "").replace(/_/g, " ");
}

function coverageCategory(row) {
  var cov = methodologyCoverage(row);
  var cat = cov.category;
  if (cat) {
    var c = String(cat).toUpperCase();
    if (c === "HIGH_COVERAGE") return "high";
    if (c === "MODERATE_COVERAGE") return "moderate";
    if (c === "LOW_COVERAGE") return "low";
    if (c === "INSUFFICIENT_EVIDENCE" || c === "CONFLICTED") return "insufficient";
  }
  var pct = coveragePct(row);
  if (pct == null) return "none";
  if (pct >= 85) return "high";
  if (pct >= 70) return "moderate";
  if (pct >= 50) return "low";
  return "insufficient";
}

function coverageLabel(row) {
  var short = coverageCategoryShortName(methodologyCoverage(row).category);
  var frac = coverageFieldFraction(row);
  if (!frac && !short) return "\u2014";
  var parts = [];
  if (short) parts.push(short);
  if (frac) parts.push(frac.available + "/" + frac.required);
  return parts.join(" \u00b7 ");
}

function coverageTooltip(row) {
  var cov = methodologyCoverage(row);
  var bits = [];
  if (cov.pressure_fields_available != null && cov.pressure_fields_required != null) {
    bits.push("Pressure " + cov.pressure_fields_available + "/" + cov.pressure_fields_required);
  }
  if (cov.ignition_fields_available != null && cov.ignition_fields_required != null) {
    bits.push("Ignition " + cov.ignition_fields_available + "/" + cov.ignition_fields_required);
  }
  var ruleCov = row.evidence_coverage;
  if (ruleCov && ruleCov.label) bits.push("Rules: " + ruleCov.label);
  else if (ruleCov && ruleCov.supported != null && ruleCov.total != null) {
    bits.push("Rules: " + ruleCov.supported + "/" + ruleCov.total + " supported");
  }
  if (cov.weight_coverage_percent != null) {
    bits.push("Weight coverage " + cov.weight_coverage_percent + "%");
  }
  var pct = coveragePct(row);
  if (pct != null) bits.push("Field coverage " + pct + "%");
  return bits.join(" \u00b7 ");
}

function sentimentLabel(row) {
  const s = cf(row, "sentiment");
  if (!s || s.status !== "KNOWN") return null;
  var v = s.value;
  if (v === "positive") return "POSITIVE";
  if (v === "neutral") return "NEUTRAL";
  if (v === "negative") return "NEGATIVE";
  if (v === "mixed" || v === "MIXED") return "MIXED";
  return v ? String(v).toUpperCase() : null;
}

function sentimentColor(label) {
  if (!label) return "#4a5568";
  if (label === "POSITIVE") return "#56d68b";
  if (label === "NEGATIVE") return "#ff7d7d";
  if (label === "MIXED") return "#ffca57";
  return "#8b98a9";
}

function newsCount(row) {
  var n = cf(row, "news_count");
  if (!n || n.status !== "KNOWN") return null;
  return n.value;
}

/* ------------------------------------------------------------------ columns */

var SCANNER_COLUMNS = [
  { label: "SYMBOL", key: "symbol", sortable: true, primary: true },
  { label: "PRICE", key: "price", sortable: true },
  { label: "CHANGE %", key: "percentage_change", sortable: true, emphasis: true },
  { label: "REL VOL", key: "relative_volume", sortable: true },
  { label: "DTC", key: "days_to_cover", sortable: true },
  { label: "NEWS", key: "news", sortable: true },
  { label: "SENTIMENT", key: "sentiment", sortable: true },
  { label: "PRESSURE", key: "pressure", sortable: true, emphasis: true },
  { label: "IGNITION", key: "ignition", sortable: true, emphasis: true },
  { label: "EVIDENCE", key: "evidence_coverage", sortable: true, emphasis: true,
    headerHint: "ADAM inputs present for Pressure/Ignition scoring. Hover a cell for rules, field %, and missing buckets." },
  { label: "CLASSIFICATION", key: "classification", sortable: true, emphasis: true },
];

/* ------------------------------------------------------------------ render table */

function valueFor(row, key) {
  switch (key) {
    case "symbol": return row.symbol;
    case "price": return cv(row, "last") || cv(row, "finviz_price") || cv(row, "finnhub_price");
    case "percentage_change": {
      // 1. Canonical metric from IBKR
      var pc = cv(row, "percentage_change");
      if (pc !== null) return pc;
      // 2. Finviz Elite export change %
      var fvpc = cv(row, "finviz_change_pct");
      if (fvpc !== null) return fvpc;
      // 3. Computed: (last price - previous close) / previous close
      var current = cv(row, "last") || cv(row, "finviz_price") || cv(row, "finnhub_price");
      var prev = cv(row, "previous_close");
      if (current != null && prev != null && prev !== 0) {
        return ((current - prev) / prev) * 100;
      }
      return null;
    }
    case "relative_volume": {
      var rv = cv(row, "relative_volume");
      if (rv !== null) return rv;
      return cv(row, "relative_volume_provider");
    }
    case "float_shares": return cv(row, "float_shares");
    case "short_float": return cv(row, "short_float");
    case "days_to_cover": return daysToCoverValue(row);
    case "pressure": return row.pressure;
    case "ignition": return row.ignition;
    case "evidence_coverage": return coveragePct(row);
    case "news": return newsCount(row);
    case "sentiment": return sentimentLabel(row);
    case "classification": return classification(row);
    case "why_listed": return (row.why_listed || []).join("; ");
    case "updated": return ago(row.last_updated) || row.last_updated;
    default: return null;
  }
}

function cellContent(row, col) {
  var td = document.createElement("td");
  td.classList.add("sc-" + col.key);

  if (col.primary) td.classList.add("primary");
  if (col.secondary) td.classList.add("secondary");
  if (col.emphasis) td.classList.add("emphasis");

  var value = valueFor(row, col.key);

  if (col.key === "symbol") {
    var rowCls = classification(row);
    var symWrap = document.createElement("span");
    symWrap.className = "symbol-cell";
    var dot = document.createElement("span");
    dot.className = "cls-dot";
    dot.style.backgroundColor = classificationColor(rowCls);
    dot.title = rowCls.replace(/_/g, " ");
    symWrap.appendChild(dot);
    var strong = document.createElement("strong");
    strong.textContent = row.symbol;
    symWrap.appendChild(strong);
    td.appendChild(symWrap);
    return td;
  }

  if (col.key === "classification") {
    var cls = value || "UNEVALUABLE";
    var clsSpan = document.createElement("span");
    clsSpan.className = "class-badge";
    clsSpan.style.backgroundColor = classificationColor(cls);
    clsSpan.textContent = cls.replace(/_/g, " ");
    td.appendChild(clsSpan);
    td.style.whiteSpace = "nowrap";
    return td;
  }

  if (col.key === "pressure" || col.key === "ignition") {
    if (value == null) {
      appendMissingLabel(td, null, "Insufficient inputs");
      return td;
    }
    var v = Number(value);
    var display = Math.round(v);
    var color = pressureColor(v);
    var wrap = document.createElement("div");
    wrap.className = "score-cell";
    var track = document.createElement("div");
    track.className = "score-track";
    track.setAttribute("aria-hidden", "true");
    var bar = document.createElement("div");
    bar.className = "score-bar";
    bar.style.width = Math.min(100, Math.max(0, display)) + "%";
    bar.style.backgroundColor = color;
    track.appendChild(bar);
    var label = document.createElement("span");
    label.className = "score-label";
    label.textContent = String(display);
    label.style.color = color;
    wrap.appendChild(track);
    wrap.appendChild(label);
    td.appendChild(wrap);
    td.title = col.key === "pressure" ? "Short pressure dimension" : "Ignition / momentum dimension";
    return td;
  }

  if (col.key === "evidence_coverage") {
    var cat = coverageCategory(row);
    var evSpan = document.createElement("span");
    evSpan.className = "coverage-pill cov-" + cat;
    evSpan.textContent = coverageLabel(row);
    var tip = coverageTooltip(row);
    if (tip) evSpan.title = tip;
    else if (cat === "insufficient") evSpan.title = "Insufficient evidence coverage";
    td.appendChild(evSpan);
    return td;
  }

  if (col.key === "sentiment") {
    var sentSpan = document.createElement("span");
    if (!value) {
      var sentField = cf(row, "sentiment");
      sentSpan.textContent = (missingLabel(sentField, "No sentiment") || {}).label || "No sentiment";
      sentSpan.className = "muted";
      sentSpan.title = sentField && sentField.missing_reason ? sentField.missing_reason : "";
    } else {
      sentSpan.textContent = value;
      sentSpan.style.color = sentimentColor(value);
      sentSpan.style.fontWeight = "700";
      sentSpan.style.letterSpacing = "0.04em";
    }
    td.appendChild(sentSpan);
    return td;
  }

  if (col.key === "news") {
    td.classList.add("news-snippet-cell");
    var headlineField = cf(row, "latest_headline");
    var headlineText = headlineField && headlineField.status === "KNOWN"
      ? String(headlineField.value || "") : "";
    if (headlineText) {
      var snippet = headlineText.length > 72 ? headlineText.substring(0, 69) + "..." : headlineText;
      td.title = headlineText;
      var newsMain = document.createElement("span");
      newsMain.className = "news-snippet-main";
      newsMain.textContent = snippet;
      td.appendChild(newsMain);
      var latestAt = cf(row, "latest_news_at");
      if (latestAt && latestAt.status === "KNOWN" && latestAt.value) {
        var sub = document.createElement("span");
        sub.className = "news-snippet-ago muted";
        sub.textContent = ago(latestAt.value) || String(latestAt.value);
        td.appendChild(sub);
      }
      if (value != null && value > 1) {
        var badge = document.createElement("span");
        badge.className = "news-count-badge muted";
        badge.textContent = String(value);
        badge.title = value + " headlines";
        td.appendChild(badge);
      }
      return td;
    }
    if (value == null) {
      appendMissingLabel(td, cf(row, "news_count"), "No headlines");
      td.className = td.className + " muted";
      return td;
    }
    td.textContent = value + (value === 1 ? " headline" : " headlines");
    return td;
  }

  if (col.key === "days_to_cover") {
    var dtcField = daysToCoverField(row);
    if (value == null) {
      appendMissingLabel(td, dtcField, "No DTC");
      td.className = td.className + " muted";
      return td;
    }
    var dtcNum = Number(value);
    td.textContent = dtcNum.toFixed(1) + "d";
    if (dtcField && dtcField.provider) td.title = "Days to cover · " + dtcField.provider;
    return td;
  }

  if (col.key === "percentage_change") {
    if (value == null) {
      appendMissingLabel(td, cf(row, "percentage_change"), "No return data");
      td.className = td.className + " muted";
      return td;
    }
    var changeColor = value >= 0 ? "#56d68b" : "#ff7d7d";
    td.textContent = (value >= 0 ? "+" : "") + value.toFixed(2) + "%";
    td.style.color = changeColor;
    td.style.fontWeight = "700";
    return td;
  }

  if (col.key === "why_listed") {
    var reason = value || MISSING;
    td.textContent = reason.length > 60 ? reason.substring(0, 57) + "..." : reason;
    td.title = reason;
    if (!value) td.className = td.className + " muted";
    td.classList.add("why-cell");
    return td;
  }

  if (value === null || value === undefined) {
    appendMissingLabel(td, cf(row, col.key), "Missing");
    td.className = td.className + " muted";
    return td;
  }

  td.textContent = typeof value === "number" ? Number(value).toLocaleString() : String(value);
  return td;
}

var SORT_DESC_FIRST_KEYS = [
  "percentage_change", "pressure", "ignition", "relative_volume",
  "short_float", "days_to_cover", "news",
];

var CLASSIFICATION_SORT_ORDER = {
  PRIME: 0, SUBPRIME: 1, WATCH: 2, CONFLICTED: 3, NOT_QUALIFIED: 4, UNEVALUABLE: 5,
};

var SENTIMENT_SORT_ORDER = {
  POSITIVE: 0, MIXED: 1, NEUTRAL: 2, NEGATIVE: 3,
};

var NUMERIC_SORT_KEYS = {
  price: true,
  percentage_change: true,
  relative_volume: true,
  float_shares: true,
  short_float: true,
  days_to_cover: true,
  pressure: true,
  ignition: true,
  evidence_coverage: true,
  news: true,
};

function parseFilterNumber(raw) {
  if (raw === "" || raw == null) return null;
  var n = parseFloat(raw);
  return Number.isFinite(n) ? n : null;
}

function compareSortValues(av, bv, descending) {
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  var aNum = finiteNumber(av);
  var bNum = finiteNumber(bv);
  if (aNum != null && bNum != null) {
    return descending ? bNum - aNum : aNum - bNum;
  }
  var as = String(av);
  var bs = String(bv);
  return descending ? bs.localeCompare(as) : as.localeCompare(bs);
}

function sortValueFor(row, key) {
  if (key === "updated") {
    var ts = row.last_updated ? Date.parse(row.last_updated) : NaN;
    return Number.isFinite(ts) ? ts : null;
  }
  if (key === "classification") {
    var cls = classification(row);
    return CLASSIFICATION_SORT_ORDER[cls] != null ? CLASSIFICATION_SORT_ORDER[cls] : 9;
  }
  if (key === "sentiment") {
    var label = sentimentLabel(row);
    if (!label) return null;
    return SENTIMENT_SORT_ORDER[label] != null ? SENTIMENT_SORT_ORDER[label] : 9;
  }
  var value = valueFor(row, key);
  if (value != null && NUMERIC_SORT_KEYS[key]) {
    var numeric = finiteNumber(value);
    if (numeric != null) return numeric;
  }
  return value;
}

function renderHead() {
  var head = el("scanner-head");
  head.textContent = "";
  SCANNER_COLUMNS.forEach(function (col) {
    var th = document.createElement("th");
    th.textContent = col.label;
    if (col.headerHint) th.title = col.headerHint;
    if (col.sortable) {
      th.classList.add("sortable");
      th.setAttribute("data-key", col.key);
      if (state.sortKey === col.key) {
        th.classList.add(state.sortDesc ? "sorted-desc" : "sorted-asc");
      }
      th.addEventListener("click", function () {
        if (state.sortKey === col.key) {
          state.sortDesc = !state.sortDesc;
        } else {
          state.sortKey = col.key;
          state.sortDesc = SORT_DESC_FIRST_KEYS.indexOf(col.key) !== -1;
        }
        renderHead();
        renderRows(state.filteredRows);
      });
    }
    if (col.primary) th.classList.add("primary");
    if (col.secondary) th.classList.add("secondary");
    if (col.emphasis) th.classList.add("emphasis");
    head.appendChild(th);
  });
}

function sortRows(rows) {
  if (!state.sortKey) return defaultSort(rows);
  var key = state.sortKey;
  var known = [];
  var missing = [];
  rows.forEach(function (row) {
    var v = sortValueFor(row, key);
    if (v == null || v === undefined) missing.push(row);
    else known.push(row);
  });
  known.sort(function (a, b) {
    return compareSortValues(sortValueFor(a, key), sortValueFor(b, key), state.sortDesc);
  });
  return known.concat(missing);
}

function defaultSort(rows) {
  var order = { PRIME: 0, SUBPRIME: 1, WATCH: 2, CONFLICTED: 3, NOT_QUALIFIED: 4, UNEVALUABLE: 5 };
  return rows.slice().sort(function (a, b) {
    var aCls = classification(a);
    var bCls = classification(b);
    return (order[aCls] || 9) - (order[bCls] || 9)
      || ((b.pressure || 0) + (b.ignition || 0)) - ((a.pressure || 0) + (a.ignition || 0));
  });
}

function classificationColor(cls) {
  return CLASS_COLORS[cls] || CLASS_COLORS.UNEVALUABLE;
}

function setClassificationFilter(cls) {
  var select = el("filter-classification");
  if (!select) return;
  select.value = cls || "";
  state.filteredRows = applyFilters(state.rows);
  renderRows(state.filteredRows);
}

function renderRows(rows) {
  var body = el("scanner-body");
  body.textContent = "";
  rows = sortRows(rows);
  renderClassificationLegend();
  if (!rows.length) {
    var tr = document.createElement("tr");
    var td = document.createElement("td");
    td.colSpan = SCANNER_COLUMNS.length;
    td.className = "muted";
    td.style.textAlign = "center";
    td.textContent = "No candidates.";
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  rows.forEach(function (row) {
    var cls = classification(row);

    var tr = document.createElement("tr");
    tr.className = "clickable cls-" + cls;
    if (hasEvaluableRules(row)) tr.classList.add("rule-evaluable");
    if (state.selected === row.symbol) tr.classList.add("selected");
    tr.addEventListener("click", function () { selectSymbol(row.symbol); });
    SCANNER_COLUMNS.forEach(function (col) {
      tr.appendChild(cellContent(row, col));
    });
    body.appendChild(tr);
  });
}

/* ------------------------------------------------------------------ summary */
function renderClassificationLegend() {
  var legend = el("classification-legend");
  if (!legend) return;
  legend.textContent = "";

  var rows = state.rows;
  var counts = {};
  rows.forEach(function (row) {
    var c = classification(row);
    counts[c] = (counts[c] || 0) + 1;
  });

  var order = ["PRIME", "SUBPRIME", "WATCH", "NOT_QUALIFIED", "UNEVALUABLE", "CONFLICTED", "REFERENCE_DEFINITION_INCOMPLETE"];
  var total = rows.length;
  var activeFilter = el("filter-classification") ? el("filter-classification").value : "";

  var totalSpan = document.createElement("span");
  totalSpan.className = "legend-total";
  totalSpan.textContent = total + " Candidates";
  legend.appendChild(totalSpan);

  order.forEach(function (cls) {
    var n = counts[cls] || 0;
    var badge = document.createElement("span");
    badge.className = "legend-badge" + (activeFilter === cls ? " active" : "");
    badge.style.backgroundColor = classificationColor(cls);
    badge.textContent = cls.replace(/_/g, " ") + " " + n;
    badge.title = "Click to filter table to " + cls.replace(/_/g, " ") + " (" + n + ")";
    badge.setAttribute("role", "button");
    badge.tabIndex = 0;
    badge.addEventListener("click", function () {
      var select = el("filter-classification");
      var current = select ? select.value : "";
      setClassificationFilter(current === cls ? "" : cls);
    });
    badge.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        var select = el("filter-classification");
        var current = select ? select.value : "";
        setClassificationFilter(current === cls ? "" : cls);
      }
    });
    legend.appendChild(badge);
  });
}

function renderSummary(rows) {
  renderReadiness(rows);
  renderTriageFilters(rows);
  syncBlockerPanelVisibility();
  if (state.diagnosticsOpen) renderBlockerPanel(rows);
}

function renderReadiness(rows) {
  var pill = el("scan-status-pill");
  if (!pill) return;
  var transport = transportReadiness();
  var readiness = (state.summary && state.summary.readiness) || null;
  var ruleEvaluable = actionableCountFromRows(rows);
  var candidateCount = readiness
    ? Number(readiness.candidate_count || rows.length)
    : rows.length;
  var modeLabel = state.mode === "CURRENT" ? "Live" : "Frozen";
  var headline = modeLabel + " \u00b7 " + ruleEvaluable + "/" + candidateCount + " evaluable";
  pill.textContent = headline;
  var tone = ruleEvaluable > 0 ? (transport.live || state.mode !== "CURRENT" ? "ok" : "warn") : "bad";
  pill.className = "scan-status-pill " + tone;
  pill.title = transport.detail
    + "\n" + ruleEvaluable + "/" + candidateCount + " candidates with evaluable current rules."
    + "\n" + rows.filter(isEvaluable).length + " fully classified by methodology.";
  if (readiness && readiness.unevaluable_candidate_count != null) {
    pill.title += "\nUNEVALUABLE (backend): " + readiness.unevaluable_candidate_count;
  }
}

function syncBlockerPanelVisibility() {
  var panel = el("blocker-panel");
  if (panel) panel.hidden = !state.diagnosticsOpen;
}

function buildUnevaluableDiagnostics(rows) {
  var readiness = (state.summary && state.summary.readiness) || null;
  if (readiness && (readiness.top_unevaluable_causes || []).length) {
    return ["Top UNEVALUABLE causes (backend):"]
      .concat(readiness.top_unevaluable_causes.map(function (item) {
        return item.cause + ": " + item.candidate_count;
      }))
      .join("\n");
  }
  return "UNEVALUABLE diagnostics are unavailable in summary.readiness.";
}

function renderBanner(mode) {
  var banners = el("banners");
  banners.textContent = "";
  if (mode === "FROZEN") {
    var b = document.createElement("div");
    b.className = "banner warn";
    b.textContent = "FROZEN \u2014 pre-computed research; live discovery unavailable on this deployment.";
    banners.appendChild(b);
  }
  // In live mode (or empty string), no banner — clean interface for Railway
}

function renderTriageFilters(rows) {
  var wrap = el("triage-filters");
  if (!wrap) return;
  wrap.textContent = "";
  var defs = [
    { id: "", label: "All", count: rows.length },
    { id: "evaluable", label: "Rule-evaluable", count: rows.filter(hasEvaluableRules).length },
    { id: "stale", label: "Stale", count: rows.filter(function (row) { return !!row.stale; }).length },
    { id: "insufficient", label: "Insufficient", count: rows.filter(isInsufficient).length },
    { id: "missing_core_si", label: "Missing Core SI", count: rows.filter(hasMissingCoreShortInterest).length },
  ];
  defs.forEach(function (def) {
    var btn = document.createElement("button");
    var tone = "";
    if (def.id === "stale" && def.count > 0) tone = " warn";
    else if (def.id === "insufficient" && def.count > 0) tone = " warn";
    else if (def.id === "missing_core_si" && def.count > 0) tone = " bad";
    btn.className = "triage-btn" + tone + (state.triageFilter === def.id ? " active" : "");
    btn.type = "button";
    btn.setAttribute("data-triage", def.id);
    btn.textContent = def.label + " (" + def.count + ")";
    wrap.appendChild(btn);
  });
}

function aggregateRowBlockers(rows) {
  var causeCounts = {};
  var bucketCounts = {};
  rows.forEach(function (row) {
    var dq = dataQuality(row);
    (dq.cause_summaries || []).forEach(function (cause) {
      causeCounts[cause] = (causeCounts[cause] || 0) + 1;
    });
    (dq.missing_evidence_buckets || []).forEach(function (bucketItem) {
      var key = bucketItem.bucket;
      if (!key) return;
      bucketCounts[key] = (bucketCounts[key] || 0) + Number(bucketItem.missing_field_count || 0);
    });
  });
  var causes = Object.keys(causeCounts).map(function (key) {
    return { key: key, count: causeCounts[key] };
  }).sort(function (a, b) { return b.count - a.count || a.key.localeCompare(b.key); });
  var buckets = Object.keys(bucketCounts).map(function (key) {
    return { key: key, count: bucketCounts[key] };
  }).sort(function (a, b) { return b.count - a.count || a.key.localeCompare(b.key); });
  return { causes: causes, buckets: buckets };
}

function renderBlockerPanel(rows) {
  var content = el("blocker-content");
  var toggle = el("blocker-toggle");
  if (!content || !toggle) return;
  toggle.setAttribute("aria-expanded", state.blockerOpen ? "true" : "false");
  content.hidden = !state.blockerOpen;
  content.textContent = "";
  if (!state.blockerOpen) return;

  var agg = aggregateRowBlockers(rows);
  if (!agg.causes.length && !agg.buckets.length) {
    var empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "No blocker diagnostics available.";
    content.appendChild(empty);
    return;
  }

  function buildGroup(title, type, items) {
    var group = document.createElement("div");
    group.className = "blocker-group";
    var heading = document.createElement("p");
    heading.className = "blocker-group-title";
    heading.textContent = title;
    group.appendChild(heading);

    var list = document.createElement("div");
    list.className = "blocker-list";
    items.forEach(function (item) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "blocker-chip";
      if (state.blockerFilter && state.blockerFilter.type === type && state.blockerFilter.key === item.key) {
        btn.classList.add("active");
      }
      btn.setAttribute("data-blocker-type", type);
      btn.setAttribute("data-blocker-key", item.key);
      btn.textContent = item.key + " (" + item.count + ")";
      list.appendChild(btn);
    });
    group.appendChild(list);
    return group;
  }

  content.appendChild(buildGroup("Cause Summaries", "cause", agg.causes));
  content.appendChild(buildGroup("Missing Buckets", "bucket", agg.buckets));
  if (state.blockerFilter) {
    var clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "blocker-chip blocker-chip-clear";
    clearBtn.setAttribute("data-blocker-clear", "1");
    clearBtn.textContent = "Clear blocker filter";
    content.appendChild(clearBtn);
  }
}

/* ------------------------------------------------------------------ filters */

function applyFilters(rows) {
  var cls = el("filter-classification").value;
  var sym = el("filter-symbol").value.trim().toUpperCase();
  var minPrice = parseFilterNumber(el("filter-min-price").value);
  var maxPrice = parseFilterNumber(el("filter-max-price").value);
  var minChange = parseFilterNumber(el("filter-min-change").value);
  var minRelvol = parseFilterNumber(el("filter-min-relvol").value);
  var minPressure = parseFilterNumber(el("filter-min-pressure").value);
  var minIgnition = parseFilterNumber(el("filter-min-ignition").value);
  var minCoverage = parseFilterNumber(el("filter-min-coverage").value);
  var newsFilter = el("filter-news").value;
  var sentimentFilter = el("filter-sentiment").value;
  var maxFloat = parseFilterNumber(el("filter-max-float").value);

  return rows.filter(function (row) {
    if (cls && classification(row) !== cls) return false;
    if (sym && row.symbol.indexOf(sym) === -1) return false;
    if (minPrice != null) {
      var p = valueFor(row, "price");
      if (p == null || p < minPrice) return false;
    }
    if (maxPrice != null) {
      var p2 = valueFor(row, "price");
      if (p2 == null || p2 > maxPrice) return false;
    }
    if (minChange != null) {
      var c = valueFor(row, "percentage_change");
      if (c == null || c < minChange) return false;
    }
    if (minRelvol != null) {
      var r = valueFor(row, "relative_volume");
      if (r == null || r < minRelvol) return false;
    }
    if (minPressure != null) {
      if (row.pressure == null || row.pressure < minPressure) return false;
    }
    if (minIgnition != null) {
      if (row.ignition == null || row.ignition < minIgnition) return false;
    }
    if (minCoverage != null) {
      var cov = coveragePct(row);
      if (cov == null || cov < minCoverage) return false;
    }
    if (newsFilter === "has") {
      var n = newsCount(row);
      if (n == null || n === 0) return false;
    }
    if (sentimentFilter) {
      var s = sentimentLabel(row);
      if (s !== sentimentFilter) return false;
    }
    if (maxFloat != null) {
      var f = cv(row, "float_shares");
      if (f == null || f > maxFloat) return false;
    }
    if (state.triageFilter === "evaluable" && !hasEvaluableRules(row)) return false;
    if (state.triageFilter === "stale" && !row.stale) return false;
    if (state.triageFilter === "insufficient" && !isInsufficient(row)) return false;
    if (state.triageFilter === "missing_core_si" && !hasMissingCoreShortInterest(row)) return false;
    if (state.blockerFilter) {
      if (state.blockerFilter.type === "cause" && !hasCause(row, state.blockerFilter.key)) return false;
      if (state.blockerFilter.type === "bucket" && bucketCountForRow(row, state.blockerFilter.key) <= 0) return false;
    }
    return true;
  });
}

/* ------------------------------------------------------------------ detail drawer */

function openDetail(symbol) {
  var overlay = el("detail-overlay");
  overlay.hidden = false;
  overlay.style.display = "flex";
  el("drawer-title").textContent = "Loading " + symbol + "...";
  el("drawer-body").textContent = "";
  buildDetail(symbol);
}

function closeDetail() {
  var overlay = el("detail-overlay");
  if (overlay) {
    overlay.hidden = true;
    overlay.style.display = "none";
  }
  state.selected = null;
  renderRows(state.filteredRows || []);
}

function selectSymbol(symbol) {
  state.selected = symbol;
  renderRows(state.filteredRows);
  openDetail(symbol);
}

function fieldLine(label, value, extra) {
  var div = document.createElement("div");
  div.className = "field-line";
  var k = document.createElement("span");
  k.className = "fl-key";
  k.textContent = label;
  var v = document.createElement("span");
  v.className = "fl-value";
  v.textContent = value === null || value === undefined || value === "" ? MISSING : String(value);
  div.appendChild(k);
  div.appendChild(v);
  if (extra) {
    var e = document.createElement("span");
    e.className = "fl-extra";
    e.textContent = " \u00b7 " + extra;
    div.appendChild(e);
  }
  return div;
}

function detailSection(title) {
  var h = document.createElement("h3");
  h.textContent = title;
  return h;
}

function detailGrid(children) {
  var div = document.createElement("div");
  div.className = "detail-grid-2col";
  children.forEach(function (c) { div.appendChild(c); });
  return div;
}

async function buildDetail(symbol) {
  var body = el("drawer-body");
  var title = el("drawer-title");
  body.textContent = "";
  title.textContent = "Loading " + symbol + "...";

  var detail;
  try {
    detail = await getJSON("/api/symbol?symbol=" + encodeURIComponent(symbol) + "&mode=" + state.mode);
  } catch (e) {
    body.appendChild(text(document.createElement("p"), "Unavailable: " + e.message));
    return;
  }

  if (detail.error) {
    body.appendChild(text(document.createElement("p"), detail.error));
    return;
  }

  var id = detail.identity || {};
  var row = state.rows.find(function (r) { return r.symbol === symbol; });
  var cls = row ? classification(row) : "UNEVALUABLE";

  title.textContent = id.symbol;
  if (id.contract && id.contract.long_name) {
    title.textContent += " \u2014 " + id.contract.long_name;
  }

  body.appendChild(detailSection("HEADER"));
  body.appendChild(detailGrid([
    fieldLine("Symbol", id.symbol),
    fieldLine("Price", cv(row || {}, "last"), "USD"),
    fieldLine("Change %", cv(row || {}, "percentage_change") != null ? (cv(row || {}, "percentage_change") >= 0 ? "+" : "") + cv(row || {}, "percentage_change").toFixed(2) + "%" : null),
    fieldLine("Classification", cls.replace(/_/g, " ")),
    fieldLine("Why Listed", (row && row.why_listed || []).join("; ")),
    fieldLine("Updated", ago(row && row.last_updated) || (row && row.last_updated)),
  ]));

  body.appendChild(detailSection("SHORT PRESSURE"));
  body.appendChild(detailGrid([
    fieldLine("Float", cv(row || {}, "float_shares") != null ? Number(cv(row || {}, "float_shares")).toLocaleString() : null),
    fieldLine("Short Float", cv(row || {}, "short_float") != null ? cv(row || {}, "short_float") + "%" : null),
    fieldLine("Days to Cover", daysToCoverValue(row || {})),
    fieldLine("Borrow Fee", cv(row || {}, "borrow_fee") != null ? cv(row || {}, "borrow_fee") + "%" : null),
  ]));

  body.appendChild(detailSection("IGNITION"));
  body.appendChild(detailGrid([
    fieldLine("Change %", cv(row || {}, "percentage_change") != null ? (cv(row || {}, "percentage_change") >= 0 ? "+" : "") + cv(row || {}, "percentage_change").toFixed(2) + "%" : null),
    fieldLine("Relative Volume", cv(row || {}, "relative_volume")),
    fieldLine("Market Mode", id.market_data_mode || id.data_mode),
  ]));

  var headlines = Array.isArray(detail.news) ? detail.news : [];
  if (!headlines.length) {
    var newsPayload = await getCachedNews(symbol);
    if (newsPayload && Array.isArray(newsPayload.headlines)) {
      headlines = newsPayload.headlines;
    }
  }
  body.appendChild(detailSection("NEWS"));
  var newsWrap = document.createElement("div");
  newsWrap.className = "detail-news-list";
  if (!headlines.length) {
    newsWrap.appendChild(text(document.createElement("p"), "No headlines available."));
    newsWrap.classList.add("muted");
  } else {
    headlines.slice(0, 12).forEach(function (item) {
      var line = document.createElement("div");
      line.className = "news-headline-line";
      var title = item.headline || item.title || "";
      if (item.url) {
        var link = document.createElement("a");
        link.className = "detail-news-link";
        link.href = item.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = title;
        line.appendChild(link);
      } else {
        line.textContent = title;
      }
      if (item.timestamp) {
        var meta = document.createElement("span");
        meta.className = "muted";
        meta.style.marginLeft = "8px";
        meta.textContent = ago(item.timestamp) || item.timestamp;
        line.appendChild(meta);
      }
      newsWrap.appendChild(line);
    });
  }
  body.appendChild(newsWrap);

  body.appendChild(detailSection("CATALYST / SENTIMENT"));
  var sentKnown = cf(row || {}, "sentiment");
  var dominantSent = sentimentLabel(row);
  if (!dominantSent && sentKnown && sentKnown.status !== "KNOWN") {
    dominantSent = (missingLabel(sentKnown, "No sentiment") || {}).label || MISSING;
  }
  function knownCount(name) {
    var f = cf(row || {}, name);
    return f && f.status === "KNOWN" ? f.value : MISSING;
  }
  body.appendChild(detailGrid([
    fieldLine("Dominant label", dominantSent || MISSING),
    fieldLine("Positive / Neutral / Negative",
      knownCount("sentiment_positive_count") + " / "
      + knownCount("sentiment_neutral_count") + " / "
      + knownCount("sentiment_negative_count")),
    fieldLine("Headline count", newsCount(row)),
    fieldLine("Latest headline", knownCount("latest_headline") !== MISSING
      ? knownCount("latest_headline") : null),
  ]));

  var advLink = document.createElement("p");
  var advA = document.createElement("a");
  advA.href = "/advanced";
  advA.textContent = "Open Advanced Analysis";
  advA.style.color = "var(--accent)";
  advA.style.fontWeight = "600";
  advLink.appendChild(advA);
  body.appendChild(advLink);
}

/* ------------------------------------------------------------------ screener */

async function loadAndRender(url, mode) {
  var payload;
  try {
    payload = await getJSON(url);
  } catch (e) {
    return null;
  }
  if (!payload || !payload.rows || !payload.rows.length) return null;

  state.rows = payload.rows || [];
  state.summary = payload.summary || null;
  state.mode = mode;

  var filtered = applyFilters(state.rows);
  state.filteredRows = filtered;
  renderSummary(state.rows);
  renderHead();
  renderRows(filtered);

  // Kick off news feed for current candidates
  startNewsFeed();

  return payload;
}

function startAutoRefresh() {
  if (state.autoTimer) { clearInterval(state.autoTimer); state.autoTimer = null; }
  state.autoTimer = setInterval(function () {
    if (state.mode === "CURRENT") {
      loadLiveScanner().catch(function () {});
    }
  }, 30000);
  el("auto-refresh").checked = true;
}

async function loadScanner() {
  setStatus("Loading scanner...");
  var pct = Date.now();

  // 1. Render frozen instantly so the page isn't blank — but DON'T show the frozen banner
  var frozenPromise = loadAndRender("/api/screener?mode=FROZEN_RESEARCH", "FROZEN");

  // 2. In parallel, run live discovery — this populates the session asynchronously
  var livePromise = (async function () {
    try {
      var discResp = await fetch("/api/discovery/refresh", { method: "POST" });
      var discData = await discResp.json().catch(function(){ return {}; });
      if (discData.discovered && discData.discovered > 0) {
        await fetch("/api/live/refresh", { method: "POST" });
      }
      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, 15000);
      var resp = await fetch("/api/screener?mode=CURRENT", { signal: controller.signal });
      clearTimeout(timeout);
      if (resp.ok) {
        var live = await resp.json();
        if (live && live.rows && live.rows.length) {
          return { ok: true, data: live };
        }
      }
      return { ok: false, reason: "No live candidates returned from screener" };
    } catch (e) {
      return { ok: false, reason: (e.message || "error") };
    }
  })();

  // 3. Wait for frozen to render first so user sees data instantly
  var frozenPayload = await frozenPromise;
  if (frozenPayload) {
    setStatus("Frozen ready \u00b7 discovering live candidates...");
    resetRefreshTimer();
  } else {
    setStatus("Awaiting data...", true);
    renderRows([]);
    renderHead();
  }

  // 4. Now wait for live to finish — if it succeeded, swap in live data
  var liveResult = await livePromise;
  if (liveResult.ok && liveResult.data) {
    state.rows = liveResult.data.rows;
    state.summary = liveResult.data.summary || null;
    state.mode = "CURRENT";
    state.filteredRows = applyFilters(state.rows);
    renderSummary(state.rows);
    renderHead();
    renderRows(state.filteredRows);
    updateModeUI("CURRENT");
    renderBanner("");
    startNewsFeed();
    resetRefreshTimer();
    setStatus(state.rows.length + " candidates [LIVE] \u00b7 " + (Date.now() - pct) + "ms");
    startAutoRefresh();
    el("auto-refresh").checked = true;
  } else {
    // Live didn't produce rows — keep frozen visible with a clean banner
    if (frozenPayload) {
      renderBanner("FROZEN");
      var ms = Date.now() - pct;
      setStatus(state.rows.length + " candidates [FROZEN] \u00b7 " + ms + "ms \u00b7 live: " + (liveResult.reason || "unavailable"));
    }
  }

  // 5. Load provider status bar
  loadProviderStatus();
  loadCadenceStatus();
}

async function refreshNow() {
  if (state.mode === "CURRENT") {
    refreshLive();
  } else {
    setStatus("Refreshing evidence...");
    loadScanner();
  }
}

async function refreshLive() {
  setStatus("Discovering + refreshing live evidence...");
  try {
    await fetch("/api/discovery/refresh", { method: "POST" });
    await fetch("/api/live/refresh", { method: "POST" });
  } catch (e) {
    // Continue anyway
  }
  await loadLiveScanner();
}

async function loadLiveScanner() {
  setStatus("Loading live scanner data...");
  var pct = Date.now();
  try {
    var resp = await fetch("/api/screener?mode=CURRENT");
    if (resp.ok) {
      var live = await resp.json();
      if (live && live.rows && live.rows.length) {
        state.rows = live.rows;
        state.summary = live.summary || null;
        state.mode = "CURRENT";
        state.filteredRows = applyFilters(state.rows);
        renderSummary(state.rows);
        renderHead();
        renderRows(state.filteredRows);
        updateModeUI("CURRENT");
        renderBanner("CURRENT");
        startNewsFeed();
        resetRefreshTimer();
        setStatus(state.rows.length + " candidates [LIVE] \u00b7 " + (Date.now() - pct) + "ms");
        startAutoRefresh();
        return;
      }
    }
    setStatus("Live mode ready but no candidates found. Click Refresh to re-scan.", true);
  } catch (e) {
    setStatus("Live data unavailable: " + (e.message || "error"), true);
  }
}

async function loadFrozenScanner() {
  setStatus("Loading frozen research...");
  var pct = Date.now();
  try {
    var payload = await getJSON("/api/screener?mode=FROZEN_RESEARCH");
    state.rows = payload.rows || [];
    state.summary = payload.summary || null;
    state.mode = "FROZEN";
    state.filteredRows = applyFilters(state.rows);
    renderSummary(state.rows);
    renderHead();
    renderRows(state.filteredRows);
    updateModeUI("FROZEN");
    renderBanner("FROZEN");
    startNewsFeed();
    resetRefreshTimer();
    setStatus(state.rows.length + " candidates [FROZEN] \u00b7 " + (Date.now() - pct) + "ms");
    if (state.autoTimer) { clearInterval(state.autoTimer); state.autoTimer = null; }
    el("auto-refresh").checked = false;
  } catch (e) {
    setStatus("Frozen research unavailable: " + e.message, true);
  }
}

function updateModeUI(mode) {
  var frozenBtn = el("btn-mode-frozen");
  var liveBtn = el("btn-mode-live");
  if (frozenBtn) frozenBtn.classList.toggle("active", mode === "FROZEN");
  if (liveBtn) liveBtn.classList.toggle("active", mode === "CURRENT");
}

function switchMode(mode) {
  if (mode === "CURRENT") {
    loadLiveScanner();
  } else {
    loadFrozenScanner();
  }
}

async function setAutoRefresh(enabled) {
  try {
    var params = new URLSearchParams({ enabled: enabled ? "true" : "false" });
    await getJSON("/api/live/auto?" + params.toString(), { method: "POST" });
  } catch (e) {
    setStatus("Auto refresh error: " + e.message, true);
  }
  if (state.autoTimer) { clearInterval(state.autoTimer); state.autoTimer = null; }
  if (enabled) {
    state.autoTimer = setInterval(function () {
      if (state.mode === "CURRENT") {
        loadLiveScanner().catch(function () {});
      } else {
        loadFrozenScanner().catch(function () {});
      }
    }, 30000);
  }
  renderRefreshClock();
}

function freshnessElapsedLabel() {
  var elapsed = Math.floor((Date.now() - lastRefreshTime) / 1000);
  if (elapsed < 60) return elapsed + "s ago";
  if (elapsed < 3600) return Math.floor(elapsed / 60) + "m " + (elapsed % 60) + "s ago";
  return Math.floor(elapsed / 3600) + "h ago";
}

function renderRefreshClock() {
  var node = el("refresh-clock");
  if (!node) return;
  var text = el("timer-text");
  var dot = el("timer-dot");
  var summary = state.summary;
  var bits = [];
  bits.push(freshnessElapsedLabel());
  if (summary) {
    var lastAt = summary.last_refresh_at;
    if (lastAt) bits.push("ref " + ago(lastAt));
    bits.push(summary.auto_refresh ? "auto on" : "auto off");
    var cadence = state.cadence;
    if (cadence && cadence.discovery) {
      var disc = cadence.discovery;
      var cap = disc.target_screen_cap || disc.current_screen_cap;
      if (cap) bits.push((disc.candidate_count || 0) + "/" + cap + " screen");
      if (disc.estimated_full_sweep_minutes) {
        bits.push("~ " + disc.estimated_full_sweep_minutes + "m IBKR sweep");
      }
    }
  }
  var line = bits.join(" \u00b7 ");
  if (text) text.textContent = line;
  else node.textContent = line;
  var elapsed = Math.floor((Date.now() - lastRefreshTime) / 1000);
  if (dot) {
    if (elapsed < 15) dot.style.background = "#56d68b";
    else if (elapsed < 60) dot.style.background = "#ffca57";
    else dot.style.background = "#ff7d7d";
  }
}

async function loadCadenceStatus() {
  try {
    state.cadence = await getJSON("/api/discovery/cadence");
    renderRefreshClock();
  } catch (e) {
    // optional status hint
  }
}

/* ------------------------------------------------------------------ provider status bar */

async function loadProviderStatus() {
  try {
    var caps = await getJSON("/api/capabilities");
    state.providerCaps = caps;
    renderProviderBar(caps);
    renderReadiness(state.rows || []);
    updateNewsFeedTitle();
  } catch (e) {
    // Silently skip
  }
}

function renderProviderBar(caps) {
  var bar = el("provider-bar");
  if (!bar) return;
  bar.textContent = "";

  var providers = caps.providers || {};
  var entries = ["IBKR", "Finviz Elite", "NewsAPI", "Finnhub", "SEC_EDGAR", "Finnhub News"];
  var degraded = [];

  entries.forEach(function (id) {
    var info = providers[id] || {};
    if (info.configured && !info.connected) {
      degraded.push({ id: id, detail: info.detail || "Configured, not connected" });
    }
  });

  var btn = document.createElement("button");
  btn.type = "button";
  btn.id = "providers-toggle";
  btn.className = "providers-btn";
  if (!degraded.length) {
    btn.textContent = "Providers OK";
    btn.title = "All configured providers connected";
  } else {
    btn.textContent = "Providers (" + degraded.length + " degraded)";
    btn.title = "Click for details";
    btn.classList.add("warn");
  }
  bar.appendChild(btn);

  var pop = document.createElement("div");
  pop.id = "providers-popover";
  pop.className = "providers-popover";
  pop.hidden = true;
  if (degraded.length) {
    degraded.forEach(function (item) {
      var line = document.createElement("div");
      line.className = "providers-popover-line";
      line.textContent = item.id + ": " + item.detail;
      pop.appendChild(line);
    });
  } else {
    var ok = document.createElement("div");
    ok.className = "providers-popover-line muted";
    ok.textContent = "No degraded providers.";
    pop.appendChild(ok);
  }
  bar.appendChild(pop);

  var adv = document.createElement("a");
  adv.className = "providers-advanced-link";
  adv.href = "/advanced";
  adv.textContent = "Full health";
  bar.appendChild(adv);

  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    pop.hidden = !pop.hidden;
  });
  if (!state.providerPopoverBound) {
    state.providerPopoverBound = true;
    document.addEventListener("click", function () {
      var p = el("providers-popover");
      if (p) p.hidden = true;
    });
  }
}

/* ------------------------------------------------------------------ news feed */

var newsFeedTimer = null;
var newsFeedSymbols = [];
var newsFeedFilter = "";
const NEWS_FEED_INTERVAL = 60000;
const NEWS_FEED_MAX_ITEMS = 30;

/* ------------------------------------------------------------------ live countdown timer */

var lastRefreshTime = Date.now();
var countdownTimer = null;

function resetRefreshTimer() {
  lastRefreshTime = Date.now();
  updateTimerDisplay();
  if (!countdownTimer) {
    countdownTimer = setInterval(updateTimerDisplay, 1000);
  }
}

function updateTimerDisplay() {
  renderRefreshClock();
}

function refreshNewsFeed() {
  if (!state.rows || !state.rows.length) { renderNewsFeed([]); return; }

  // Single request to aggregated endpoint — one call instead of N
  var param = newsFeedFilter ? "classification=" + encodeURIComponent(newsFeedFilter) + "&" : "";
  var url = "/api/news/feed?" + param + "limit=" + NEWS_FEED_MAX_ITEMS;

  getJSON(url).then(function (data) {
    if (!data || !data.headlines) { renderNewsFeed([]); return; }
    newsFeedSymbols = data.symbols || [];
    state.newsMeta = {
      scanned: data.symbols_scanned || 0,
      fetched: data.symbols_fetched || 0,
      lastSuccessAt: new Date().toISOString(),
      lastError: "",
    };
    renderNewsFeed(data.headlines);
    updatePillCounts(data.counts || {});
    updateNewsFeedTitle();
  }).catch(function () {
    state.newsMeta = state.newsMeta || {};
    state.newsMeta.lastError = "News request failed.";
    renderNewsFeed([]);
    updateNewsFeedTitle();
  });
}

function renderNewsFeed(headlines) {
  var list = el("news-feed-list");
  var updated = el("news-feed-updated");
  if (!list) return;

  list.textContent = "";
  if (updated) updated.textContent = new Date().toLocaleTimeString();
  updateNewsFeedTitle();

  if (!headlines.length) {
    var empty = document.createElement("div");
    empty.className = "news-feed-empty";
    var meta = state.newsMeta || {};
    if (!newsFeedSymbols.length) {
      empty.textContent = "Awaiting candidate data before requesting headlines.";
    } else if (meta.scanned && meta.fetched === 0) {
      empty.textContent = "Providers returned no headlines for scanned candidates.";
    } else {
      empty.textContent = "No recent headlines for tracked symbols.";
    }
    list.appendChild(empty);
    return;
  }

  headlines.forEach(function (item) {
    var row = document.createElement("div");
    row.className = "news-feed-item";
    if (item.url) {
      row.style.cursor = "pointer";
      row.addEventListener("click", function () { window.open(item.url, "_blank"); });
    }

    // Symbol badge
    var badge = document.createElement("span");
    badge.className = "nf-symbol";
    var cls = item.classification || "UNEVALUABLE";
    if (cls === "PRIME") badge.classList.add("sym-PRIME");
    else if (cls === "SUBPRIME") badge.classList.add("sym-SUBPRIME");
    else if (cls === "WATCH") badge.classList.add("sym-WATCH");
    else badge.classList.add("sym-default");
    badge.textContent = item.symbol;
    row.appendChild(badge);

    // Headline text
    var headlineSpan = document.createElement("span");
    headlineSpan.className = "nf-headline";
    headlineSpan.textContent = item.headline.length > 110
      ? item.headline.substring(0, 107) + "..."
      : item.headline;
    if (item.headline.length > 110) headlineSpan.title = item.headline;
    row.appendChild(headlineSpan);

    // Time and source line
    var meta = document.createElement("span");
    meta.className = "nf-time";
    var metaParts = [];
    if (item.time) metaParts.push(ago(item.time));
    if (item.source) metaParts.push(item.source);
    meta.textContent = metaParts.join(" \u00b7 ");
    row.appendChild(meta);

    list.appendChild(row);
  });
}

function updateNewsFeedTitle() {
  var title = el("news-feed-title");
  if (!title) return;
  var providers = (state.providerCaps && state.providerCaps.providers) || {};
  var newsApi = providers.NewsAPI || {};
  var finnhubNews = providers["Finnhub News"] || {};
  var bits = ["News"];
  if (newsApi.connected || finnhubNews.connected) bits.push("live");
  else if (newsApi.configured || finnhubNews.configured) bits.push("standby");
  else bits.push("off");
  if (state.newsMeta && state.newsMeta.lastSuccessAt) {
    bits.push("updated " + ago(state.newsMeta.lastSuccessAt));
  }
  if (state.newsMeta && state.newsMeta.lastError) bits.push(state.newsMeta.lastError);
  title.textContent = bits.join(" \u00b7 ");
}

function startNewsFeed() {
  if (newsFeedTimer) { clearInterval(newsFeedTimer); newsFeedTimer = null; }
  refreshNewsFeed();
  newsFeedTimer = setInterval(refreshNewsFeed, NEWS_FEED_INTERVAL);
}

/* ------------------------------------------------------------------ news feed toggle pills */

function updatePillCounts(counts) {
  var toggles = el("news-feed-toggles");
  if (!toggles) return;
  var total = Object.values(counts).reduce(function (a, b) { return a + b; }, 0);
  toggles.querySelectorAll(".nf-pill").forEach(function (pill) {
    var filter = pill.getAttribute("data-nf-filter") || "";
    var n = filter ? (counts[filter] || 0) : total;
    var label = pill.textContent.replace(/\s*\(\d+\)\s*$/, "");
    pill.innerHTML = label + ' <span class="nf-count">(' + n + ')</span>';
  });
}

function setupNewsFeedToggles() {
  var toggles = el("news-feed-toggles");
  if (!toggles) return;
  toggles.addEventListener("click", function (e) {
    var pill = e.target.closest(".nf-pill");
    if (!pill) return;
    e.preventDefault();

    // Update active state
    toggles.querySelectorAll(".nf-pill").forEach(function (p) {
      p.classList.remove("active");
    });
    pill.classList.add("active");

    // Update filter and refresh
    newsFeedFilter = pill.getAttribute("data-nf-filter") || "";
    refreshNewsFeed();
  });
}

function applyNewsPanelMode(mode) {
  state.newsPanelMode = mode || "compact";
  try {
    localStorage.setItem("scannerNewsPanelMode", state.newsPanelMode);
  } catch (e) { /* ignore */ }
  var main = document.querySelector(".scanner-main");
  if (main) {
    main.classList.remove("news-panel-compact", "news-panel-wide", "news-panel-collapsed");
    if (state.newsPanelMode === "compact") main.classList.add("news-panel-compact");
    if (state.newsPanelMode === "wide") main.classList.add("news-panel-wide");
    if (state.newsPanelMode === "collapsed") main.classList.add("news-panel-collapsed");
  }
  var menu = el("news-panel-menu");
  if (menu) {
    menu.querySelectorAll("[data-news-panel]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-news-panel") === state.newsPanelMode);
    });
  }
}

function setupNewsPanelControls() {
  var controls = el("news-panel-controls");
  if (!controls) return;
  var menuBtn = el("news-panel-menu-btn");
  var menu = el("news-panel-menu");
  if (menuBtn && menu) {
    menuBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
    });
    document.addEventListener("click", function () {
      if (menu) menu.hidden = true;
    });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });
  }
  controls.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-news-panel]");
    if (!btn) return;
    e.preventDefault();
    applyNewsPanelMode(btn.getAttribute("data-news-panel") || "compact");
    if (menu) menu.hidden = true;
  });
  applyNewsPanelMode(state.newsPanelMode);
}

/* ------------------------------------------------------------------ export */

function screenerApiMode() {
  return state.mode === "CURRENT" ? "CURRENT" : "FROZEN_RESEARCH";
}

async function exportSnapshot() {
  setStatus("Exporting snapshot…");
  try {
    var params = new URLSearchParams({ mode: screenerApiMode() });
    var result = await getJSON("/api/export?" + params.toString(), { method: "POST" });
    var written = result.written || {};
    var msg = "Exported " + result.row_count + " row(s): "
      + (written.json || "json") + " · " + (written.csv || "csv");
    setStatus(msg);
    showToast(msg, false);
  } catch (error) {
    setStatus("Export failed: " + error.message, true);
    showToast("Export failed: " + error.message, true);
  }
}

function scannerCsvRecord(row) {
  var price = cv(row, "last") || cv(row, "finviz_price") || cv(row, "finnhub_price");
  var dtc = daysToCoverValue(row);
  return {
    symbol: row.symbol,
    price: price == null ? "" : price,
    change_pct: valueFor(row, "percentage_change") == null ? "" : valueFor(row, "percentage_change"),
    rel_vol: valueFor(row, "relative_volume") == null ? "" : valueFor(row, "relative_volume"),
    days_to_cover: dtc == null ? "" : dtc,
    news: newsCount(row) == null ? "" : newsCount(row),
    sentiment: sentimentLabel(row) || "",
    pressure: row.pressure == null ? "" : row.pressure,
    ignition: row.ignition == null ? "" : row.ignition,
    evidence: coverageLabel(row),
    classification: classification(row),
    data_mode: screenerApiMode(),
  };
}

function exportCsvDownload() {
  var rows = state.filteredRows || [];
  if (!rows.length) {
    setStatus("No rows to export.", true);
    showToast("No rows to export.", true);
    return;
  }
  var cols = [
    "symbol", "price", "change_pct", "rel_vol", "days_to_cover",
    "news", "sentiment", "pressure", "ignition", "evidence", "classification", "data_mode",
  ];
  var lines = [cols.join(",")];
  rows.forEach(function (row) {
    var rec = scannerCsvRecord(row);
    lines.push(cols.map(function (c) { return csvEscape(rec[c]); }).join(","));
  });
  var stem = "scanner-" + (state.mode === "CURRENT" ? "live" : "frozen") + "-" + exportTimestamp();
  downloadBlob(stem + ".csv", lines.join("\n"), "text/csv;charset=utf-8");
  var msg = "Downloaded CSV (" + rows.length + " row(s).";
  setStatus(msg);
  showToast(msg, false);
}

/* ------------------------------------------------------------------ init */

function init() {
  el("btn-refresh-now").addEventListener("click", refreshNow);
  el("auto-refresh").addEventListener("change", function (e) { setAutoRefresh(e.target.checked); });
  el("btn-close-detail").addEventListener("click", closeDetail);
  el("detail-overlay").addEventListener("click", function (e) {
    if (e.target === el("detail-overlay")) closeDetail();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDetail();
  });

  // Mode toggle buttons
  var frozenBtn = el("btn-mode-frozen");
  var liveBtn = el("btn-mode-live");
  if (frozenBtn) frozenBtn.addEventListener("click", function () { switchMode("FROZEN"); });
  if (liveBtn) liveBtn.addEventListener("click", function () { switchMode("CURRENT"); });

  var diag = el("toggle-diagnostics");
  if (diag) {
    diag.addEventListener("change", function (e) {
      state.diagnosticsOpen = !!e.target.checked;
      syncBlockerPanelVisibility();
      if (state.diagnosticsOpen) renderBlockerPanel(state.rows);
    });
  }

  var triage = el("triage-filters");
  if (triage) {
    triage.addEventListener("click", function (e) {
      var btn = e.target.closest(".triage-btn");
      if (!btn) return;
      state.triageFilter = btn.getAttribute("data-triage") || "";
      state.filteredRows = applyFilters(state.rows);
      renderSummary(state.rows);
      renderHead();
      renderRows(state.filteredRows);
    });
  }

  var blockerToggle = el("blocker-toggle");
  if (blockerToggle) {
    blockerToggle.addEventListener("click", function () {
      state.blockerOpen = !state.blockerOpen;
      renderBlockerPanel(state.rows);
    });
  }
  var blockerContent = el("blocker-content");
  if (blockerContent) {
    blockerContent.addEventListener("click", function (e) {
      var clear = e.target.closest("[data-blocker-clear]");
      if (clear) {
        state.blockerFilter = null;
      } else {
        var chip = e.target.closest(".blocker-chip");
        if (!chip) return;
        var type = chip.getAttribute("data-blocker-type");
        var key = chip.getAttribute("data-blocker-key");
        if (!type || !key) return;
        if (state.blockerFilter && state.blockerFilter.type === type && state.blockerFilter.key === key) {
          state.blockerFilter = null;
        } else {
          state.blockerFilter = { type: type, key: key };
        }
      }
      state.filteredRows = applyFilters(state.rows);
      renderSummary(state.rows);
      renderHead();
      renderRows(state.filteredRows);
    });
  }

  var filterIds = [
    "filter-classification", "filter-symbol", "filter-min-price", "filter-max-price",
    "filter-min-change", "filter-min-relvol", "filter-min-pressure", "filter-min-ignition",
    "filter-min-coverage", "filter-news", "filter-sentiment", "filter-max-float",
  ];
  filterIds.forEach(function (id) {
    var node = el(id);
    if (!node) return;
    node.addEventListener(id === "filter-symbol" ? "input" : "change", function () {
      state.filteredRows = applyFilters(state.rows);
      renderSummary(state.rows);
      renderHead();
      renderRows(state.filteredRows);
    });
  });

  // Start with frozen (instant), then auto-discover live
  loadScanner();
  setupNewsFeedToggles();
  setupNewsPanelControls();
  var showNewsBtn = el("btn-show-news-panel");
  if (showNewsBtn) {
    showNewsBtn.addEventListener("click", function () {
      applyNewsPanelMode("compact");
    });
  }
  var exportSnapBtn = el("btn-export-snapshot");
  if (exportSnapBtn) exportSnapBtn.addEventListener("click", exportSnapshot);
  var exportCsvBtn = el("btn-export-csv");
  if (exportCsvBtn) exportCsvBtn.addEventListener("click", exportCsvDownload);
  loadProviderStatus();
  loadCadenceStatus();
}

document.addEventListener("DOMContentLoaded", init);
