// SOFTWARE_CONTROLLED only. Starts its own isolated harness_trade_lifecycle.py and the built UI, then drives the real UI.
// Clock, bars, quote, marks, candidate receipts, model proposal, Opportunity and auth are controlled fixtures: this proves
// that the Screener tells the lifecycle truth, not market behaviour and not strategy performance.
const { chromium } = require(process.env.IMP_PLAYWRIGHT_MODULE || 'playwright');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '..', '..');
const apiPort = process.env.IMP_OCT1_10_API_PORT || '18810';
const uiPort = process.env.IMP_OCT1_10_UI_PORT || '15110';
const api = 'http://127.0.0.1:' + apiPort;
const base = 'http://127.0.0.1:' + uiPort;
const python = process.env.IMP_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const stateDir = path.join(root, '.local', 'oct1-10-harness-state');
const env = { ...process.env, IMP_OCT1_10_HARNESS: '1', IMP_STATE_DIR: stateDir, IMP_E2E_API_PORT: apiPort, IMP_E2E_UI_PORT: uiPort };
for (const key of ['IMP_LIVE_EXECUTION', 'IMP_LIVE_OBSERVATIONAL', 'IMP_BROKER_PAPER_EXECUTION', 'IMP_MOOMOO_LIVE', 'IMP_FINVIZ_LIVE', 'IMP_LIVE_INTERNAL_SIMULATION']) delete env[key];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function waitFor(url, label) {
  for (let i = 0; i < 240; i++) {
    try { if ((await fetch(url)).ok) return; } catch { /* not up yet */ }
    await sleep(500);
  }
  throw new Error(label + ' did not start');
}
async function stop(child) {
  if (!child || child.exitCode !== null) return;
  const done = new Promise((resolve) => child.once('exit', resolve));
  child.kill();
  await done;
}

(async () => {
  fs.rmSync(stateDir, { recursive: true, force: true });
  fs.mkdirSync(stateDir, { recursive: true });
  const apiProcess = spawn(python, [path.join(root, 'tests', 'acceptance', 'harness_trade_lifecycle.py')], { cwd: root, env, stdio: ['ignore', 'ignore', 'inherit'] });
  // The production bundle is served (vite preview), so the acceptance exercises what ships, not the dev server.
  const vite = path.join(root, 'ui', 'node_modules', 'vite', 'bin', 'vite.js');
  if (!process.env.IMP_OCT1_10_SKIP_BUILD) {
    const built = spawnSync(process.execPath, [vite, 'build'], { cwd: path.join(root, 'ui'), env, stdio: ['ignore', 'ignore', 'inherit'] });
    assert.equal(built.status, 0, 'UI production build failed');
  }
  const ui = spawn(process.execPath, [vite, 'preview', '--host', '127.0.0.1', '--port', uiPort, '--strictPort'],
    { cwd: path.join(root, 'ui'), env, stdio: ['ignore', 'ignore', 'inherit'] });
  let browser;
  let page;
  const receipt = { classification: 'SOFTWARE_CONTROLLED', evidence_class: 'SOFTWARE_CONTROLLED', not_market_evidence: true, not_a_profitability_claim: true,
    fixtures: ['clock', 'completed-bar feed', 'last-trade quote', 'marks', 'candidate receipts', 'model proposal', 'governed Opportunity', 'auth'],
    production: ['trade lifecycle projection', 'action decision service', 'SMA stop service', 'experiment service', 'Paper preview/submit route', 'pre-trade risk',
      'bar-conservative simulator', 'Paper ledger', 'SQLite local state', 'UI production bundle'],
    steps: [], extra_scenarios: [], live_submissions: 0 };
  const step = (id, name, detail = {}) => receipt.steps.push({ step: id, name, ...detail });
  const extra = (name, detail = {}) => receipt.extra_scenarios.push({ name, ...detail });
  try {
    await waitFor(api + '/acceptance/lifecycle/metrics', 'harness API');
    await waitFor(base + '/', 'UI server');
    browser = await chromium.launch({ headless: true, ...(process.env.IMP_CHROMIUM_PATH ? { executablePath: process.env.IMP_CHROMIUM_PATH } : {}) });
    page = await browser.newPage({ viewport: { width: 1500, height: 1500 } });
    page.setDefaultTimeout(25000);
    const requests = [];
    page.on('request', (request) => { const url = new URL(request.url()); if (url.port === apiPort || url.pathname.startsWith('/screener') || url.pathname.startsWith('/paper') || url.pathname.startsWith('/live')) requests.push(request.method() + ' ' + url.pathname); });

    const control = async (suffix) => (await page.request.get(api + '/acceptance/' + suffix)).json();
    const get = async (suffix) => (await page.request.get(api + suffix)).json();
    const squash = (value) => value.replace(/\s+/g, ' ').trim();
    const enterPaper = async () => page.getByRole('button', { name: /Paper.*simulated execution/i }).click();
    const result = page.getByRole('region', { name: 'AI Screener result' });
    const selected = (symbol) => result.getByTestId('lifecycle-card-' + symbol);
    const grouped = (group, symbol) => page.getByTestId(group).getByTestId('lifecycle-card-' + symbol);
    const field = async (card, id) => squash(await card.getByTestId(id).first().innerText());
    const stage = async (card, text) => { await card.getByTestId('lifecycle-stage').filter({ hasText: text }).waitFor(); return field(card, 'lifecycle-stage'); };
    const openScreener = async ({ run = true } = {}) => {
      await page.goto(base + '/screener');
      await page.getByRole('button', { name: 'AI Screener', exact: true }).click();
      await page.getByTestId('lifecycle-boundary').waitFor();
      if (run) { await page.getByRole('button', { name: 'Run AI Screener', exact: true }).click(); await result.waitFor(); }
    };
    const evaluate = async (symbol, state) => {
      const card = selected(symbol);
      await card.getByRole('button', { name: 'Open decision assessment', exact: true }).click();
      await card.getByRole('button', { name: 'Evaluate Decision', exact: true }).waitFor();
      if (state === 'ENTER') {
        const select = card.getByLabel('Governed Opportunity', { exact: true });
        const values = await select.locator('option').evaluateAll((options) => options.map((o) => o.value).filter(Boolean));
        await select.selectOption(values[values.length - 1]);
      }
      await card.getByRole('button', { name: 'Evaluate Decision', exact: true }).click();
      await card.getByRole('heading', { name: state.replace(/_/g, ' '), exact: true }).first().waitFor();
      return (await get('/screener/action-decisions?instrument=' + symbol)).decisions[0];
    };
    const expand = async (card) => { await card.getByRole('button', { name: 'View lifecycle', exact: true }).click(); const detail = card.getByTestId('lifecycle-detail'); await detail.waitFor(); return detail; };
    const timeline = async (card) => card.getByTestId('lifecycle-timeline').locator(':scope > li > strong').allInnerTexts();
    // The Workspace stays the only Paper submit boundary: preview, operator confirmation, explicit Submit.
    const submitTicket = async ({ quantity } = {}) => {
      await page.waitForURL('**/workspace/AAPL');
      await enterPaper();
      await page.getByTestId('experiment-context').waitFor();
      if (quantity) { await page.getByText(/Governed entry risk: APPROVE/).waitFor(); await page.getByLabel('Quantity', { exact: true }).fill(String(quantity)); }
      await page.getByRole('button', { name: 'Preview', exact: true }).click();
      await page.getByText(/^Risk: PASS/).last().waitFor();
      const confirm = page.getByTestId('paper-placeholder-confirm').locator('input');
      if (await confirm.count()) { await page.getByTestId('paper-placeholder-confirm').locator('input:not([disabled])').waitFor(); await confirm.check(); }
      await page.waitForFunction(() => [...document.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Submit' && !b.disabled));
      const before = (await get('/paper/trades')).total_count;
      const attempts = (await control('lifecycle/metrics')).submit_attempts;
      await page.getByRole('button', { name: 'Submit', exact: true }).click();
      for (let i = 0; i < 60 && (await get('/paper/trades')).total_count === before; i++) await sleep(250);
      const trades = await get('/paper/trades');
      assert.equal(trades.total_count, before + 1, 'one simulated fill per explicit submit');
      assert.equal((await control('lifecycle/metrics')).submit_attempts, attempts + 1, 'exactly one submit request');
      return trades.trades[0];
    };

    // Setup: the explicit OCT1-09 Paper experiment. Nothing is created by opening the Screener.
    const start = await control('lifecycle/metrics');
    assert.equal(start.paper_env, '1'); assert.equal(start.live_env, null); assert.equal(start.broker_paper_env, null); assert.equal(start.experiments, 0);
    await page.goto(base + '/portfolio');
    await enterPaper();
    await page.getByRole('button', { name: 'Create $100,000 Paper experiment', exact: true }).click();
    await page.getByTestId('experiment-panel').waitFor();
    const experiment = (await get('/paper/experiments/current')).experiment;
    receipt.experiment = { experiment_id: experiment.experiment_id, paper_account_id: experiment.paper_account_id, execution_mode: experiment.execution_mode, data_mode: experiment.data_mode };
    await control('experiment/price?instrument=AAPL&price=150.00');

    // Extra: NO_ACTION is a complete lifecycle.
    await control('lifecycle/scenario?state=NO_ACTION');
    await openScreener();
    await evaluate('AAPL', 'NO_ACTION');
    assert.equal(await stage(selected('AAPL'), 'NO ACTION'), 'NO ACTION');
    assert.match(await field(selected('AAPL'), 'lifecycle-position'), /^Position FLAT$/);
    assert.match(await field(selected('AAPL'), 'lifecycle-entry'), /^Entry None · Paper: no fill$/);
    assert.match(await field(selected('AAPL'), 'lifecycle-evidence'), /2 supporting · 2 conflicting · 0 weak · 0 missing · 1 blocked/);
    assert.equal((await get('/paper/trades')).total_count, 0);
    extra('NO_ACTION: selected candidate, conflicts and gaps visible, flat, no Paper execution', { stage: 'NO ACTION', position: 'FLAT', entry: 'None · Paper: no fill',
      evidence: await field(selected('AAPL'), 'lifecycle-evidence'), paper_fills: 0 });

    // 1 - 3
    const runA = (await control('lifecycle/scenario?state=ENTER')).run_id;
    const listBefore = requests.length;
    await openScreener();
    step(1, 'Open Screener', { url: base + '/screener' });
    step(2, 'Open AI Screener', { boundary: squash(await page.getByTestId('lifecycle-boundary').innerText()) });
    assert.match(squash(await page.getByTestId('lifecycle-boundary').innerText()), /Market data: .* · Execution: SIMULATED PAPER/);
    step(3, 'Run controlled AI selection', { run_id: runA, model_calls_for_selection: 0, note: 'The stored candidate receipt is a fixture; the reducer is not called.' });

    // 4
    const card = selected('AAPL');
    await card.waitFor();
    assert.equal(squash(await card.getByRole('heading', { level: 3 }).first().innerText()), '#1 AAPL');
    assert.equal(await stage(card, 'SELECTED'), 'SELECTED · NOT ASSESSED');
    step(4, 'See selected candidate and rank', { heading: '#1 AAPL', stage: 'SELECTED · NOT ASSESSED', origin: await field(card, 'lifecycle-origin') });

    // 5 - 7, one request per expansion
    const before = requests.length;
    const detail = await expand(card);
    const detailRequests = requests.slice(before).filter((r) => r.startsWith('GET /screener/trade-lifecycles/'));
    assert.equal(detailRequests.length, 1, 'expanding one lifecycle costs one request');
    const supporting = squash(await detail.getByRole('region', { name: 'Supporting' }).first().innerText());
    assert.match(supporting, /QUOTE · price: 150\.0 — CONTROLLED_FIXTURE · .* ET · CURRENT · FIXTURE/); assert.match(supporting, /TECHNICALS · change_pct: 2/);
    step(5, 'See supporting evidence', { supporting, requests_to_expand: detailRequests.length });
    const conflicting = squash(await detail.getByRole('region', { name: 'Conflicting' }).first().innerText());
    assert.match(conflicting, /SENTIMENT · label: NEGATIVE/); assert.match(conflicting, /PUBLICATION-BASED/); assert.match(conflicting, /Evidence alignment CONFLICTING/);
    step(6, 'See conflicting evidence', { conflicting });
    const missing = squash(await detail.getByRole('region', { name: 'Missing or unavailable' }).first().innerText());
    assert.match(missing, /Excluded: LEVEL2 · STALE · Age exceeds policy/);
    step(7, 'See missing/weak evidence', { missing, weak: squash(await detail.getByRole('region', { name: 'Weak' }).first().innerText()) });

    // 8 - 11, and ENTER is not a fill
    const enter = await evaluate('AAPL', 'ENTER');
    step(8, 'Run action evaluation', { decision_id: enter.decision_id, model_calls: (await control('lifecycle/metrics')).model_calls });
    assert.equal(await stage(card, 'ENTER DECIDED'), 'ENTER DECIDED · NOT EXECUTED');
    const decisionLine = await field(card, 'lifecycle-decision');
    assert.match(decisionLine, /^Decision ENTER · \d\d:\d\d:\d\d ET · AI proposal, server-gated decision$/);
    step(9, 'See ENTER', { stage: 'ENTER DECIDED · NOT EXECUTED', decision: decisionLine });
    const entryLine = await field(card, 'lifecycle-entry');
    assert.match(entryLine, /^Entry DECIDED — NOT EXECUTED · Paper: no fill · Decision reference \$150\.00 at \d\d:\d\d:\d\d ET \(quote, not a fill\)$/);
    step(10, 'See decision time/reference', { entry: entryLine });
    await card.getByRole('button', { name: 'Hide lifecycle', exact: true }).click();
    const entered = await expand(card);
    const conditions = squash(await entered.getByRole('table', { name: 'Entry conditions' }).first().innerText());
    assert.match(conditions, /Current quote available Met/); assert.match(conditions, /Directional support Met/);
    assert.match(squash(await entered.getByRole('region', { name: 'Decision' }).innerText()), /AI proposal: ENTER → server decision: ENTER/);
    step(11, 'See entry conditions', { conditions });
    assert.match(await field(card, 'lifecycle-position'), /^Position FLAT$/);
    assert.equal(await card.getByTestId('lifecycle-unrealized').count(), 0);
    assert.equal((await get('/paper/trades')).total_count, 0);
    extra('ENTER not executed: decision is not a fill and never a position', { stage: 'ENTER DECIDED · NOT EXECUTED', entry: entryLine, position: 'FLAT', paper_fills: 0 });

    // 12 - 15
    const eventsBefore = (await control('lifecycle/metrics')).ledger_events;
    await card.getByRole('button', { name: 'Prepare Paper Preview', exact: true }).click();
    step(12, 'Prepare Paper entry', { control: 'Prepare Paper Preview', route: 'POST /screener/action-decision/handoff' });
    await page.waitForURL('**/workspace/AAPL');
    step(13, 'Open existing Workspace', { url: page.url() });
    assert.equal((await control('lifecycle/metrics')).ledger_events, eventsBefore, 'preparing a draft never mutates the ledger');
    const entryTrade = await submitTicket({ quantity: 6 });
    step(14, 'Preview', { governed_entry_risk: 'APPROVE', interactive_risk: 'PASS', quantity: 6 });
    assert.equal(entryTrade.fill_kind, 'SIMULATED_FILL'); assert.equal(entryTrade.fill_price_minor, 15000); assert.equal(entryTrade.position_effect, 'OPEN');
    assert.equal(entryTrade.decision_id, enter.decision_id);
    step(15, 'Explicitly submit Paper simulation', { submit_route: 'POST /paper/orders', fill_id: entryTrade.fill_id, fill_kind: 'SIMULATED_FILL', decision_id: entryTrade.decision_id });

    // 16 - 19: the position is found again with no AI run loaded
    await openScreener({ run: false });
    const managed = grouped('lifecycle-active-managed', 'AAPL');
    await managed.waitFor();
    step(16, 'Return/open lifecycle', { group: 'Active managed positions', run_loaded: false, origin: await field(managed, 'lifecycle-origin') });
    assert.equal(await stage(managed, 'POSITION OPEN'), 'POSITION OPEN · ENTER');
    step(17, 'See position open', { stage: 'POSITION OPEN · ENTER' });
    const filled = await field(managed, 'lifecycle-entry');
    assert.match(filled, /^Entry Filled \(simulated\) · Position opened \d{4}-\d\d-\d\d \d\d:\d\d:\d\d ET · simulated Paper fill \$150\.00 · Decision reference \$150\.00 at \d\d:\d\d:\d\d ET \(quote, not a fill\)$/);
    step(18, 'See simulated fill time/price', { entry: filled });
    assert.equal(await field(managed, 'lifecycle-position'), 'Position LONG 6 · average entry $150.00');
    step(19, 'See quantity/average entry', { position: 'LONG 6 · average entry $150.00' });

    // 20 - 22
    assert.match(await field(managed, 'lifecycle-mark'), /Unavailable — no mark for this position/);
    assert.match(await field(managed, 'lifecycle-unrealized'), /^Unrealized P&L Unavailable · UNAVAILABLE$/);
    await control('experiment/mark?instrument=AAPL&price=151.00');
    await openScreener({ run: false });
    const mark = await field(managed, 'lifecycle-mark');
    assert.match(mark, /^Current mark \$151\.00 · CURRENT · CONTROLLED_FIXTURE · \d+s old$/);
    step(20, 'See current mark', { mark, before_mark: 'Unavailable — no mark for this position (never $0.00)' });
    const unrealized = await field(managed, 'lifecycle-unrealized');
    assert.equal(unrealized, 'Unrealized P&L +$6.00 · CURRENT');
    assert.equal(await managed.getByTestId('lifecycle-unrealized-value').first().getAttribute('aria-label'), 'gain of $6.00');
    step(21, 'See unrealized P&L', { unrealized, accessible_name: 'gain of $6.00', arithmetic: '6 x (151.00 - 150.00)' });
    assert.match(await field(managed, 'lifecycle-risk'), /SMA trailing stop not configured/);
    assert.doesNotMatch(await field(managed, 'lifecycle-risk'), /\$0\.00/);
    await control('lifecycle/stop?op=configure&window=2');
    await control('lifecycle/stop?op=bar&close=140.00');
    await control('lifecycle/stop?op=bar&close=140.00');
    await openScreener({ run: false });
    const risk = await field(managed, 'lifecycle-risk');
    assert.match(risk, /^Risk control SMA trailing stop · ACTIVE · active stop \$140\.00 · SMA \$140\.0000 · distance \$10\.00 · Deterministic risk control · Model: none$/);
    step(22, 'See SMA risk context', { before_configuration: 'SMA trailing stop not configured', risk });
    await managed.screenshot({ path: path.join(root, '.local', 'oct1-10-open-position.png') }).catch(() => {});

    // Extra: stale mark is never current P&L
    await control('experiment/mark?instrument=AAPL&price=151.00&quality=STALE');
    await openScreener({ run: false });
    assert.match(await field(managed, 'lifecycle-mark'), /^Current mark \$151\.00 · STALE · CONTROLLED_FIXTURE/);
    assert.equal(await field(managed, 'lifecycle-unrealized'), 'Unrealized P&L +$6.00 · STALE — not a current valuation');
    extra('Stale mark: P&L is labelled stale, never current', { mark: await field(managed, 'lifecycle-mark'), unrealized: await field(managed, 'lifecycle-unrealized') });
    await control('experiment/mark?instrument=AAPL&price=151.00');

    // Extra: active position not in the latest run
    const runB = (await control('lifecycle/scenario?state=NO_ACTION&instruments=NVDA')).run_id;
    await openScreener();
    await selected('NVDA').waitFor();
    assert.equal(await selected('AAPL').count(), 0);
    await managed.waitFor();
    const earlier = await field(managed, 'lifecycle-origin');
    assert.match(earlier, /^Active managed position — opened from AI Screener run selected \d\d:\d\d:\d\d ET; not selected by the latest run$/);
    assert.equal(await stage(managed, 'POSITION OPEN'), 'POSITION OPEN · ENTER');
    const lineage = (await get('/screener/trade-lifecycles?run_id=' + runB)).active_managed[0];
    assert.equal(lineage.candidate.run_id, runA); assert.equal(lineage.candidate.selected_in_current_run, false);
    extra('Active position not in the latest run stays visible with its original lineage', { latest_run: runB, latest_selected: ['NVDA'], managed: 'AAPL', origin: earlier, origin_run_id: lineage.origin.run_id });

    // 23 - 24: HOLD through a fresh run that selects the held symbol again
    await control('experiment/price?instrument=AAPL&price=151.00');
    await control('lifecycle/scenario?state=HOLD');
    await openScreener();
    const held = selected('AAPL');
    await held.waitFor();
    assert.match(await field(held, 'lifecycle-origin'), /Selected by this run · position opened from an earlier AI Screener run/);
    const hold = await evaluate('AAPL', 'HOLD');
    step(23, 'Run/consume reevaluation', { decision_id: hold.decision_id, previous_state: hold.previous_state, route: 'explicit Evaluate Decision on a new run',
      note: 'The scheduled reevaluation worker is not started in this harness; receipt-to-timeline joins are covered by tests/trading_correctness/test_trade_lifecycle.py.' });
    assert.equal(await stage(held, 'HOLD'), 'POSITION OPEN · HOLD');
    step(24, 'See HOLD transition', { stage: 'POSITION OPEN · HOLD', decision: await field(held, 'lifecycle-decision') });

    // 25 - 26
    await control('lifecycle/stop?op=bar&close=144.00');
    await openScreener({ run: false });
    const tightened = await field(managed, 'lifecycle-risk');
    assert.match(tightened, /ACTIVE · active stop \$142\.00 · SMA \$142\.0000/);
    step(25, 'Tighten SMA stop', { risk: tightened, arithmetic: '2-bar SMA of 140.00 and 144.00' });
    await expand(managed);
    const history = await timeline(managed);
    assert.ok(history.includes('SMA stop tightened'));
    assert.match(squash(await managed.getByTestId('lifecycle-detail').innerText()), /previous stop \$140\.00/);
    step(26, 'See stop history/context', { events: history.filter((e) => e.startsWith('SMA')), previous_stop: '$140.00' });

    // 27 - 28, and EXIT is not a closed trade
    const calls = (await control('lifecycle/metrics')).model_calls;
    const breached = await control('lifecycle/stop?op=quote&price=141.00');
    assert.equal(breached.status, 'BREACHED');
    assert.equal((await control('lifecycle/metrics')).model_calls, calls, 'a stop breach calls no model');
    step(27, 'Trigger controlled stop breach', { status: 'BREACHED', active_stop: breached.stop.active_stop, observed: breached.stop.trigger_price, model_calls_added: 0 });
    await openScreener({ run: false });
    assert.equal(await stage(managed, 'EXIT DECIDED'), 'EXIT DECIDED · POSITION STILL OPEN');
    const exitDecision = await field(managed, 'lifecycle-decision');
    assert.match(exitDecision, /^Decision EXIT · \d\d:\d\d:\d\d ET · Deterministic risk control · Model: none$/);
    const exitLine = await field(managed, 'lifecycle-exit');
    assert.match(exitLine, /^Exit EXIT decided — position still open · Paper close: NOT SUBMITTED/);
    assert.equal(await field(managed, 'lifecycle-position'), 'Position LONG 6 · average entry $150.00');
    assert.match(await field(managed, 'lifecycle-risk'), /BREACHED · active stop \$142\.00 .* observed \$141\.00 at .* ET · EXIT decision generated/);
    step(28, 'See EXIT decision while position remains open', { stage: 'EXIT DECIDED · POSITION STILL OPEN', decision: exitDecision, exit: exitLine, position: 'LONG 6', risk: await field(managed, 'lifecycle-risk') });
    extra('EXIT not filled: position still open, Paper close not submitted, deterministic origin', { decision: exitDecision, exit: exitLine, trades: (await get('/paper/trades')).total_count });

    // 29 - 31
    await managed.getByRole('button', { name: 'Prepare Paper Exit', exact: true }).click();
    step(29, 'Prepare Paper exit', { control: 'Prepare Paper Exit (lifecycle card)', route: 'POST /screener/action-decision/handoff' });
    const exitTrade = await submitTicket();
    step(30, 'Explicitly submit close', { submit_route: 'POST /paper/orders', side: exitTrade.side, quantity: exitTrade.filled_quantity });
    assert.equal(exitTrade.position_effect, 'CLOSE'); assert.equal(exitTrade.fill_price_minor, 14100); assert.equal(exitTrade.filled_quantity, 6);
    const kinds = Object.fromEntries(exitTrade.lineage_refs.map((r) => [r.kind, r.id]));
    assert.ok(kinds.SMA_STOP_STATE); assert.ok(kinds.ACTION_DECISION);
    step(31, 'See close fill', { fill_id: exitTrade.fill_id, fill_kind: exitTrade.fill_kind, fill_price: '141.00', lineage: kinds });

    // 32 - 34
    await openScreener({ run: false });
    const closed = grouped('lifecycle-recent-closed', 'AAPL');
    await closed.waitFor();
    assert.equal(await page.getByTestId('lifecycle-active-managed').count(), 0);
    assert.equal(await stage(closed, 'POSITION CLOSED'), 'POSITION CLOSED');
    step(32, 'See position CLOSED', { stage: 'POSITION CLOSED', position: await field(closed, 'lifecycle-position') });
    const closedExit = await field(closed, 'lifecycle-exit');
    assert.match(closedExit, /^Exit Closed \(simulated close fill\) · Position closed \d{4}-\d\d-\d\d \d\d:\d\d:\d\d ET · simulated close fill \$141\.00 · Exit decision reference \$141\.00 at \d\d:\d\d:\d\d ET \(quote, not a fill\)$/);
    step(33, 'See exit time/price', { exit: closedExit });
    const realized = await field(closed, 'lifecycle-realized');
    assert.match(realized, /^Realized P&L −\$54\.00 · simulated Paper, this episode only, net of \$0\.00 costs$/);
    assert.equal(await closed.getByTestId('lifecycle-realized-value').first().getAttribute('aria-label'), 'loss of $54.00');
    assert.equal(await closed.getByTestId('lifecycle-unrealized').count(), 0);
    const ledger = await get('/paper/trades');
    assert.equal(ledger.trades.reduce((sum, t) => sum + t.realized_pnl_delta_minor, 0), -5400, 'lifecycle P&L equals the ledger trade history');
    step(34, 'See realized P&L', { realized, arithmetic: '6 x (141.00 - 150.00)', ledger_realized_minor: -5400, accessible_name: 'loss of $54.00' });

    // 35 - 38
    await expand(closed);
    const story = await timeline(closed);
    step(35, 'Open lifecycle history', { events: story });
    await closed.screenshot({ path: path.join(root, '.local', 'oct1-10-closed-lifecycle.png') }).catch(() => {});
    const order = ['Candidate selected', 'Action decision: ENTER', 'Paper simulated fill — position opened', 'Action decision: HOLD', 'SMA trailing stop breached', 'Risk control: EXIT', 'Paper simulated close fill — position closed'];
    let cursor = -1;
    for (const name of order) { const at = story.indexOf(name, cursor + 1); assert.ok(at > cursor, name + ' out of order in ' + JSON.stringify(story)); cursor = at; }
    step(36, 'Verify candidate→ENTER→fill→HOLD→EXIT→close sequence', { verified_order: order });
    const old = closed.getByTestId('lifecycle-decision-' + enter.decision_id).first();
    await old.locator('xpath=ancestor::details[1]').locator(':scope > summary').click();
    await old.getByText('Evidence frozen with this decision').click();
    step(37, 'Expand old ENTER', { decision_id: enter.decision_id });
    const frozen = squash(await old.innerText());
    assert.match(frozen, /ENTER/); assert.match(frozen, /QUOTE · price: 150\.0/); assert.doesNotMatch(frozen, /price: 151\.0|price: 141\.0/);
    // Identifiers are secondary: present, but under the collapsed Details.
    assert.match(await old.evaluate((node) => node.textContent), new RegExp(enter.evidence_snapshot_id));
    assert.doesNotMatch(frozen, new RegExp(enter.evidence_snapshot_id));
    step(38, 'Verify original evidence snapshot', { evidence_snapshot_id: enter.evidence_snapshot_id, frozen_quote: 'price: 150.0', later_quotes_absent: ['151.0', '141.0'] });

    // Extra: a later episode of the same symbol inherits nothing
    await control('experiment/price?instrument=AAPL&price=160.00');
    await control('lifecycle/scenario?state=ENTER');
    await openScreener();
    const fresh = selected('AAPL');
    await fresh.waitFor();
    assert.equal(await stage(fresh, 'SELECTED'), 'SELECTED · NOT ASSESSED');
    assert.match(await field(fresh, 'lifecycle-entry'), /^Entry None · Paper: no fill$/);
    assert.equal(await fresh.getByTestId('lifecycle-realized').count(), 0);
    const second = await evaluate('AAPL', 'ENTER');
    await fresh.getByRole('button', { name: 'Prepare Paper Preview', exact: true }).click();
    const secondTrade = await submitTicket({ quantity: 3 });
    assert.equal(secondTrade.fill_price_minor, 16000);
    await openScreener({ run: false });
    const current = grouped('lifecycle-active-managed', 'AAPL');
    assert.match(await field(current, 'lifecycle-entry'), /simulated Paper fill \$160\.00/);
    assert.equal(await field(current, 'lifecycle-position'), 'Position LONG 3 · average entry $160.00');
    assert.match(await field(current, 'lifecycle-realized'), /^Realized P&L \$0\.00/);
    assert.match(await field(grouped('lifecycle-recent-closed', 'AAPL'), 'lifecycle-realized'), /−\$54\.00/);
    assert.match(await field(grouped('lifecycle-recent-closed', 'AAPL'), 'lifecycle-entry'), /simulated Paper fill \$150\.00/);
    const both = await get('/screener/trade-lifecycles');
    assert.notEqual(both.active_managed[0].lifecycle_id, both.recent_closed[0].lifecycle_id);
    await expand(current);
    assert.match(squash(await current.getByRole('region', { name: 'Other episodes of this instrument' }).innerText()), /Closed .* realized −\$54\.00/);
    assert.doesNotMatch(squash(await current.getByTestId('lifecycle-timeline').innerText()), new RegExp(enter.decision_id));
    extra('Multiple episodes of one symbol: one closed, one new, no cross-contamination', { closed: { entry: '$150.00', realized: '−$54.00', lifecycle_id: both.recent_closed[0].lifecycle_id },
      current: { entry: '$160.00', quantity: 3, realized: '$0.00', lifecycle_id: both.active_managed[0].lifecycle_id, decision_id: second.decision_id } });

    // 39
    const final = await control('lifecycle/metrics');
    assert.equal(final.live_attempts, 0); assert.equal(final.live_env, null); assert.equal(final.broker_paper_env, null);
    assert.equal(requests.filter((r) => r.includes(' /live/') && !r.startsWith('GET')).length, 0);
    step(39, 'Verify zero Live order submissions', { live_attempts: 0, live_env: null, browser_live_mutations: 0 });

    const lifecycleRequests = requests.slice(listBefore).filter((r) => r.includes('/screener/trade-lifecycles'));
    receipt.metrics = { explicit_ui_submits: 3, simulated_fills: final.fills, model_calls: final.model_calls, decisions: final.decisions, stop_events: final.stop_events,
      controlled_clock_offset_seconds: final.offset_seconds, requests_to_expand_one_lifecycle: 1,
      lifecycle_list_requests: lifecycleRequests.filter((r) => r === 'GET /screener/trade-lifecycles').length,
      lifecycle_detail_requests: lifecycleRequests.filter((r) => r !== 'GET /screener/trade-lifecycles').length,
      note: 'The decision made by the stop breach used no model call; every Paper fill followed an explicit Workspace submit.' };
    receipt.steps.sort((a, b) => a.step - b.step);
    fs.writeFileSync(path.join(root, 'artifacts', 'oct1-10-browser.json'), JSON.stringify(receipt, null, 2) + '\n');
    console.log('OCT1-10 browser acceptance passed: ' + receipt.steps.length + ' steps, ' + receipt.extra_scenarios.length + ' extra scenarios');
  } catch (error) {
    fs.mkdirSync(path.join(root, '.local'), { recursive: true });
    if (page) {
      fs.writeFileSync(path.join(root, '.local', 'oct1-10-browser-failure.txt'), page.url() + '\n' + (await page.locator('body').innerText().catch(() => '')));
      await page.screenshot({ path: path.join(root, '.local', 'oct1-10-browser-failure.png'), fullPage: true }).catch(() => {});
    }
    fs.writeFileSync(path.join(root, '.local', 'oct1-10-browser-partial.json'), JSON.stringify(receipt, null, 2));
    throw error;
  } finally {
    if (browser) await browser.close();
    await stop(apiProcess);
    await stop(ui);
  }
})().catch((e) => { console.error(e); process.exitCode = 1; });
