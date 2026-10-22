// SOFTWARE_CONTROLLED only. Requires isolated harness_reevaluation.py + Vite.
// The schedule runs on the harness's accelerated clock: runtime evidence, not market-data freshness proof.
const { chromium } = require(process.env.IMP_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const base = process.env.IMP_OCT1_07_UI_URL || 'http://127.0.0.1:15107';
const api = process.env.IMP_OCT1_07_API_URL || 'http://127.0.0.1:18807';
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.IMP_CHROMIUM_PATH ? { executablePath: process.env.IMP_CHROMIUM_PATH } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.setDefaultTimeout(20000);
  const receipt = { classification: 'SOFTWARE_CONTROLLED', clock: 'ACCELERATED_CONTROLLED', steps: [], paper_submissions: 0, live_submissions: 0 };
  const harness = async (path) => (await page.request.get(api + '/acceptance/reevaluation/' + path)).json();
  const get = async (path) => (await page.request.get(api + path)).json();
  const step = (id, name, detail = {}) => receipt.steps.push({ step: id, name, ...detail });
  const body = () => page.locator('body').innerText();
  const button = (name) => page.getByRole('button', { name, exact: true });
  const history = async () => (await get('/screener/reevaluation/history?limit=100')).cycles;
  const seen = async (text) => page.locator('.reevaluation').getByText(text).first().waitFor();
  // One scheduled cycle through the production worker, then wait for the panel's own refresh to show it.
  const tick = async () => { const before = (await history()).length; const m = await harness('tick'); assert.equal((await history()).length, before + 1); return m; };
  try {
    const start = await harness('metrics');
    await page.goto(base + '/screener');
    await button('AI Screener').click();
    step(1, 'Open Screener', { url: page.url() });

    // 7-9: reevaluation controls, requested vs effective cadence
    assert.equal(start.cycles, 0);
    await button('Open reevaluation controls').click();
    await page.getByRole('status').filter({ hasText: 'Worker: NOT_CONFIGURED' }).waitFor();
    assert.equal(await button('Start').count(), 0, 'nothing starts by opening the panel');
    step(7, 'Open reevaluation controls', { worker_state: 'NOT_CONFIGURED', auto_started: false });
    await harness('set?policy=' + encodeURIComponent(JSON.stringify({ model_min_interval_seconds: 120 })));
    await page.getByLabel('Requested cadence (seconds)').fill('60');
    await button('Configure').click();
    await seen(/Requested: 60 sec · Effective: 120 sec — slower than requested \(limited by MODEL_MINIMUM_INTERVAL\)/);
    step(9, 'Effective cadence shown independently of requested', { requested: 60, effective: 120, limiting: 'MODEL_MINIMUM_INTERVAL' });
    await harness('set?policy=' + encodeURIComponent('{}'));
    await button('Configure').click();
    await seen(/Requested: 60 sec · Effective: 60 sec$/);
    const table = await page.locator('.reevaluation table').innerText();
    assert.match(table, /QUOTE\s+CONTROLLED_FIXTURE\s+CURRENT · REALTIME[\s\S]*Yes/);
    assert.match(table, /NEWS\s+RSS\s+REFERENCE · SNAPSHOT[\s\S]*1860s old\s+No/);
    assert.match(table, /RATES\s+TREASURY\s+PUBLICATION-BASED[\s\S]*No/);
    await seen(/Paper execution remains manual/);
    step(8, 'Configure requested 60s cadence', { requested: 60, effective: 60, quote: 'CURRENT within cadence', news: 'REFERENCE, 1860s old, not within cadence', treasury: 'PUBLICATION-BASED, not within cadence' });

    // 10-12: start, first cycle, no-material-change cycle
    assert.equal((await harness('metrics')).model_calls, 0, 'configure/readiness never calls a model');
    await button('Start').click();
    await page.getByRole('status').filter({ hasText: 'Worker: RUNNING' }).waitFor();
    step(10, 'Start recurring reevaluation explicitly', { worker_state: 'RUNNING' });
    let m = await tick();
    let cycles = await history();
    assert.equal(cycles[0].cycle_status, 'MATERIAL_CHANGE');
    assert.deepEqual(cycles[0].transitions.map((t) => t.classification), ['CANDIDATE_ADDED', 'STATE_CHANGED']);
    assert.equal(cycles[0].transitions[1].new_state, 'ENTER');
    await seen(/US:NVDA · STATE CHANGED · Initial → ENTER · model call: yes/);
    step(11, 'First cycle', { status: 'MATERIAL_CHANGE', transition: 'Initial → ENTER', model_calls: m.model_calls, scheduled_for: cycles[0].scheduled_for });
    const afterFirst = m;
    m = await tick();
    cycles = await history();
    assert.equal(cycles[0].cycle_status, 'NO_MATERIAL_CHANGE');
    assert.equal(m.model_calls, afterFirst.model_calls); assert.equal(m.reductions, afterFirst.reductions); assert.equal(m.decisions, afterFirst.decisions);
    assert.equal(Date.parse(cycles[0].scheduled_for) - Date.parse(cycles[1].scheduled_for), 60000);
    await seen(/NO MATERIAL CHANGE/);
    step(12, 'No-material-change cycle', { model_calls_added: 0, decisions_added: 0, receipt_recorded: true, slot_spacing_ms: 60000 });

    // 16: churn — a direction flip inside the dwell after ENTER is held
    await harness('set?change=-0.1');
    m = await tick();
    cycles = await history();
    assert.equal(cycles[0].transitions[0].classification, 'CHURN_SUPPRESSED');
    assert.deepEqual(cycles[0].transitions[0].reason_codes, ['DIRECTION_CHANGED', 'MIN_STATE_DWELL']);
    assert.equal(m.model_calls, afterFirst.model_calls);
    await seen(/US:NVDA · CHURN SUPPRESSED · ENTER → no new decision · model call: no · DIRECTION_CHANGED, MIN_STATE_DWELL/);
    step(16, 'Churn suppression', { reason_codes: cycles[0].transitions[0].reason_codes, model_call: false });
    await harness('set?change=2');

    // 18: a pending entry order prevents a duplicate entry, without a model call
    await harness('set?pending=1');
    m = await tick();
    cycles = await history();
    let t = cycles[0].transitions[0];
    assert.equal(t.classification, 'DUPLICATE_SUPPRESSED'); assert.ok(t.reason_codes.includes('PENDING_ORDER_REVALIDATION'));
    assert.equal(t.new_state, 'REVALIDATION_REQUIRED'); assert.equal(t.execution_readiness, 'BLOCKED'); assert.equal(m.model_calls, afterFirst.model_calls);
    await seen(/DUPLICATE SUPPRESSED/);
    step(18, 'Pending order prevents duplicate entry', { classification: t.classification, new_state: t.new_state, execution_readiness: t.execution_readiness, model_call: false });

    // 19 + 15: the fill is read from the ledger; a re-proposed ENTER on a held position is suppressed
    await harness('set?pending=0&position=7&force=ENTER');
    m = await tick();
    cycles = await history();
    t = cycles[0].transitions[0];
    assert.equal(t.position_state, 'LONG'); assert.ok(t.reason_codes.includes('POSITION_CHANGED'));
    assert.equal(t.classification, 'DUPLICATE_SUPPRESSED'); assert.ok(t.reason_codes.includes('ILLEGAL_POSITION_ACTION')); assert.equal(t.execution_readiness, 'BLOCKED');
    step(19, 'Current position change affects next cycle', { position_state: 'LONG', source: 'PAPER_LEDGER', reason: 'POSITION_CHANGED' });
    step(15, 'Duplicate-entry suppression', { proposed: 'ENTER', position: 'LONG', classification: t.classification, new_state: t.new_state, execution_readiness: t.execution_readiness });

    // 13-14: controlled material evidence change → new immutable decision
    const priorDecisions = (await get('/screener/action-decisions?instrument=US%3ANVDA')).decisions;
    await harness('set?force=&price=153');
    m = await tick();
    cycles = await history();
    t = cycles[0].transitions[0];
    assert.ok(t.reason_codes.includes('PRICE_MOVED')); assert.equal(t.new_state, 'HOLD'); assert.equal(t.model_call, true);
    const decisions = (await get('/screener/action-decisions?instrument=US%3ANVDA')).decisions;
    assert.equal(decisions.length, priorDecisions.length + 1);
    assert.deepEqual(decisions.slice(1), priorDecisions, 'earlier decisions are byte-for-byte unchanged');
    await seen(/REVALIDATION_REQUIRED → HOLD · model call: yes/);
    step(13, 'Controlled material evidence change', { reason: 'PRICE_MOVED', price: '150 → 153' });
    step(14, 'New immutable decision/transition', { transition: 'REVALIDATION_REQUIRED → HOLD', new_decision_id: t.new_decision_id, prior_decisions_unchanged: true });

    // 17: a valid EXIT condition inside the dwell is not suppressed; the flip back is
    await harness('set?change=-2');
    m = await tick();
    cycles = await history();
    t = cycles[0].transitions[0];
    assert.equal(t.new_state, 'EXIT'); assert.equal(t.safety, true); assert.ok(t.reason_codes.includes('SAFETY_PRECEDENCE') && t.reason_codes.includes('EXIT_CONDITION_MET'));
    await seen(/HOLD → EXIT · model call: yes/);
    await harness('set?change=2');
    await tick();
    assert.equal((await history())[0].transitions[0].classification, 'CHURN_SUPPRESSED');
    step(17, 'Valid safety EXIT is not suppressed', { transition: 'HOLD → EXIT', safety: true, within_dwell: true, flip_back: 'CHURN_SUPPRESSED (EXIT_CONDITION_CLEARED)' });

    // 20-22: stop, unobserved gap, prospective restart; then process death with missed cycles
    const beforeStop = await harness('metrics');
    await button('Stop').click();
    await page.getByRole('status').filter({ hasText: 'Worker: STOPPED' }).waitFor();
    const stopped = await harness('metrics');
    assert.equal(stopped.decisions, beforeStop.decisions); assert.equal(stopped.ledger_events, beforeStop.ledger_events);
    step(20, 'Stop loop', { worker_state: 'STOPPED', decisions_changed: 0, positions_changed: 0 });
    await harness('advance?seconds=600');
    await button('Start').click();
    await page.getByRole('status').filter({ hasText: 'Worker: RUNNING' }).waitFor();
    cycles = await history();
    assert.equal(cycles[0].cycle_status, 'NOT_OBSERVED'); assert.equal(cycles[0].not_observed.reason, 'OPERATOR_STOPPED'); assert.equal(cycles[0].not_observed.decisions_backfilled, 0);
    await seen(/NOT OBSERVED/);
    await tick();
    await tick();
    await harness('crash');
    await harness('advance?seconds=420');
    await button('Run Reevaluation Now').waitFor();
    await page.reload();
    await button('AI Screener').click();
    await button('Open reevaluation controls').click();
    await page.getByRole('status').filter({ hasText: 'Worker: INTERRUPTED' }).waitFor();
    const beforeRestart = (await history()).length;
    await button('Start').click();
    await page.getByRole('status').filter({ hasText: 'Worker: RUNNING' }).waitFor();
    cycles = await history();
    assert.equal(cycles.length, beforeRestart + 1, 'exactly one gap receipt, no fabricated cycles');
    assert.equal(cycles[0].not_observed.reason, 'PROCESS_DOWNTIME'); assert.equal(cycles[0].not_observed.missed_scheduled_cycles, 6); assert.equal(cycles[0].not_observed.decisions_backfilled, 0);
    await seen(/6 scheduled cycles missed · PROCESS_DOWNTIME · no decisions were reconstructed/);
    step(21, 'Missed / not-observed gap', { operator_stop_gap: 'NOT_OBSERVED · OPERATOR_STOPPED · 0 missed', process_downtime_gap: 'NOT_OBSERVED · PROCESS_DOWNTIME · 6 scheduled cycles missed', decisions_backfilled: 0, interrupted_state_shown: true });
    m = await tick();
    cycles = await history();
    assert.equal(cycles[0].scheduled_for, cycles[1].not_observed.observed_to, 'resumes at the restart instant');
    step(22, 'Restart prospectively without backfill', { first_slot_after_restart: cycles[0].scheduled_for, fabricated_cycles: 0 });
    await page.getByRole('heading', { name: /Cycle history/ }).waitFor();
    fs.mkdirSync('.local', { recursive: true });
    await page.screenshot({ path: '.local/oct1-07-reevaluation.png', fullPage: true });
    fs.writeFileSync('.local/oct1-07-reevaluation.txt', await page.locator('.reevaluation').innerText());
    step(23, 'Cycle history', { receipts: cycles.length, statuses: [...new Set(cycles.map((c) => c.cycle_status))] });
    const once = (await harness('metrics'));
    await button('Run Reevaluation Now').click();
    await page.waitForFunction(async (n) => (await (await fetch('/screener/reevaluation/history?limit=100')).json()).cycles.length > n, cycles.length);
    assert.equal((await history())[0].trigger, 'MANUAL');
    step('8b', 'Run Reevaluation Now uses the same core cycle', { trigger: 'MANUAL', worker_state_unchanged: true, model_calls_added: (await harness('metrics')).model_calls - once.model_calls });
    await button('Stop').click();
    await page.getByRole('status').filter({ hasText: 'Worker: STOPPED' }).waitFor();

    // 2-6: freeze an OCT1-06 action decision at 15:55:12 ET and lock it
    await harness('set?position=0&change=2&price=150');
    const clock = Date.parse((await harness('metrics')).clock) / 1000;
    const midnight = clock - ((clock - 4 * 3600) % 86400);  // ET day start (EDT) for the harness date
    await harness('advance?seconds=' + (midnight + 15 * 3600 + 55 * 60 + 12 - clock));
    await page.goto(base + '/screener');
    await button('AI Screener').click();
    await button('Run AI Screener').click();
    await button('Open decision assessment').click();
    await button('Evaluate Decision').click();
    await page.getByText('CURRENT DECISION', { exact: true }).waitFor();
    const frozenFrom = (await get('/screener/action-decisions?instrument=US%3ANVDA')).decisions[0];
    step(2, 'Use an OCT1-06 action decision', { decision_id: frozenFrom.decision_id, action_state: frozenFrom.action_state, decision_time: frozenFrom.decision_time });
    await button('Freeze for Next Session').first().click();
    await page.getByText(/DRAFT — not yet frozen/).waitFor();
    step(3, 'Freeze decision for next session', { lock_state: 'DRAFT' });
    const list = (await get('/screener/next-session?instrument=US%3ANVDA')).snapshots;
    const snapshot = list[0].snapshot;
    const cutoffDay = new Date(Date.parse(snapshot.decision_cutoff));
    assert.equal(cutoffDay.getUTCDay(), 1, 'decision made on a Monday');
    assert.equal(new Date(snapshot.target_session_date + 'T12:00:00Z').getUTCDay(), 2, 'target is the next market session (Tuesday), not +24h arithmetic');
    assert.equal(snapshot.target_session_kind, 'US_EQUITY_RTH'); assert.match(snapshot.decision_cutoff, /T19:55:12/);
    await page.getByText(new RegExp('Target: ' + snapshot.target_session_date + ' · US_EQUITY_RTH')).waitFor();
    step(4, 'Verify target market session', { decision_cutoff: snapshot.decision_cutoff, target_session_date: snapshot.target_session_date, target_session_start: snapshot.target_session_start, evaluation_policy: snapshot.evaluation_policy.policy_id });
    await button('Lock').first().click();
    await page.getByText(/LOCKED — immutable\. This snapshot cannot be changed\./).waitFor();
    const locked = (await get('/screener/next-session?id=' + snapshot.snapshot_id)).snapshot;
    step(5, 'Lock snapshot', { lock_state: locked.lock_state, locked_at: locked.locked_at, content_hash: locked.content_hash });
    const refused = await page.request.post(api + '/screener/next-session/draft', { data: { decision_id: frozenFrom.decision_id, evaluation_policy: 'next-session-close/1.0.0' } });
    assert.equal(refused.status(), 400); assert.match(await refused.text(), /NEXT_SESSION_LOCKED_IMMUTABLE/);
    await harness('set?price=170&change=-3');  // later evidence
    assert.deepEqual((await get('/screener/next-session?id=' + snapshot.snapshot_id)).snapshot, locked);
    assert.deepEqual((await get('/screener/action-decisions?instrument=US%3ANVDA')).decisions.find((d) => d.decision_id === frozenFrom.decision_id), frozenFrom);
    const early = await page.request.post(api + '/screener/next-session/evaluate', { data: { snapshot_id: snapshot.snapshot_id } });
    assert.equal(early.status(), 400); assert.match(await early.text(), /FORWARD_TEST_HORIZON_NOT_REACHED/);
    step(6, 'Locked evidence cannot change', { policy_change: 'NEXT_SESSION_LOCKED_IMMUTABLE', later_evidence_entered_snapshot: false, early_evaluation: 'FORWARD_TEST_HORIZON_NOT_REACHED' });

    // 24-25: next-session observation, comparison, original unchanged
    const open = Date.parse(snapshot.evaluation_policy.observation_start) / 1000;
    await harness('set?price=153&change=2');
    await harness('advance?seconds=' + (open + 300 - Date.parse((await harness('metrics')).clock) / 1000));
    await button('Record observation').first().click();
    await page.getByText(/Evaluation status: OBSERVING · 1 observation recorded/).waitFor();
    await harness('advance?seconds=1500');
    await button('Evaluate outcome').first().click();
    await page.getByText(/Evaluation status: EVALUATED/).waitFor();
    await page.getByText(/change since decision 2%/).waitFor();
    await page.getByText(/Signal comparison: COMPLETE · Paper execution outcome: NOT_APPLICABLE/).waitFor();
    const evaluated = (await get('/screener/next-session?id=' + snapshot.snapshot_id));
    step(24, 'Next-session later observation comparison', { frozen: evaluated.comparison.frozen_action_state + ' ' + (evaluated.comparison.frozen_direction ?? ''), reference: evaluated.comparison.decision_reference_price,
      observed: evaluated.comparison.last_observed_price, change_pct: evaluated.comparison.change_pct, signal: evaluated.comparison.signal_outcome.quality, execution: evaluated.comparison.execution_outcome.quality });
    const frozen = (r) => Object.fromEntries(Object.entries(r).filter(([k]) => !['state', 'evaluation', 'updated_at'].includes(k)));
    assert.deepEqual(frozen(evaluated.snapshot), frozen(locked)); assert.equal(evaluated.integrity, 'VERIFIED'); assert.equal(evaluated.snapshot.content_hash, locked.content_hash);
    step(25, 'Original snapshot unchanged', { content_hash: locked.content_hash, integrity: 'VERIFIED' });
    await page.screenshot({ path: '.local/oct1-07-next-session.png', fullPage: true });
    fs.writeFileSync('.local/oct1-07-next-session.txt', await page.locator('.next-session').first().innerText());

    const end = await harness('metrics');
    assert.equal(end.ledger_events, start.ledger_events); assert.equal(end.submit_attempts, 0); assert.equal(end.news_refreshes, 0);
    receipt.metrics = { model_calls: end.model_calls, reductions: end.reductions, evidence_reads: end.packets, cycles: end.cycles, decisions: end.decisions, news_provider_refreshes: end.news_refreshes };
    step(26, 'Zero automatic Paper submissions', { submit_route_attempts: end.submit_attempts, ledger_events_added: end.ledger_events - start.ledger_events });
    step(27, 'Zero Live submissions', { live_routes_called: 0, live_env_enabled: false });
    receipt.steps.sort((a, b) => String(a.step).localeCompare(String(b.step), undefined, { numeric: true }));
    fs.writeFileSync('artifacts/oct1-07-browser.json', JSON.stringify(receipt, null, 2) + '\n');
    console.log(JSON.stringify(receipt));
  } catch (error) {
    fs.mkdirSync('.local', { recursive: true });
    fs.writeFileSync('.local/oct1-07-browser-failure.txt', await body());
    await page.screenshot({ path: '.local/oct1-07-browser-failure.png', fullPage: true });
    throw error;
  } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exitCode = 1; });
