/* Renders the deterministic public outcome export at data/biya-outcome-case.json.
 *
 * This file only presents what the export contains. It computes no metric, infers no
 * value, and has no fallback that would invent content when a field is absent -- a
 * missing field renders as an explicit "unknown", never as zero or a blank. */

'use strict';

var RULE_TITLES = {
  'RULE-001-PRIME-SUBPRIME': 'Prime / Subprime classification',
  'RULE-002-SHORT-INTEREST-COLUMN': '"Short Interest %" column',
  'RULE-003-DAYS-TO-COVER': 'Days to cover',
  'RULE-004-NEWS-TIMESTAMP': 'News loading and timestamps',
  'RULE-005-MARKET-DATA-FRESHNESS': 'Market data freshness',
  'RULE-006-CROSS-PROVIDER-CORROBORATION': 'Cross-provider corroboration',
  'RULE-007-COMPOSITE-SQUEEZE-SCORE': 'Composite pressure score'
};

/* Plain-language glosses. Deliberately neutral: these describe a rule's evidential
   standing, never a stock's attractiveness. */
var CLASSIFICATION_TEXT = {
  SUPPORTED: 'Used semantically correct evidence that existed at detection, and reproduces.',
  SUPPORTED_WITH_CORRECTION: 'The underlying idea holds, but the formula, label, source, unit, or timing needs correction.',
  MOMENTUM_DISCOVERY_ONLY: 'May surface active movers, but does not on its own confirm short-squeeze pressure.',
  MISLABELED: 'The displayed label does not accurately describe the underlying value.',
  STALE: 'The value existed, but its age or reporting period differs materially from how it was presented.',
  UNAVAILABLE_AT_DETECTION: 'The evidence this rule needs became available only after the candidate was surfaced.',
  MISSING_DEFAULT_SUBSTITUTION: 'A default was substituted for missing evidence, making absence indistinguishable from a real value.',
  REDUNDANT: 'Duplicates another rule without adding materially independent information.',
  UNSUPPORTED: 'Cannot be defended using the available evidence or semantics.',
  UNKNOWN: 'The available artifacts are not sufficient to classify this rule.'
};

var CONCLUSION_TEXT = {
  VALIDATED_AS_RECORDED: 'Validated as recorded',
  PARTIALLY_VALIDATED: 'Partially validated',
  OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED: 'Outcome confirmed, methodology unverified',
  NOT_POINT_IN_TIME_VALID: 'Not point-in-time valid',
  INSUFFICIENT_EVIDENCE: 'Insufficient evidence'
};

var COMPARISON_TEXT = {
  MATCH: 'Match',
  MATCH_WITH_NORMALIZATION: 'Match after unit conversion',
  DIFFERENT_VALUE: 'Different value',
  DIFFERENT_SEMANTICS: 'Different quantity',
  ORIGINAL_MISSING: 'Original missing',
  REBUILT_UNAVAILABLE: 'Rebuilt unavailable',
  ORIGINAL_DEFAULT_SUBSTITUTION: 'Original used a default',
  ORIGINAL_MISLABELED: 'Original mislabeled',
  INCOMPARABLE: 'Not comparable',
  UNKNOWN: 'Unknown'
};

function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) { node.className = className; }
  if (text !== undefined && text !== null) { node.textContent = text; }
  return node;
}

function formatInstant(iso) {
  if (!iso) { return null; }
  var parsed = new Date(iso);
  if (isNaN(parsed.getTime())) { return iso; }
  return parsed.toISOString().replace('.000Z', 'Z').replace('T', ' ');
}

function renderVerdict(data) {
  var label = CONCLUSION_TEXT[data.conclusion] || data.conclusion || 'Unknown';
  document.getElementById('verdict-value').textContent = label;
  document.getElementById('verdict-rationale').textContent = data.conclusion_rationale || '';
}

function renderDetection(data) {
  var start = formatInstant(data.detection_window_start);
  var end = formatInstant(data.detection_window_end);
  var zone = data.detection_timezone ? ' (' + data.detection_timezone + ' local)' : '';

  var summary = document.getElementById('detection-summary');
  if (data.detection_time_state === 'BOUNDED_TIME_WINDOW' && start && end) {
    summary.textContent =
      'Detection is established as a bounded window, not an exact instant: between ' +
      start + ' and ' + end + ' UTC' + zone + '.';
  } else if (data.detection_time_state === 'EXACT_TIMESTAMP') {
    summary.textContent = 'Detection time is exactly recorded by a platform artifact.';
  } else {
    summary.textContent = 'No artifact establishes a defensible detection time for this candidate.';
  }

  document.getElementById('detection-basis').textContent = data.detection_confidence_basis || '';

  var timeline = document.getElementById('timeline');
  timeline.textContent = '';

  var events = [];
  if (start) {
    events.push({
      time: start + ' UTC', bound: true,
      event: 'Earliest possible detection',
      detail: 'The screener run begins. The ticker appears in its log almost immediately, so it was surfaced at or near startup.'
    });
  }
  if (end) {
    events.push({
      time: end + ' UTC', bound: true,
      event: 'Latest possible detection',
      detail: 'The application log is written for the last time. The candidate had certainly been surfaced by this point.'
    });
  }
  events.push({
    time: 'Within the window above', bound: false,
    event: 'Candidate observed on screen during a review session',
    detail: 'Corroborates that the ticker was displayed, but records discussion rather than the moment of detection.'
  });
  events.push({
    time: 'After the window', bound: false,
    event: 'Classification logic was redesigned',
    detail: 'The scoring rules changed later the same day. The rules assessed on this page are the ones that were actually running at detection, not the redesigned ones.'
  });

  events.forEach(function (item) {
    var li = el('li', item.bound ? 'is-bound' : null);
    li.appendChild(el('time', null, item.time));
    li.appendChild(el('div', 'event', item.event));
    li.appendChild(el('div', 'detail', item.detail));
    timeline.appendChild(li);
  });
}

function renderRules(data) {
  var body = document.querySelector('#rules-table tbody');
  body.textContent = '';
  var seen = {};

  (data.rules || []).forEach(function (rule) {
    var tr = el('tr');

    var idCell = el('td', 'rule-id');
    idCell.appendChild(el('strong', null, RULE_TITLES[rule.rule_id] || rule.rule_id));
    tr.appendChild(idCell);

    var classCell = el('td');
    classCell.appendChild(el('span', 'tag tag-emphasis', rule.classification));
    tr.appendChild(classCell);

    tr.appendChild(el('td', null, rule.rationale || ''));
    body.appendChild(tr);

    seen[rule.classification] = true;
  });

  var legend = document.getElementById('legend');
  legend.textContent = '';
  Object.keys(seen).sort().forEach(function (code) {
    legend.appendChild(el('dt', null, code));
    legend.appendChild(el('dd', null, CLASSIFICATION_TEXT[code] || ''));
  });
}

function renderComparisons(data) {
  var rows = data.field_comparisons || [];
  var note = document.getElementById('comparison-note');
  var body = document.querySelector('#comparison-table tbody');
  body.textContent = '';

  if (!rows.length) {
    note.textContent =
      'No field-level comparison is possible. The surviving platform record preserves no ' +
      'displayed value for this candidate, so there is nothing on the original side to ' +
      'compare against. Values are left unknown rather than reconstructed from later data.';
    document.querySelector('#comparison-table').closest('.table-scroll').hidden = true;
    return;
  }

  note.textContent = 'Each recoverable field, with whether its evidence existed at detection.';
  rows.forEach(function (row) {
    var tr = el('tr');
    tr.appendChild(el('td', 'field-id', row.display_name || row.field_id));

    var original = el('td');
    if (row.original_value === 'unknown') {
      original.appendChild(el('span', 'unknown', 'unknown'));
    } else {
      original.textContent = row.original_value;
    }
    tr.appendChild(original);

    var rebuilt = el('td');
    if (row.rebuilt_value === 'unavailable') {
      rebuilt.appendChild(el('span', 'unknown', 'unavailable'));
    } else {
      rebuilt.textContent = row.rebuilt_value;
    }
    tr.appendChild(rebuilt);

    var avail = el('td');
    if (row.available_at_detection === 'unknown') {
      avail.appendChild(el('span', 'unknown', 'unknown'));
    } else {
      avail.textContent = row.available_at_detection === 'true' ? 'yes' : 'no';
    }
    tr.appendChild(avail);

    var state = el('td');
    state.appendChild(el('span', 'tag', COMPARISON_TEXT[row.comparison_state] || row.comparison_state));
    tr.appendChild(state);

    body.appendChild(tr);
  });
}

function renderEvidence(data) {
  var list = document.getElementById('evidence-list');
  list.textContent = '';
  var summaries = data.artifact_summaries || [];
  if (!summaries.length) {
    list.appendChild(el('li', null, 'No artifact is eligible for publication; all supporting evidence is private.'));
    return;
  }
  summaries.forEach(function (summary) {
    list.appendChild(el('li', null, summary));
  });
}

function renderReplays(data) {
  var list = document.getElementById('replay-list');
  list.textContent = '';
  (data.replay_labels || []).forEach(function (label) {
    list.appendChild(el('li', null, label + ' window edge'));
  });
}

function renderOutcome(data) {
  var block = document.getElementById('outcome-block');
  block.textContent = '';

  var policy = el('div', 'policy-strip');
  policy.appendChild(el('span', 'policy-label', 'Reference policy'));
  policy.appendChild(el('code', null,
    (data.boundaries && data.boundaries[0] && data.boundaries[0].reference_policy) || 'unknown'));
  block.appendChild(policy);

  var ledger = el('div', 'boundary-ledger');
  (data.boundaries || []).forEach(function (boundary, index) {
    var card = el('article', 'boundary-card');
    card.appendChild(el('p', 'boundary-index', index === 0 ? 'EARLIEST BOUNDARY' : 'LATEST BOUNDARY'));
    card.appendChild(el('h3', null, formatInstant(boundary.boundary) + ' UTC'));
    var ref = el('div', 'reference-price');
    ref.appendChild(el('span', null, 'Reference close'));
    ref.appendChild(el('strong', null, boundary.reference_price === null ? 'unavailable' : '$' + Number(boundary.reference_price).toFixed(4)));
    card.appendChild(ref);

    var tableWrap = el('div', 'table-scroll');
    var table = el('table', 'outcome-table');
    table.innerHTML = '<thead><tr><th scope="col">Window</th><th scope="col">Maximum move</th><th scope="col">Adverse move</th><th scope="col">Status</th></tr></thead><tbody></tbody>';
    var body = table.querySelector('tbody');
    (boundary.windows || []).forEach(function (window) {
      var row = el('tr');
      row.appendChild(el('td', null, window.window.replaceAll('_', ' ').toLowerCase()));
      row.appendChild(el('td', 'number-cell', window.maximum_observed_return_percent === null ? '—' : Number(window.maximum_observed_return_percent).toFixed(2) + '%'));
      row.appendChild(el('td', 'number-cell', window.maximum_adverse_move_percent === null ? '—' : Number(window.maximum_adverse_move_percent).toFixed(2) + '%'));
      var state = el('td');
      state.appendChild(el('span', 'data-state ' + (window.missing_data_state === 'COMPLETE' ? 'is-complete' : 'is-partial'), window.missing_data_state));
      row.appendChild(state);
      body.appendChild(row);
    });
    tableWrap.appendChild(table);
    card.appendChild(tableWrap);
    ledger.appendChild(card);
  });
  block.appendChild(ledger);

  var contexts = el('div', 'context-grid');
  (data.context || []).forEach(function (item) {
    var card = el('div', 'context-card');
    card.appendChild(el('h3', null, item.data_type.replaceAll('_', ' ').toLowerCase()));
    if (item.availability === 'UNAVAILABLE') {
      card.appendChild(el('p', 'unknown', 'Historical evidence unavailable'));
    } else if (item.data_type === 'NEWS') {
      card.appendChild(el('p', null, item.record_count + ' timestamped items retained'));
      var timing = el('ul', 'context-list');
      (item.items || []).forEach(function (news) {
        timing.appendChild(el('li', null, news.timing.replaceAll('_', ' ').toLowerCase() + ' · ' + news.publisher));
      });
      card.appendChild(timing);
    } else if (item.data_type === 'FINRA_SHORT_SALE_VOLUME') {
      card.appendChild(el('p', null, (item.records || []).length + ' daily records retained'));
      card.appendChild(el('p', 'context-caution', item.limitation));
    } else {
      card.appendChild(el('p', null, item.limitation || 'Historical context retained.'));
    }
    contexts.appendChild(card);
  });
  block.appendChild(el('h3', 'context-heading', 'Context evidence and recorded gaps'));
  block.appendChild(contexts);
}

function renderLimits(data) {
  var list = document.getElementById('limits-list');
  list.textContent = '';
  (data.limitations || []).forEach(function (item) {
    list.appendChild(el('li', null, item));
  });
}

function renderMeta(data) {
  document.getElementById('status-line').textContent =
    'Case ' + data.case_id + ' · status ' + data.case_status + ' · schema ' + data.schema_version;
  document.getElementById('footer-meta').textContent =
    'Deterministic export id: ' + data.deterministic_id;
}

function renderError(message) {
  document.getElementById('status-line').textContent = 'Case data could not be loaded.';
  var main = document.getElementById('main');
  main.textContent = '';
  var box = el('div', 'error-box');
  box.appendChild(el('h2', null, 'Case data unavailable'));
  box.appendChild(el('p', null, message));
  box.appendChild(el('p', null,
    'This page renders a generated export. If you are opening it directly from disk, ' +
    'serve the directory over HTTP instead so the data file can be fetched.'));
  main.appendChild(box);
}

fetch('data/biya-outcome-case.json')
  .then(function (response) {
    if (!response.ok) { throw new Error('HTTP ' + response.status); }
    return response.json();
  })
  .then(function (data) {
    var original = data.original_case;
    renderMeta(original);
    renderVerdict({conclusion: data.conclusion,
      conclusion_rationale: data.methodology_boundary});
    renderDetection(original);
    renderRules(original);
    renderComparisons(original);
    renderEvidence(original);
    renderReplays(original);
    renderOutcome(data);
    renderLimits({limitations: data.limitations});
    document.getElementById('footer-meta').textContent =
      'Deterministic outcome export id: ' + data.deterministic_id;
  })
  .catch(function (error) {
    renderError(String(error && error.message ? error.message : error));
  });
