# UI Route Code-Splitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the current Vite large-chunk warning and reduce the JavaScript required for the initial `/` route without changing application behavior.

**Architecture:** Keep the home page and shared application shell eager, because they are required at startup. Load every non-home route and the assistant sidecar through React `lazy`, place them behind a reusable accessible `Suspense` boundary, and use Vite's generated manifest to enforce budgets on the initial static import graph and every emitted JavaScript chunk.

**Tech Stack:** React 18, React Router 6, TypeScript 5.6, Vite 5, Vitest 2, Node.js standard library

## Global Constraints

- Preserve all existing routes, route props, keyboard behavior, query behavior, and API contracts.
- Preserve unrelated pre-existing worktree changes; stage only the files named in each task.
- Add no runtime or development dependencies.
- Keep `NowPage`, `NavShell`, `ContextBar`, startup recovery, drawers, and inspectors in the eager application shell.
- Lazy-load `WorkspaceRoute` so `lightweight-charts` is absent from the initial static import graph.
- Lazy-load `ResearchPage` so `recharts` is absent from the initial static import graph.
- Lazy-load `AssistantSidecar` only when `assistantOpen` is true.
- Do not raise or suppress Vite's 500,000-byte chunk warning.
- Require initial statically imported JavaScript to be at most 204,800 gzip bytes (200 KiB).
- Require every emitted JavaScript chunk to be at most 500,000 raw bytes.
- Keep the final build fully offline.

## Baseline

The verified production build currently emits one JavaScript asset:

```text
ui/dist/assets/index-DFh9-mdE.js  1,021,994 bytes raw
Vite build output                 1,021.37 kB raw / 280.83 kB gzip
```

`ui/src/App.tsx` statically imports every route. The two chart libraries enter that single graph through:

```text
App.tsx -> WorkspaceRoute.tsx -> WorkspacePage.tsx -> lightweight-charts
App.tsx -> ResearchPage.tsx -> charts/ResearchChartPanels.tsx -> recharts
```

## File Structure

- Create `ui/src/components/LazyBoundary.tsx`: reusable accessible `Suspense` fallback.
- Create `ui/src/components/LazyBoundary.test.tsx`: verifies fallback and resolved-child behavior.
- Create `ui/scripts/check-bundle-budget.mjs`: reads Vite's manifest, computes the initial static import graph, and enforces raw/gzip budgets.
- Modify `ui/src/App.tsx`: replace non-home static imports with named-export-aware `lazy` imports and use `LazyBoundary` for routes and the assistant.
- Modify `ui/vite.config.ts`: emit `.vite/manifest.json` for deterministic budget analysis.
- Modify `ui/package.json`: run the budget checker after `vite build`.

---

### Task 1: Add an Accessible Lazy-Loading Boundary

**Files:**
- Create: `ui/src/components/LazyBoundary.tsx`
- Create: `ui/src/components/LazyBoundary.test.tsx`

**Interfaces:**
- Consumes: React `Suspense`, a `ReactNode`, and an optional loading label.
- Produces: `LazyBoundary({ children, label? })`, used by `App.tsx` for route and assistant loading states.

- [ ] **Step 1: Write the failing boundary test**

Create `ui/src/components/LazyBoundary.test.tsx`:

```tsx
import { lazy, type ReactElement } from "react";
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LazyBoundary } from "./LazyBoundary";

describe("LazyBoundary", () => {
  it("shows an accessible fallback until the child module resolves", async () => {
    let resolveModule!: (module: { default: () => ReactElement }) => void;
    const LazyView = lazy(
      () =>
        new Promise<{ default: () => ReactElement }>((resolve) => {
          resolveModule = resolve;
        }),
    );

    render(
      <LazyBoundary label="Loading research…">
        <LazyView />
      </LazyBoundary>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Loading research…");

    await act(async () => {
      resolveModule({ default: () => <div>Research ready</div> });
    });

    expect(await screen.findByText("Research ready")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the focused test to verify RED**

Run from `ui`:

```powershell
npm.cmd run test -- LazyBoundary.test.tsx
```

Expected: FAIL because `./LazyBoundary` does not exist.

- [ ] **Step 3: Implement the minimal boundary**

Create `ui/src/components/LazyBoundary.tsx`:

```tsx
import { Suspense, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  label?: string;
};

export function LazyBoundary({ children, label = "Loading view…" }: Props) {
  return (
    <Suspense
      fallback={
        <div className="app-loading" role="status">
          {label}
        </div>
      }
    >
      {children}
    </Suspense>
  );
}
```

- [ ] **Step 4: Run focused and full UI tests**

Run from `ui`:

```powershell
npm.cmd run test -- LazyBoundary.test.tsx
npm.cmd run test
```

Expected: the focused test and all UI tests PASS; React Router future-flag warnings may remain informational.

- [ ] **Step 5: Run changed validation**

Run from the repository root:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed
```

Expected: exit code 0. If the report says `full_suite_required=true`, continue to the final full validation in Task 3.

- [ ] **Step 6: Commit the boundary**

```powershell
git add ui/src/components/LazyBoundary.tsx ui/src/components/LazyBoundary.test.tsx
git commit -m "perf(ui): add lazy loading boundary"
```

---

### Task 2: Split Non-Critical Routes and Enforce Bundle Budgets

**Files:**
- Create: `ui/scripts/check-bundle-budget.mjs`
- Modify: `ui/src/App.tsx`
- Modify: `ui/vite.config.ts`
- Modify: `ui/package.json`

**Interfaces:**
- Consumes: Vite's `dist/.vite/manifest.json`, emitted `dist/assets/*.js`, and the existing named page exports.
- Produces: the unchanged `App` default export, dynamic chunks for non-home routes, and an `npm run build` command that fails when either bundle budget is exceeded.

- [ ] **Step 1: Add a manifest-backed budget checker**

Create `ui/scripts/check-bundle-budget.mjs`:

```js
import { readFile, readdir } from "node:fs/promises";
import { gzipSync } from "node:zlib";

const DIST_DIR = new URL("../dist/", import.meta.url);
const MANIFEST_URL = new URL(".vite/manifest.json", DIST_DIR);
const MAX_INITIAL_GZIP_BYTES = 200 * 1024;
const MAX_CHUNK_RAW_BYTES = 500_000;

const manifest = JSON.parse(await readFile(MANIFEST_URL, "utf8"));
const entryRecords = Object.values(manifest).filter((record) => record.isEntry);

if (entryRecords.length !== 1) {
  throw new Error(`Expected exactly one Vite entry, found ${entryRecords.length}.`);
}

const initialFiles = new Set();

function collectStaticImports(record) {
  if (record.file.endsWith(".js")) initialFiles.add(record.file);
  for (const importKey of record.imports ?? []) {
    const importedRecord = manifest[importKey];
    if (!importedRecord) throw new Error(`Manifest import is missing: ${importKey}`);
    if (!initialFiles.has(importedRecord.file)) collectStaticImports(importedRecord);
  }
}

collectStaticImports(entryRecords[0]);

let initialGzipBytes = 0;
for (const relativePath of initialFiles) {
  const source = await readFile(new URL(relativePath, DIST_DIR));
  initialGzipBytes += gzipSync(source).byteLength;
}

const assetsDir = new URL("assets/", DIST_DIR);
const jsAssetNames = (await readdir(assetsDir)).filter((name) => name.endsWith(".js"));
const chunkSizes = await Promise.all(
  jsAssetNames.map(async (name) => {
    const source = await readFile(new URL(name, assetsDir));
    return { name, rawBytes: source.byteLength };
  }),
);
const oversizedChunks = chunkSizes.filter(({ rawBytes }) => rawBytes > MAX_CHUNK_RAW_BYTES);
const failures = [];

if (initialGzipBytes > MAX_INITIAL_GZIP_BYTES) {
  failures.push(
    `Initial JavaScript is ${(initialGzipBytes / 1024).toFixed(2)} KiB gzip; budget is 200.00 KiB.`,
  );
}
for (const { name, rawBytes } of oversizedChunks) {
  failures.push(`${name} is ${rawBytes} raw bytes; budget is ${MAX_CHUNK_RAW_BYTES}.`);
}

const largestChunk = [...chunkSizes].sort((a, b) => b.rawBytes - a.rawBytes)[0];
console.log(
  `Bundle metrics: initial ${(initialGzipBytes / 1024).toFixed(2)} KiB gzip; ` +
    `largest chunk ${largestChunk.name} ${(largestChunk.rawBytes / 1024).toFixed(2)} KiB raw.`,
);

if (failures.length > 0) {
  for (const failure of failures) console.error(`Bundle budget exceeded: ${failure}`);
  process.exitCode = 1;
}
```

- [ ] **Step 2: Make production builds emit a manifest and run the checker**

In `ui/vite.config.ts`, add `build` alongside `test` and `server`:

```ts
export default defineConfig({
  plugins: [react()],
  build: {
    manifest: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
  // existing server block remains unchanged
});
```

In `ui/package.json`, replace the build script:

```json
"build": "vite build && node scripts/check-bundle-budget.mjs"
```

- [ ] **Step 3: Run the build to verify the performance regression test is RED**

Run from `ui`:

```powershell
npm.cmd run build
```

Expected: Vite completes its build, then the budget checker exits non-zero. It must report the current initial graph above 200 KiB gzip and the current `index-*.js` above 500,000 raw bytes.

- [ ] **Step 4: Replace page imports with named-export-aware lazy imports**

In `ui/src/App.tsx`, change the React import and add `LazyBoundary`:

```tsx
import { lazy, useEffect, useState } from "react";
import { LazyBoundary } from "./components/LazyBoundary";
```

Keep these shell imports eager:

```tsx
import { ContextBar } from "./components/ContextBar";
import { ExplanationDrawer } from "./components/ExplanationDrawer";
import { InspectorPanel } from "./components/InspectorPanel";
import { NavShell } from "./components/NavShell";
import { NowPage } from "./components/NowPage";
```

Delete the static imports for `AssistantHistoryPage`, `AssistantSidecar`, `ExplorePage`, `DiscoverPage`, `ResearchPage`, every specialized workspace page, `PortfolioPage`, `OperatorSettingsPage`, `ProviderHealthPanel`, `LiveCanaryControlPlanePage`, `WorkspaceRoute`, and `WorkspaceIndex`. Replace them with these module-scope declarations after the stylesheet imports:

```tsx
const AssistantHistoryPage = lazy(() =>
  import("./components/AssistantHistoryPage").then((module) => ({ default: module.AssistantHistoryPage })),
);
const AssistantSidecar = lazy(() =>
  import("./components/AssistantSidecar").then((module) => ({ default: module.AssistantSidecar })),
);
const ExplorePage = lazy(() =>
  import("./components/ExplorePage").then((module) => ({ default: module.ExplorePage })),
);
const DiscoverPage = lazy(() =>
  import("./components/DiscoverPage").then((module) => ({ default: module.DiscoverPage })),
);
const ResearchPage = lazy(() =>
  import("./components/ResearchPage").then((module) => ({ default: module.ResearchPage })),
);
const SqueezeWorkspacePage = lazy(() =>
  import("./components/squeeze/SqueezeWorkspacePage").then((module) => ({
    default: module.SqueezeWorkspacePage,
  })),
);
const OrderFlowWorkspacePage = lazy(() =>
  import("./components/orderflow/OrderFlowWorkspacePage").then((module) => ({
    default: module.OrderFlowWorkspacePage,
  })),
);
const OptionsWorkspacePage = lazy(() =>
  import("./components/options/OptionsWorkspacePage").then((module) => ({
    default: module.OptionsWorkspacePage,
  })),
);
const LargeTransactionsWorkspacePage = lazy(() =>
  import("./components/largetransactions/LargeTransactionsWorkspacePage").then((module) => ({
    default: module.LargeTransactionsWorkspacePage,
  })),
);
const OrderBookWorkspacePage = lazy(() =>
  import("./components/orderbook/OrderBookWorkspacePage").then((module) => ({
    default: module.OrderBookWorkspacePage,
  })),
);
const FuturesWorkspacePage = lazy(() =>
  import("./components/futures/FuturesWorkspacePage").then((module) => ({
    default: module.FuturesWorkspacePage,
  })),
);
const CatalystWorkspacePage = lazy(() =>
  import("./components/catalyst/CatalystWorkspacePage").then((module) => ({
    default: module.CatalystWorkspacePage,
  })),
);
const FundEtfWorkspacePage = lazy(() =>
  import("./components/fundetf/FundEtfWorkspacePage").then((module) => ({
    default: module.FundEtfWorkspacePage,
  })),
);
const DisclosureWorkspacePage = lazy(() =>
  import("./components/disclosure/DisclosureWorkspacePage").then((module) => ({
    default: module.DisclosureWorkspacePage,
  })),
);
const InstitutionalFlowWorkspacePage = lazy(() =>
  import("./components/institutional/InstitutionalFlowWorkspacePage").then((module) => ({
    default: module.InstitutionalFlowWorkspacePage,
  })),
);
const PortfolioPage = lazy(() =>
  import("./components/PortfolioPage").then((module) => ({ default: module.PortfolioPage })),
);
const OperatorSettingsPage = lazy(() =>
  import("./components/OperatorSettingsPage").then((module) => ({
    default: module.OperatorSettingsPage,
  })),
);
const ProviderHealthPanel = lazy(() =>
  import("./components/live/ProviderHealthPanel").then((module) => ({
    default: module.ProviderHealthPanel,
  })),
);
const LiveCanaryControlPlanePage = lazy(() =>
  import("./components/live/LiveCanaryControlPlanePage").then((module) => ({
    default: module.LiveCanaryControlPlanePage,
  })),
);
const WorkspaceRoute = lazy(() =>
  import("./components/WorkspaceRoute").then((module) => ({ default: module.WorkspaceRoute })),
);
const WorkspaceIndex = lazy(() =>
  import("./components/WorkspaceIndex").then((module) => ({ default: module.WorkspaceIndex })),
);
```

- [ ] **Step 5: Put lazy routes and the assistant behind loading boundaries**

In `Shell`, replace the existing opening `<Routes>` tag with these exact opening tags:

```tsx
<LazyBoundary>
  <Routes>
```

Replace the matching closing `</Routes>` tag with these exact closing tags:

```tsx
  </Routes>
</LazyBoundary>
```

Do not change or reorder any `Route` between those tags.

Replace the always-mounted `AssistantSidecar` block with a conditional lazy boundary. Keep every existing prop and callback unchanged:

```tsx
{assistantOpen ? (
  <LazyBoundary label="Loading assistant…">
    <AssistantSidecar
      open
      status={assistantStatusQuery.data}
      messages={assistantMessagesQuery.data?.messages ?? []}
      loading={assistantBusy || assistantMessagesQuery.isLoading}
      conversationId={conversationId}
      selectionRef={selectionRef}
      onClose={() => setAssistantOpen(false)}
      onSubmit={submitAssistantPrompt}
      onCitationClick={async (ref) => {
        if (ref.startsWith("inspect:")) {
          await openInspectRef(ref);
          return;
        }
        await openExplainRef(ref);
      }}
    />
  </LazyBoundary>
) : null}
```

Keep the existing closed-state assistant toggle unchanged. Do not lazy-load `NowPage`; this prevents a loading flash on the default route and keeps the first meaningful screen in the entry graph.

- [ ] **Step 6: Run TypeScript, UI tests, and the production budget gate**

Run from `ui`:

```powershell
.\node_modules\.bin\tsc.cmd --noEmit
npm.cmd run test
npm.cmd run build
```

Expected:

- TypeScript exits 0.
- All UI tests pass.
- The build emits multiple route chunks.
- `check-bundle-budget.mjs` exits 0.
- Initial statically imported JavaScript is at most 200 KiB gzip.
- No JavaScript asset exceeds 500,000 raw bytes.
- Vite prints no large-chunk warning.

- [ ] **Step 7: Inspect the emitted graph for accidental eager chart loading**

Run from `ui`:

```powershell
Get-Content -Raw 'dist\.vite\manifest.json'
Get-ChildItem 'dist\assets' -File | Sort-Object Length -Descending | Select-Object Name,Length
```

Expected: the manifest entry's recursive `imports` graph does not include the chunks containing `WorkspaceRoute`, `ResearchPage`, `lightweight-charts`, or `recharts`; those appear through `dynamicImports`. Every listed `.js` asset is below 500,000 bytes.

- [ ] **Step 8: Run changed validation**

Run from the repository root:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed
```

Expected: exit code 0 with no failures or errors.

- [ ] **Step 9: Commit route splitting and the budget gate**

```powershell
git add ui/src/App.tsx ui/vite.config.ts ui/package.json ui/scripts/check-bundle-budget.mjs
git commit -m "perf(ui): split routes and enforce bundle budget"
```

---

### Task 3: Run Repository Validation and Review the Final Diff

**Files:**
- Verify only; no planned source changes.

**Interfaces:**
- Consumes: the completed Task 1 and Task 2 commits.
- Produces: evidence that the code-splitting change is safe across UI, domain, and full offline validation.

- [ ] **Step 1: Run the UI domain validator**

Run from the repository root:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py domain ui
```

Expected: exit code 0 with no failures or errors.

- [ ] **Step 2: Run the final offline full validator once**

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py full
```

Expected: exit code 0 with no failures or errors. Do not run a live provider suite because no live provider boundary changes.

- [ ] **Step 3: Review whitespace and scope**

```powershell
git diff --check
git status --short
git diff -- ui/src/App.tsx ui/src/components/LazyBoundary.tsx ui/src/components/LazyBoundary.test.tsx ui/vite.config.ts ui/package.json ui/scripts/check-bundle-budget.mjs
```

Expected: `git diff --check` is clean; the reviewed diff contains only lazy loading, the loading boundary, manifest emission, and bundle-budget enforcement. Unrelated pre-existing changes remain untouched.

- [ ] **Step 4: Record final evidence in the handoff**

Report the known previous bundle (1,021,994 raw bytes and 280.83 KiB gzip in one JavaScript asset), the exact new initial gzip total printed by the budget checker, the exact new largest raw chunk size, and the final TypeScript/test/domain/full pass counts. Use the measured values from the final commands; do not substitute estimates.

## Out of Scope

- Do not add manual Rollup vendor chunks unless measured output after route splitting violates the 500,000-byte cap; route ownership should remain the primary split boundary.
- Do not preload all dynamic routes, because that would undo the initial-load reduction.
- Do not change API request timing, data schemas, route URLs, visual design, or backend code.
- Do not raise `chunkSizeWarningLimit` to silence the warning.
