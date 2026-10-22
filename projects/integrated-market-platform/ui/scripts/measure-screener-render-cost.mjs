/** Controlled React/jsdom render work. Excludes network, full page, layout and paint. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { cpus, platform, release, totalmem } from "node:os";
import ts from "typescript";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useAvailableFilters, useScreenSnapshot } from "../src/components/screener/screenerRenderMemo.ts";

const ui = fileURLToPath(new URL("../", import.meta.url));
const fixtureFlag = process.argv.indexOf("--fixture");
assert(fixtureFlag >= 0, "pass --fixture FILE from the production filter_catalog(None) export");
const catalog = JSON.parse(readFileSync(process.argv[fixtureFlag + 1], "utf8"));
const page = readFileSync(new URL("../src/components/screener/ScreenerPage.tsx", import.meta.url), "utf8");
const parsed = ts.createSourceFile("ScreenerPage.tsx", page, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let columnExpression;
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(parsed) === "definitions") columnExpression = node.initializer.getText(parsed);
  ts.forEachChild(node, visit);
}
visit(parsed);
assert(columnExpression, "production column definitions unavailable");
// The checked-in definition is a literal array; never evaluate request content.
const columns = JSON.parse(JSON.stringify(Function(`return (${columnExpression});`)()));
const keys = columns.map((column) => column.key);
const fields = Object.fromEntries(catalog.map((item) => [item.field, { label: item.label, unit: item.unit }]));
let props = { catalog, universe: "US_EQUITIES", fields,
  screen: { filters: [], view: "Overview", sort: "volume", descending: true, keys,
    visibility: Object.fromEntries(keys.map((key, i) => [key, i % 3 !== 0])), order: keys,
    sizing: Object.fromEntries(columns.map((column) => [column.key, column.width])), pinning: { left: keys.slice(0, 2) } } };

function plain({ catalog, universe, fields, screen }) {
  const filters = catalog.filter((item) => (item.universes ?? ["US_EQUITIES"]).includes(universe)).map((item) => {
    const entry = catalog.find((candidate) => candidate.field === item.field);
    const own = fields[item.field];
    return entry && own?.label ? { ...entry, label: own.label, unit: own.unit ?? entry.unit } : entry ?? item;
  });
  const snapshot = () => ({ filters: screen.filters, view: screen.view,
    sort: { field: screen.sort, descending: screen.descending }, columns: {
      visible: screen.keys.filter((key) => screen.visibility[key] !== false),
      order: screen.order.filter((key) => screen.keys.includes(key)),
      widths: Object.fromEntries(Object.entries(screen.sizing).filter(([key]) => screen.keys.includes(key))),
      pinned: (screen.pinning.left ?? []).filter((key) => screen.keys.includes(key)),
    } });
  const serialized = JSON.stringify(snapshot());
  JSON.stringify(snapshot()); // former second serialization for saved-screen dirty check
  return { filters, serialized };
}
const dom = new JSDOM("<div id='before'></div><div id='after'></div>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let memoOutput;
function Before(input) { plain(input); return null; }
function After(input) {
  const filters = useAvailableFilters(input.catalog, input.universe, input.fields);
  const { snapshot, serialized } = useScreenSnapshot(input.screen);
  memoOutput = { filters, snapshot, serialized };
  return null;
}
const beforeRoot = createRoot(document.getElementById("before"));
const afterRoot = createRoot(document.getElementById("after"));
const renderBefore = () => act(() => beforeRoot.render(React.createElement(Before, props)));
const renderAfter = () => act(() => afterRoot.render(React.createElement(After, props)));
const assertParity = () => {
  assert.deepEqual(memoOutput.filters, plain(props).filters);
  assert.equal(memoOutput.serialized, plain(props).serialized);
};
renderAfter(); assertParity();
const initial = props;
const first = memoOutput;
renderAfter();
assert.equal(first.filters, memoOutput.filters);
assert.equal(first.snapshot, memoOutput.snapshot);
const changes = [
  { catalog: catalog.map((item, i) => i ? item : { ...item, label: "Changed Catalog" }) },
  { fields: { ...fields, price: { label: "Changed Price", unit: "USD" } } },
  { universe: "CRYPTO" },
  ...[{ filters: [{ id: "p", field: "price", operator: "gt", value: 2 }] }, { view: "Custom" },
    { sort: "price" }, { descending: false }, { keys: keys.slice(1) },
    { visibility: { ...props.screen.visibility, price: false, symbol: true } },
    { order: [...keys].reverse() }, { sizing: { ...props.screen.sizing, price: 121 } },
    { pinning: { left: ["price"] } }].map((screen) => ({ screen: { ...initial.screen, ...screen } })),
];
for (const change of changes) {
  props = initial; renderAfter();
  const previous = memoOutput;
  props = { ...initial, ...change }; renderAfter(); assertParity();
  if (change.screen) assert.notEqual(previous.serialized, memoOutput.serialized);
  else assert.notEqual(previous.filters, memoOutput.filters);
}
props = initial;
const hash = (value) => createHash("sha256").update(value).digest("hex");
function measurePair(invalidate) {
  for (let i = 0; i < 40; i++) { renderBefore(); renderAfter(); }
  const before = [], after = [];
  for (let i = 0; i < 400; i++) {
    if (invalidate) props = { ...initial, fields: { ...initial.fields, price: { label: `Price ${i}`, unit: "USD" } }, screen: { ...initial.screen, sort: i % 2 ? "volume" : "price" } };
    for (const [samples, render] of i % 2 ? [[after, renderAfter], [before, renderBefore]] : [[before, renderBefore], [after, renderAfter]]) {
      const start = performance.now(); render(); samples.push(performance.now() - start);
    }
  }
  const summary = (samples) => { const sorted = [...samples].sort((a, b) => a - b); return { median_ms: sorted[200], p95_ms: sorted[380], samples_ms: samples }; };
  return { before: summary(before), after: summary(after) };
}
const steady = measurePair(false);
const invalidated = measurePair(true);
assertParity();
act(() => { beforeRoot.unmount(); afterRoot.unmount(); }); dom.window.close();
const git = (...args) => execFileSync("git", args, { cwd: ui, encoding: "utf8" }).trim();
const report = {
  version: "screener-react-render-cost/2.0.0",
  source: { sha: git("rev-parse", "HEAD"), dirty: Boolean(git("status", "--porcelain", "--", ".")) },
  fixture: { catalog_entries: catalog.length, columns: keys.length, catalog_sha256: hash(JSON.stringify(catalog)), columns_sha256: hash(JSON.stringify(columns)) },
  environment: { node: process.version, react: React.version, platform: platform(), release: release(), cpu: cpus()[0]?.model, memory_bytes: totalmem() },
  methodology: { samples_per_side: 400, warmup: 40, order: "alternating", renderer: "React createRoot + act in jsdom", included: "production hooks, React scheduling, dependency comparison, catalog projection and screen serialization", excluded: "full Screener DOM, network, browser layout, paint, provider, inference" },
  correctness: { independent_output_parity: true, stable_identity: true, invalidated_dependencies: changes.length },
  steady_state: steady, changing_dependencies: invalidated,
};
console.log(JSON.stringify({ ...report, steady_state: { before: steady.before.median_ms, after: steady.after.median_ms }, changing_dependencies: { before: invalidated.before.median_ms, after: invalidated.after.median_ms } }, null, 2));
const outputFlag = process.argv.indexOf("--out");
if (outputFlag >= 0) writeFileSync(process.argv[outputFlag + 1], JSON.stringify(report, null, 2));
