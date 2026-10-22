// SOFTWARE_CONTROLLED only. Starts its own isolated harness_paper_experiment.py and the built UI, then drives the real UI.
// Bars, marks, candidate receipt, model proposal, Opportunity and auth are controlled fixtures: this proves the
// Paper experiment accounting lifecycle, not market behaviour and not strategy performance.
const { chromium } = require(process.env.IMP_PLAYWRIGHT_MODULE || 'playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '..', '..');
const apiPort = process.env.IMP_OCT1_09_API_PORT || '18809';
const uiPort = process.env.IMP_OCT1_09_UI_PORT || '15109';
const api = 'http://127.0.0.1:' + apiPort;
const base = 'http://127.0.0.1:' + uiPort;
const python = process.env.IMP_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const stateDir = path.join(root, '.local', 'oct1-09-harness-state');
const env = { ...process.env, IMP_OCT1_09_HARNESS: '1', IMP_STATE_DIR: stateDir, IMP_E2E_API_PORT: apiPort, IMP_E2E_UI_PORT: uiPort };
for (const key of ['IMP_LIVE_EXECUTION', 'IMP_LIVE_OBSERVATIONAL', 'IMP_BROKER_PAPER_EXECUTION', 'IMP_MOOMOO_LIVE', 'IMP_FINVIZ_LIVE', 'IMP_LIVE_INTERNAL_SIMULATION']) delete env[key];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function waitFor(url, label) {
  for (let i = 0; i < 240; i++) {
    try { if ((await fetch(url)).ok) return; } catch { /* not up yet */ }
    await sleep(500);
  }
  throw new Error(label + ' did not start');
}
function startApi() {
  const child = spawn(python, [path.join(root, 'tests', 'acceptance', 'harness_paper_experiment.py')], { cwd: root, env, stdio: ['ignore', 'ignore', 'inherit'] });
  return child;
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
  let apiProcess = startApi();
  // The production bundle is served (vite preview), so the acceptance exercises what ships, not the dev server.
  const vite = path.join(root, 'ui', 'node_modules', 'vite', 'bin', 'vite.js');
  if (!process.env.IMP_OCT1_09_SKIP_BUILD) {
    const built = require('node:child_process').spawnSync(process.execPath, [vite, 'build'], { cwd: path.join(root, 'ui'), env, stdio: ['ignore', 'ignore', 'inherit'] });
    assert.equal(built.status, 0, 'UI production build failed');
  }
  const ui = spawn(process.execPath, [vite, 'preview', '--host', '127.0.0.1', '--port', uiPort, '--strictPort'],
    { cwd: path.join(root, 'ui'), env, stdio: ['ignore', 'ignore', 'inherit'] });
  let browser;
  let page;
  const receipt = { classification: 'SOFTWARE_CONTROLLED', evidence_class: 'SOFTWARE_CONTROLLED', not_market_evidence: true, not_a_profitability_claim: true,
    fixtures: ['completed-bar feed', 'marks', 'candidate receipt', 'model proposal', 'governed Opportunity', 'auth'],
    production: ['experiment service', 'Paper preview/submit route', 'pre-trade risk', 'bar-conservative simulator', 'Paper ledger', 'SQLite local state', 'action decision service', 'UI'],
    steps: [], extra_scenarios: [], live_submissions: 0 };
  const step = (id, name, detail = {}) => receipt.steps.push({ step: id, name, ...detail });
  const extra = (name, detail = {}) => receipt.extra_scenarios.push({ name, ...detail });
  try {
    await waitFor(api + '/acceptance/experiment/metrics', 'harness API');
    await waitFor(base + '/', 'UI server');
    browser = await chromium.launch({ headless: true, ...(process.env.IMP_CHROMIUM_PATH ? { executablePath: process.env.IMP_CHROMIUM_PATH } : {}) });
    page = await browser.newPage({ viewport: { width: 1500, height: 1500 } });
    page.setDefaultTimeout(25000);
    let lastSubmit = null;
    if (process.env.IMP_OCT1_09_DEBUG) { page.on('request', (r) => { if (r.url().includes('/paper/orders')) console.log('REQ', r.method(), r.url(), (r.postData() || '').slice(0, 160)); }); page.on('response', async (r) => { if (r.url().includes('/paper/orders')) console.log('RES', r.status(), (await r.text().catch(() => '')).slice(0, 300)); }); page.on('requestfailed', (r) => console.log('FAILED', r.url(), r.failure())); page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text().slice(0, 300)); }); }
    page.on('request', (request) => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/paper/orders') lastSubmit = request.postDataJSON(); });

    const harness = async (suffix) => (await page.request.get(api + '/acceptance/experiment/' + suffix)).json();
    const get = async (suffix) => (await page.request.get(api + suffix)).json();
    const panel = page.getByTestId('experiment-panel');
    const metric = async (label) => (await page.getByTestId('experiment-summary').locator('div', { has: page.locator('dt', { hasText: new RegExp('^' + label.replace(/[&]/g, '\\$&') + '$') }) }).locator('dd').innerText()).trim();
    const row = async (symbol) => (await page.getByTestId('experiment-position-' + symbol).innerText()).replace(/\s+/g, ' ');
    // Mode is chosen per page load; Paper is entered explicitly every time.
    const enterPaper = async () => page.getByRole('button', { name: /Paper.*simulated execution/i }).click();
    const openPortfolio = async () => { await page.goto(base + '/portfolio'); await enterPaper(); await panel.waitFor(); };
    const expectMetric = async (label, value) => {
      await page.getByTestId('experiment-summary').locator('div', { has: page.locator('dt', { hasText: new RegExp('^' + label.replace(/[&]/g, '\\$&') + '$') }) }).locator('dd', { hasText: value }).waitFor();
      assert.equal(await metric(label), value, label);
    };
    const openTicket = async (symbol) => {
      await page.goto(base + '/workspace/' + symbol);
      await enterPaper();
      await page.getByTestId('experiment-context').waitFor();
    };
    const setQuantity = async (quantity) => { const input = page.getByLabel('Quantity', { exact: true }); await input.fill(String(quantity)); };
    const previewAndSubmit = async () => {
      await page.getByRole('button', { name: 'Preview', exact: true }).click();
      const submit = page.getByRole('button', { name: 'Submit', exact: true });
      await page.getByText(/^Risk: PASS/).last().waitFor();
      // A handed-off draft is a placeholder: the operator confirms side and quantity after the server preview.
      const confirm = page.getByTestId('paper-placeholder-confirm').locator('input');
      if (await confirm.count()) { await page.getByTestId('paper-placeholder-confirm').locator('input:not([disabled])').waitFor(); await confirm.check(); }
      await page.waitForFunction(() => [...document.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Submit' && !b.disabled));
      const before = (await get('/paper/trades')).total_count;
      await submit.click();
      for (let i = 0; i < 60 && (await get('/paper/trades')).total_count === before; i++) await sleep(250);
      const trades = await get('/paper/trades');
      assert.equal(trades.total_count, before + 1, 'one simulated fill per explicit submit');
      return trades.trades[0];
    };
    const assess = async (state) => {
      await harness('scenario?state=' + state);
      await page.goto(base + '/screener');
      await page.getByRole('button', { name: 'AI Screener', exact: true }).click();
      await page.getByRole('button', { name: 'Run AI Screener', exact: true }).click();
      await page.getByRole('button', { name: 'Open decision assessment', exact: true }).click();
      await page.getByRole('button', { name: 'Evaluate Decision', exact: true }).waitFor();
      if (state === 'ENTER') {
        const select = page.getByLabel('Governed Opportunity', { exact: true });
        const values = await select.locator('option').evaluateAll((options) => options.map((o) => o.value).filter(Boolean));
        await select.selectOption(values[values.length - 1]);
      }
      await page.getByRole('button', { name: 'Evaluate Decision', exact: true }).click();
      await page.getByRole('heading', { name: state, exact: true }).waitFor();
      return (await get('/screener/action-decisions?instrument=AAPL')).decisions[0];
    };

    // 1
    const start = await harness('metrics');
    assert.equal(start.paper_env, '1'); assert.equal(start.live_env, null); assert.equal(start.broker_paper_env, null); assert.equal(start.experiments, 0);
    await page.goto(base + '/portfolio');
    await enterPaper();
    await page.getByTestId('experiment-none').waitFor();
    assert.equal((await get('/paper/experiments/current')).state, 'NO_ACTIVE_PAPER_EXPERIMENT');
    step(1, 'Open Paper Portfolio with no experiment', { state: 'NO_ACTIVE_PAPER_EXPERIMENT', heading: 'No active Paper experiment' });

    // 2
    await page.getByRole('button', { name: 'Create $100,000 Paper experiment', exact: true }).click();
    await panel.waitFor();
    const created = (await get('/paper/experiments/current')).experiment;
    assert.match(created.experiment_id, /^PPE-/); assert.equal(created.evidence_class, 'SOFTWARE_CONTROLLED');
    step(2, 'Create OCT1-09 experiment (explicit)', { experiment_id: created.experiment_id, paper_account_id: created.paper_account_id, schema_version: created.schema_version });

    // 3
    await expectMetric('Initial capital', '$100,000.00'); await expectMetric('Cash', '$100,000.00'); await expectMetric('Total equity', '$100,000.00');
    assert.equal(created.initial_capital_minor, 10000000);
    step(3, 'Verify $100,000.00', { initial_capital_minor: 10000000, cash: '$100,000.00', equity: '$100,000.00' });

    // 4, 5
    const boundary = await page.getByTestId('experiment-boundary').innerText();
    assert.match(boundary, /SIMULATED PAPER EXECUTION/); assert.match(boundary, /Internal Paper simulation \(INTERNAL\)/); assert.match(boundary, /Live capital: No/);
    assert.match(await panel.innerText(), /OCT1-09 PAPER EXPERIMENT · SIMULATED CAPITAL/);
    step(4, 'Verify SIMULATED execution', { execution: 'Internal Paper simulation (INTERNAL)', live_capital: 'No', header: 'OCT1-09 PAPER EXPERIMENT · SIMULATED CAPITAL' });
    assert.match(boundary, /FIXTURE REPLAY DATA \(NOT LIVE MARKET DATA\)/); assert.doesNotMatch(boundary, /LIVE\/CURRENT/);
    step(5, 'Verify actual data-mode label', { data_mode: created.data_mode, label: 'FIXTURE REPLAY DATA (NOT LIVE MARKET DATA) + SIMULATED PAPER EXECUTION', claims_live_data: false });

    // 6, 7
    await harness('price?instrument=AAPL&price=150.00');
    const enter = await assess('ENTER');
    assert.equal(enter.action_state, 'ENTER');
    step(6, 'Navigate from AI candidate to decision assessment', { run_id: enter.evidence_snapshot.candidate_run_id, instrument: 'AAPL' });
    step(7, 'Controlled governed ENTER', { decision_id: enter.decision_id, action_state: 'ENTER', opportunity_id: enter.opportunity_id, evidence_snapshot_id: enter.evidence_snapshot_id });

    // 8
    const eventsBefore = (await harness('metrics')).ledger_events;
    await page.getByRole('button', { name: 'Prepare Paper Preview', exact: true }).click();
    await page.waitForURL('**/workspace/AAPL');
    await enterPaper();
    const strip = page.getByTestId('experiment-context');
    await strip.waitFor();
    const stripText = (await strip.innerText()).replace(/\s+/g, ' ');
    assert.match(stripText, /Experiment: OCT1-09 Paper experiment · simulated capital/i); assert.match(stripText, /Initial \$100,000\.00/i);
    assert.match(stripText, /Cash \$100,000\.00/i); assert.match(stripText, /Buying power \$100,000\.00/i); assert.match(stripText, /Flat in AAPL/);
    // The handed-off draft is revalidated by a server preview first; the operator then sizes the entry.
    await page.getByText(/Governed entry risk: APPROVE/).waitFor();
    // The operator sizes the entry; the governed pre-trade risk engine (BUILD 22) owns the approved quantity.
    await setQuantity(6);
    await page.getByRole('button', { name: 'Preview', exact: true }).click();
    step(8, 'Prepare preview in Workspace with experiment context', { url: page.url(), context: stripText, quantity: 6, side: 'BUY',
      sizing_note: 'Governed entry risk approves at most 6 AAPL shares at 150.00 on this account; a larger request is reduced and must be re-previewed (covered by tests/intelligence/test_action_decision.py).' });

    // 9
    await page.getByTestId('paper-placeholder-confirm').locator('input:not([disabled])').waitFor();
    await page.getByText(/Governed entry risk: APPROVE/).waitFor();
    assert.equal((await harness('metrics')).ledger_events, eventsBefore, 'preview never mutates the ledger');
    await page.getByTestId('paper-placeholder-confirm').locator('input').check();
    step(9, 'Verify risk', { governed_entry_risk: 'APPROVE', approved_quantity: 6, interactive_risk: 'PASS', ledger_events_added_by_preview: 0, operator_confirmed_side_and_quantity: true });

    // 10, 11
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Submit' && !b.disabled));
    assert.equal((await harness('metrics')).submit_attempts, 0, 'nothing was submitted before the explicit click');
    await page.getByRole('button', { name: 'Submit', exact: true }).click();
    for (let i = 0; i < 60 && (await get('/paper/trades')).total_count === 0; i++) await sleep(250);
    const entryTrade = (await get('/paper/trades')).trades[0];
    step(10, 'Explicit Paper submit', { submit_route: 'POST /paper/orders', submit_attempts: (await harness('metrics')).submit_attempts, order_id: entryTrade.order_id });
    assert.equal(entryTrade.fill_kind, 'SIMULATED_FILL'); assert.equal(entryTrade.fill_price_minor, 15000); assert.equal(entryTrade.filled_quantity, 6);
    assert.equal(entryTrade.decision_source, 'AI_DECISION_GOVERNED'); assert.equal(entryTrade.position_effect, 'OPEN');
    const kinds = Object.fromEntries(entryTrade.lineage_refs.map((r) => [r.kind, r.id]));
    assert.equal(kinds.ACTION_DECISION, enter.decision_id); assert.equal(kinds.ACTION_SNAPSHOT, enter.evidence_snapshot_id);
    assert.equal(kinds.CANDIDATE_RUN, enter.evidence_snapshot.candidate_run_id); assert.equal(kinds.PAPER_EXPERIMENT, created.experiment_id);
    assert.ok(kinds.PAPER_PREVIEW); assert.ok(kinds.OPPORTUNITY); assert.ok(entryTrade.risk_decision_id);
    step(11, 'Verify simulated fill', { fill_id: entryTrade.fill_id, fill_kind: 'SIMULATED_FILL', quantity: 6, fill_price: '150.00', is_market_truth: entryTrade.is_market_truth,
      lineage: kinds, risk_decision_id: entryTrade.risk_decision_id, decision_source: entryTrade.decision_source });

    // 12 - 15, missing mark
    await openPortfolio();
    await expectMetric('Cash', '$99,100.00');
    step(12, 'Verify cash decreased', { cash_before: '$100,000.00', cash_after: '$99,100.00', arithmetic: '100000.00 - 6 x 150.00 - 0.00 costs' });
    let aapl = await row('AAPL');
    assert.match(aapl, /^AAPL LONG 6 /);
    step(13, 'Verify position appeared', { row: aapl });
    step(14, 'Verify quantity', { quantity: 6 });
    assert.match(aapl, /\$150\.00/);
    step(15, 'Verify average entry', { average_entry: '$150.00', cost_basis_minor: 90000 });
    assert.match(aapl, /No mark — not valued/); assert.doesNotMatch(aapl, /\$0\.00/);
    await expectMetric('Total equity', 'Unavailable'); await expectMetric('Unrealized P&L', 'Unavailable');
    assert.match(await page.getByTestId('experiment-quality').innerText(), /Valuation quality: UNAVAILABLE/);
    extra('Missing mark is never valued at zero', { quality: 'UNAVAILABLE', total_equity: 'Unavailable', unrealized: 'Unavailable', position_row: aapl });

    // 16, 17
    await harness('mark?instrument=AAPL&price=155.00');
    await openPortfolio();
    aapl = await row('AAPL');
    assert.match(aapl, /\$155\.00/); assert.match(aapl, /CONTROLLED_FIXTURE · PASS/);
    step(16, 'Apply/update mark', { instrument: 'AAPL', mark: '$155.00', provider: 'CONTROLLED_FIXTURE', quality: 'PASS' });
    assert.match(aapl, /\+\$30\.00/);
    await expectMetric('Unrealized P&L', '+$30.00'); await expectMetric('Total equity', '$100,030.00'); await expectMetric('Total Paper P&L', '+$30.00');
    step(17, 'Verify unrealized P&L', { unrealized: '+$30.00', arithmetic: '6 x (155.00 - 150.00)', equity: '$100,030.00' });

    // 18 - 20
    await harness('price?instrument=NVDA&price=240.00');
    await openTicket('NVDA');
    assert.match((await page.getByTestId('experiment-context').innerText()).replace(/\s+/g, ' '), /Cash \$99,100\.00.*Flat in NVDA/i);
    await setQuantity(50);
    const nvdaTrade = await previewAndSubmit();
    assert.equal(nvdaTrade.symbol, 'NVDA'); assert.equal(nvdaTrade.fill_price_minor, 24000); assert.equal(nvdaTrade.decision_source, 'MANUAL_TEST');
    await openPortfolio();
    assert.match(await page.getByTestId('experiment-quality').innerText(), /Valuation quality: PARTIAL[\s\S]*NVDA \(no mark\)/);
    await expectMetric('Total equity', 'Unavailable');
    extra('One unmarked position makes total equity unavailable (PARTIAL)', { marked: ['AAPL'], unmarked: ['NVDA'], total_equity: 'Unavailable' });
    await harness('mark?instrument=NVDA&price=236.00');
    await openPortfolio();
    const account = (await get('/paper/experiments/current')).experiment.paper_account_id;
    assert.equal(account, created.paper_account_id);
    step(18, 'Open and mark second instrument in the same account', { instrument: 'NVDA', quantity: 50, fill_price: '240.00', mark: '236.00', paper_account_id: account, same_account: true, decision_source: 'MANUAL_TEST' });
    aapl = await row('AAPL'); let nvda = await row('NVDA');
    assert.match(aapl, /\$155\.00[\s\S]*\+\$30\.00/); assert.match(nvda, /\$236\.00[\s\S]*−\$200\.00/); assert.doesNotMatch(nvda, /\$155\.00/); assert.doesNotMatch(aapl, /\$236\.00/);
    step(19, 'Verify independent marks', { AAPL: { mark: '$155.00', unrealized: '+$30.00' }, NVDA: { mark: '$236.00', unrealized: '−$200.00' } });
    await expectMetric('Cash', '$87,100.00'); await expectMetric('Position value', '$12,730.00'); await expectMetric('Total equity', '$99,830.00');
    await expectMetric('Total Paper P&L', '−$170.00'); await expectMetric('Paper experiment return', '−0.17%');
    step(20, 'Verify aggregate equity', { cash: '$87,100.00', position_value: '$12,730.00', equity: '$99,830.00', arithmetic: '87100.00 + 6 x 155.00 + 50 x 236.00', paper_pnl: '−$170.00' });

    // stale mark, close blocked
    await harness('mark?instrument=NVDA&price=236.00&quality=STALE');
    await openPortfolio();
    assert.match(await page.getByTestId('experiment-quality').innerText(), /Valuation quality: DEGRADED[\s\S]*NVDA \(not current\)/);
    assert.match(await row('NVDA'), /CONTROLLED_FIXTURE · STALE/);
    extra('Stale mark degrades the valuation and stays identified', { quality: 'DEGRADED', instrument: 'NVDA', mark_quality: 'STALE', equity_still_shown: await metric('Total equity') });
    await harness('mark?instrument=NVDA&price=236.00');
    await openPortfolio();
    await page.getByRole('button', { name: 'Close experiment', exact: true }).click();
    await page.getByTestId('experiment-close-error').waitFor();
    assert.match(await page.getByTestId('experiment-close-error').innerText(), /OPEN_POSITIONS_REMAIN/);
    assert.equal((await get('/paper/experiments/current')).state, 'ACTIVE');
    extra('Experiment close blocked with open positions; nothing liquidated', { reason: 'OPEN_POSITIONS_REMAIN', positions_after: (await get('/paper/portfolio')).positions.length });

    // 21 - 23
    await harness('price?instrument=AAPL&price=155.00');
    await openTicket('AAPL');
    assert.match((await page.getByTestId('experiment-context').innerText()).replace(/\s+/g, ' '), /LONG 6 sh of AAPL/);
    await page.getByRole('group', { name: 'Order side' }).getByRole('button', { name: /sell/i }).click();
    await setQuantity(2);
    const partial = await previewAndSubmit();
    assert.equal(partial.position_effect, 'REDUCE'); assert.equal(partial.realized_pnl_delta_minor, 1000); assert.equal(partial.position_after, 4);
    step(21, 'Partially close first position', { side: 'SELL', quantity: 2, fill_price: '155.00', position_after: 4, position_effect: 'REDUCE' });
    await openPortfolio();
    await expectMetric('Realized P&L', '+$10.00'); await expectMetric('Cash', '$87,410.00');
    step(22, 'Verify realized P&L', { realized: '+$10.00', arithmetic: '2 x (155.00 - 150.00)', cash: '$87,410.00' });
    aapl = await row('AAPL');
    assert.match(aapl, /^AAPL LONG 4 \$150\.00/); assert.match(aapl, /\+\$20\.00/);
    await expectMetric('Unrealized P&L', '−$180.00'); await expectMetric('Total equity', '$99,830.00');
    step(23, 'Verify remaining unrealized P&L', { remaining_quantity: 4, remaining_average_entry: '$150.00', remaining_cost_basis: '$600.00', AAPL_unrealized: '+$20.00', NVDA_unrealized: '−$200.00',
      total_unrealized: '−$180.00', equity: '$99,830.00', identity: '100000.00 + 10.00 realized − 180.00 unrealized' });

    // mid-lifecycle restart with open positions
    const beforeMid = { portfolio: await get('/paper/portfolio'), trades: await get('/paper/trades') };
    const pidBefore = (await harness('metrics')).pid;
    await stop(apiProcess); apiProcess = startApi();
    await waitFor(api + '/acceptance/experiment/metrics', 'restarted harness API');
    const afterMidMetrics = await harness('metrics');
    assert.notEqual(afterMidMetrics.pid, pidBefore); assert.equal(afterMidMetrics.experiment_id, created.experiment_id); assert.equal(afterMidMetrics.experiments, 1);
    const afterMid = { portfolio: await get('/paper/portfolio'), trades: await get('/paper/trades') };
    assert.deepEqual(afterMid.trades.trades, beforeMid.trades.trades);
    assert.equal(afterMid.portfolio.account.cash_minor, 8741000); assert.equal(afterMid.portfolio.valuation.initial_capital_minor, 10000000);
    for (const symbol of ['AAPL', 'NVDA']) {
      const a = beforeMid.portfolio.positions.find((p) => p.symbol === symbol); const b = afterMid.portfolio.positions.find((p) => p.symbol === symbol);
      for (const key of ['quantity', 'side', 'cost_basis_minor', 'average_fill_minor', 'first_entry_time_ns', 'mark_minor', 'mark_as_of_ns', 'realized_pnl_minor']) assert.equal(b[key], a[key], symbol + ' ' + key);
      assert.equal(b.mark_quality, 'RESTORED');
    }
    assert.equal(afterMid.portfolio.valuation.quality, 'DEGRADED'); assert.equal(afterMid.portfolio.valuation.equity_minor, 9983000);
    await openPortfolio();
    assert.match(await page.getByTestId('experiment-quality').innerText(), /Valuation quality: DEGRADED/);
    extra('Process restart with two open positions: same experiment, no re-seed, marks restored as not current', { pid_before: pidBefore, pid_after: afterMidMetrics.pid,
      experiment_id: afterMidMetrics.experiment_id, cash_minor: 8741000, equity_minor: 9983000, valuation_quality: 'DEGRADED', mark_quality: 'RESTORED', trades_identical: true });

    // 24 - 26
    await harness('price?instrument=AAPL&price=153.00');
    await harness('mark?instrument=AAPL&price=153.00'); await harness('mark?instrument=NVDA&price=236.00');
    const exit = await assess('EXIT');
    assert.equal(exit.action_state, 'EXIT');
    // The lifecycle card and the decision record both offer this action; the decision just evaluated is the one meant.
    await page.getByRole('region', { name: 'Current decision', exact: true }).getByRole('button', { name: 'Prepare Paper Exit', exact: true }).click();
    await page.waitForURL('**/workspace/AAPL');
    await enterPaper();
    await page.getByTestId('experiment-context').waitFor();
    await page.waitForFunction(() => [...document.querySelectorAll('label')].some((l) => /^Quantity/.test(l.textContent || '') && (l.querySelector('input') || document.getElementById(l.htmlFor) || {}).value === '4'));
    assert.match(await page.locator('.paper-cockpit-action').innerText(), /SELL/i);
    step(24, 'Prepare final governed EXIT', { decision_id: exit.decision_id, action_state: 'EXIT', ticket_quantity: 4, ticket_side: 'SELL', quantity_authority: 'Paper ledger (per-instrument position)' });
    const exitTrade = await previewAndSubmit();
    assert.equal(exitTrade.position_effect, 'CLOSE'); assert.equal(exitTrade.position_after, 0); assert.equal(exitTrade.realized_pnl_delta_minor, 1200);
    assert.equal(exitTrade.decision_source, 'AI_DECISION_GOVERNED');
    assert.equal(Object.fromEntries(exitTrade.lineage_refs.map((r) => [r.kind, r.id])).ACTION_DECISION, exit.decision_id);
    step(25, 'Submit Paper close (explicit)', { fill_id: exitTrade.fill_id, quantity: 4, fill_price: '153.00', realized_delta: '+$12.00', decision_source: exitTrade.decision_source });
    // The second instrument is closed from the operator ticket so the whole account is flat.
    await harness('price?instrument=NVDA&price=236.00');
    await openTicket('NVDA');
    await page.getByRole('group', { name: 'Order side' }).getByRole('button', { name: /sell/i }).click();
    await setQuantity(50);
    const nvdaClose = await previewAndSubmit();
    assert.equal(nvdaClose.position_effect, 'CLOSE'); assert.equal(nvdaClose.realized_pnl_delta_minor, -20000);
    await openPortfolio();
    await page.getByText('No open positions. Equity is cash.').waitFor();
    assert.equal((await get('/paper/portfolio')).positions.length, 0);
    step(26, 'Verify flat', { open_positions: 0, AAPL: 'closed by governed EXIT', NVDA: 'closed from operator ticket at 236.00 (realized −$200.00)' });

    // 27 - 29
    await expectMetric('Realized P&L', '−$178.00'); await expectMetric('Unrealized P&L', '$0.00'); await expectMetric('Cash', '$99,822.00');
    await expectMetric('Total equity', '$99,822.00'); await expectMetric('Total Paper P&L', '−$178.00');
    step(27, 'Verify final realized P&L', { realized: '−$178.00', arithmetic: '(+10.00 AAPL partial) + (+12.00 AAPL exit) + (−200.00 NVDA)', cash: '$99,822.00', equity: '$99,822.00', flat_identity: 'equity == cash' });
    const tradeRows = page.getByTestId('experiment-trades').locator('tbody > tr');
    assert.equal(await tradeRows.count(), 5);
    const tradeText = (await page.getByTestId('experiment-trades').innerText()).replace(/[ \t]+/g, ' ');
    assert.match(tradeText, /Governed AI decision/); assert.match(tradeText, /Operator ticket \(no governed decision\)/);
    await tradeRows.last().getByRole('button', { name: 'View decision', exact: true }).click();
    await page.getByTestId('experiment-trades').locator('[title="' + enter.decision_id + '"]').first().waitFor();  // identifiers are abbreviated; the full id is the tooltip
    const history = (await get('/paper/trades')).trades;
    step(28, 'Verify trade history', { rows: 5, effects: history.map((t) => t.symbol + ' ' + t.side + ' ' + t.filled_quantity + ' ' + t.position_effect).reverse(),
      realized_deltas_minor: history.map((t) => t.realized_pnl_delta_minor).reverse(), decision_drilldown: 'entry row shows action decision ' + enter.decision_id,
      order_history_rows: (await get('/paper/portfolio')).orders.length });
    assert.ok(history.every((t) => t.commission_minor === 0 && t.fees_minor === 0 && t.fill_kind === 'SIMULATED_FILL'));
    await page.getByTestId('experiment-assumptions').locator('summary').click();
    const assumptions = await page.getByTestId('experiment-assumptions').innerText();
    assert.match(assumptions, /NOT_SEPARATELY_MODELED/); assert.match(assumptions, /\$0\.00 per share \(none charged\)/); assert.match(assumptions, /simulation\.bar_conservative/);
    step(29, 'Verify commission/fees', { commission_total_minor: 0, fees_total_minor: 0, commission_policy: '$0.00 per share (none charged)', fee_policy: '$0.00 per order (none charged)',
      slippage: 'NOT_SEPARATELY_MODELED', fill_model: 'simulation.bar_conservative · phase7.bar-conservative/1.1.0' });
    fs.mkdirSync(path.join(root, '.local'), { recursive: true });
    await page.screenshot({ path: path.join(root, '.local', 'oct1-09-flat.png'), fullPage: true });

    // 30, 31
    const before = { portfolio: await get('/paper/portfolio'), trades: await get('/paper/trades'), equity: await get('/paper/equity-history?limit=100') };
    const pid = (await harness('metrics')).pid;
    await stop(apiProcess); apiProcess = startApi();
    await waitFor(api + '/acceptance/experiment/metrics', 'restarted harness API');
    const restarted = await harness('metrics');
    assert.notEqual(restarted.pid, pid);
    step(30, 'Restart backend (real process restart, same state directory)', { pid_before: pid, pid_after: restarted.pid, state_dir: 'isolated IMP_STATE_DIR' });
    const after = { portfolio: await get('/paper/portfolio'), trades: await get('/paper/trades'), equity: await get('/paper/equity-history?limit=100') };
    assert.equal(restarted.experiment_id, created.experiment_id); assert.equal(restarted.experiments, 1);
    assert.equal(after.portfolio.account.paper_account_id, created.paper_account_id); assert.equal(after.portfolio.account.cash_minor, 9982200);
    assert.equal(after.portfolio.account.initial_cash_minor, 10000000); assert.equal(after.portfolio.valuation.equity_minor, 9982200);
    assert.equal(after.portfolio.valuation.realized_pnl_minor, -17800); assert.deepEqual(after.trades, before.trades);
    assert.deepEqual(after.equity.snapshots, before.equity.snapshots); assert.equal(after.portfolio.orders.length, before.portfolio.orders.length);
    await openPortfolio();
    await expectMetric('Cash', '$99,822.00'); await expectMetric('Total equity', '$99,822.00'); await expectMetric('Realized P&L', '−$178.00');
    assert.equal(await page.getByTestId('experiment-trades').locator('tbody > tr').count(), 5);
    step(31, 'Verify exact portfolio restore', { experiment_id: restarted.experiment_id, paper_account_id: after.portfolio.account.paper_account_id, cash_minor: 9982200, equity_minor: 9982200,
      realized_pnl_minor: -17800, trades_identical: true, equity_history_identical: true, reseeded: false, new_experiment_created: false });

    // 32
    assert.ok(lastSubmit && lastSubmit.idempotency_key, 'a real submit body was captured from the UI');
    const eventsAtRetry = restarted.ledger_events;
    const retry = await (await page.request.post(api + '/paper/orders', { data: lastSubmit })).json();
    assert.equal(retry.submission.duplicate, true); assert.equal(retry.submission.order_id, nvdaClose.order_id);
    const afterRetry = { metrics: await harness('metrics'), trades: await get('/paper/trades'), portfolio: await get('/paper/portfolio') };
    assert.equal(afterRetry.trades.total_count, 5); assert.equal(afterRetry.portfolio.account.cash_minor, 9982200); assert.equal(afterRetry.metrics.ledger_events, eventsAtRetry);
    assert.equal(afterRetry.portfolio.positions.length, 0, 'the retried SELL did not open a short');
    step(32, 'Retry duplicate submission: no duplicate accounting', { idempotency_key: lastSubmit.idempotency_key, duplicate: true, order_id: retry.submission.order_id, trades: 5, cash_minor: 9982200, ledger_events_added: 0, after_restart: true });

    // 33
    const final = await harness('metrics');
    assert.equal(final.live_attempts, 0); assert.equal(final.live_env, null); assert.equal(final.broker_paper_env, null); assert.equal(final.live_observational_env, null);
    assert.equal(final.execution_mode, 'INTERNAL_SIMULATION');
    step(33, 'Confirm zero Live-capital submissions', { live_route_attempts: 0, live_execution_env: null, broker_paper_env: null, execution_mode: final.execution_mode, every_fill_kind: 'SIMULATED_FILL' });

    // close a flat experiment
    await page.getByRole('button', { name: 'Close experiment', exact: true }).click();
    await page.getByTestId('experiment-status').filter({ hasText: 'CLOSED' }).waitFor();
    await page.getByTestId('experiment-none').waitFor();  // a new experiment is offered explicitly; the closed one stays readable
    assert.equal(await page.getByRole('button', { name: 'Close experiment', exact: true }).count(), 0);
    await page.getByTestId('experiment-trades').locator('tbody > tr').nth(4).waitFor();  // history refetches after close
    assert.equal(await page.getByTestId('experiment-trades').locator('tbody > tr').count(), 5);
    const closed = await get('/paper/experiments/' + created.experiment_id);
    assert.equal(closed.experiment.status, 'CLOSED'); assert.equal(closed.experiment.closing.final_equity_minor, 9982200); assert.equal(closed.experiment.closing.final_cash_minor, 9982200);
    assert.equal((await get('/paper/trades?experiment_id=' + created.experiment_id)).total_count, 5);
    extra('Flat experiment closes; final values frozen and history still readable', { status: 'CLOSED', final_equity_minor: 9982200, final_cash_minor: 9982200, trade_count: closed.experiment.closing.trade_count });

    receipt.experiment = { experiment_id: created.experiment_id, paper_account_id: created.paper_account_id, initial_capital_minor: 10000000, data_mode: created.data_mode, execution_mode: created.execution_mode };
    receipt.arithmetic = [
      { event: 'create', cash: '100000.00', equity: '100000.00' },
      { event: 'BUY 6 AAPL @ 150.00 (governed ENTER, sized inside the governed pre-trade risk approval)', cash: '99100.00' },
      { event: 'mark AAPL 155.00', unrealized: '+30.00', equity: '100030.00' },
      { event: 'BUY 50 NVDA @ 240.00 (operator ticket)', cash: '87100.00' },
      { event: 'mark NVDA 236.00', unrealized: '+30.00 AAPL, -200.00 NVDA', equity: '99830.00', paper_pnl: '-170.00' },
      { event: 'SELL 2 AAPL @ 155.00 (operator ticket)', cash: '87410.00', realized: '+10.00', unrealized: '+20.00 AAPL, -200.00 NVDA', equity: '99830.00' },
      { event: 'SELL 4 AAPL @ 153.00 (governed EXIT)', cash: '88022.00', realized: '+22.00' },
      { event: 'SELL 50 NVDA @ 236.00 (operator ticket)', cash: '99822.00', realized: '-178.00', unrealized: '0.00', equity: '99822.00', paper_pnl: '-178.00' },
    ];
    receipt.metrics = { explicit_ui_submits: 5, simulated_fills: 5, duplicate_retry_submits: 1, duplicate_fills: 0, live_attempts: 0, process_restarts: 2,
      submit_route_attempts_since_last_restart: final.submit_attempts, note: 'Harness counters are in-memory and reset on each process restart; fills are counted from the persisted ledger.' };
    receipt.steps.sort((a, b) => a.step - b.step);
    fs.writeFileSync(path.join(root, 'artifacts', 'oct1-09-browser.json'), JSON.stringify(receipt, null, 2) + '\n');
    console.log('OCT1-09 browser acceptance passed: ' + receipt.steps.length + ' steps, ' + receipt.extra_scenarios.length + ' extra scenarios');
  } catch (error) {
    fs.mkdirSync(path.join(root, '.local'), { recursive: true });
    if (page) {
      fs.writeFileSync(path.join(root, '.local', 'oct1-09-browser-failure.txt'), page.url() + '\n' + (await page.locator('body').innerText().catch(() => '')));
      await page.screenshot({ path: path.join(root, '.local', 'oct1-09-browser-failure.png'), fullPage: true }).catch(() => {});
    }
    fs.writeFileSync(path.join(root, '.local', 'oct1-09-browser-partial.json'), JSON.stringify(receipt, null, 2));
    throw error;
  } finally {
    if (browser) await browser.close();
    await stop(apiProcess);
    await stop(ui);
  }
})().catch((e) => { console.error(e); process.exitCode = 1; });
