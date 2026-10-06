// SOFTWARE_CONTROLLED only. Requires isolated harness_sma_trailing_stop.py + Vite.
// Bars, quote, position and clock are controlled fixtures: this proves software behaviour, not market behaviour.
const { chromium } = require(process.env.IMP_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const base = process.env.IMP_OCT1_08_UI_URL || 'http://127.0.0.1:15108';
const api = process.env.IMP_OCT1_08_API_URL || 'http://127.0.0.1:18808';
const INSTRUMENT = 'US%3ANVDA';
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.IMP_CHROMIUM_PATH ? { executablePath: process.env.IMP_CHROMIUM_PATH } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
  page.setDefaultTimeout(20000);
  const receipt = { classification: 'SOFTWARE_CONTROLLED', clock: 'STEPPED_CONTROLLED', fixtures: ['completed bars', 'last-trade quote', 'held position', 'model proposal', 'auth'], steps: [], paper_submissions: 0, live_submissions: 0 };
  const harness = async (path) => (await page.request.get(api + '/acceptance/stop/' + path)).json();
  const get = async (path) => (await page.request.get(api + path)).json();
  const post = async (path, data) => { const r = await page.request.post(api + path, { data }); assert.equal(r.status(), 200, path + ' ' + (await r.text())); return r.json(); };
  const step = (id, name, detail = {}) => receipt.steps.push({ step: id, name, ...detail });
  const panel = page.locator('.sma-stop-panel');
  const value = async (label) => (await panel.locator('dl.paper-cockpit-meta > div', { has: page.locator('dt', { hasText: new RegExp('^' + label + '$') }) }).first().locator('dd').innerText()).trim();
  const status = () => page.getByTestId('sma-stop-status').innerText();
  const evaluate = async (expected) => {
    await panel.getByRole('button', { name: 'Evaluate Stop Now', exact: true }).click();
    await page.getByTestId('sma-stop-status').filter({ hasText: expected }).waitFor();
  };
  const decisions = async () => (await get('/screener/action-decisions?instrument=' + INSTRUMENT)).decisions;
  try {
    const start = await harness('metrics');
    assert.equal(start.paper_env, '1'); assert.equal(start.live_env, null);
    await harness('set?position=7&price=150&change=2');
    await page.goto(base + '/workspace/' + INSTRUMENT);
    await page.getByText('Paper', { exact: true }).first().click();
    await panel.getByRole('heading', { name: 'Risk control — SMA trailing stop' }).waitFor();
    await page.getByText('Long 7 sh').first().waitFor();
    step(1, 'Open Paper position context', { url: page.url(), position: 'LONG 7', source: 'Paper ledger projection (controlled fixture)' });

    await page.getByTestId('sma-stop-status').filter({ hasText: 'NOT CONFIGURED' }).waitFor();
    assert.match(await panel.innerText(), /not a resting broker stop order, and a breach never submits a Paper or Live order/);
    step(2, 'Open SMA stop risk-control view', { status: 'NOT_CONFIGURED', monitor_only: true });

    await panel.locator('summary', { hasText: 'Stop policy' }).click();
    assert.equal(await panel.getByLabel(/SMA window/).inputValue(), '20');
    assert.equal(await panel.getByLabel(/stop level|stop price|formula/i).count(), 0, 'no level or formula can be entered');
    await panel.getByRole('button', { name: 'Enable stop policy', exact: true }).click();
    await page.getByTestId('sma-stop-status').filter({ hasText: 'WARMING UP' }).waitFor();
    assert.match(await value('Window'), /20 completed 1m bars · reference test configuration — not optimized/);
    const config = await get('/paper/risk-control/sma-stop/config');
    step(3, 'Configure the bounded reference SMA policy', { policy_id: config.policy.policy_id, sma_window_bars: 20, bar_interval: '1m', config_label: config.policy.config_label });

    await harness('bar?close=' + Array(5).fill('148.00').join(','));
    await evaluate('WARMING UP');
    await panel.getByText('Warming up — 20 completed bars required; 5 available. No stop exists yet.').waitFor();
    assert.match(await value('Active stop'), /^Unavailable/);
    step(4, 'Warm-up state', { completed_bars: 5, required: 20, stop: null });

    await harness('bar?close=' + Array(15).fill('148.00').join(','));
    await evaluate('ACTIVE');
    step(5, 'Feed enough controlled completed bars', { completed_bars: 20 });
    assert.match(await value('Active stop'), /^\$148\.00 · LONG stop$/);
    step(6, 'Active stop', { active_stop: '148.00', label: 'LONG stop', status: await status() });
    assert.match(await value('Current SMA'), /^\$148\.0000/);
    step(7, 'SMA value', { sma: '148.0000' });

    await harness('bar?close=150.00');
    await evaluate('ACTIVE');
    await panel.locator('dd', { hasText: '$148.10 · LONG stop' }).waitFor();
    assert.equal(await value('Previous stop'), '$148.00');
    step(8, 'Long monotonic tightening', { sma: await value('Current SMA'), active_stop: '148.10', previous_stop: '148.00' });

    await harness('bar?close=146.00');
    await evaluate('ACTIVE');
    await panel.getByText('Stop held at previous level — trailing rule does not loosen protection.').waitFor();
    assert.match(await value('Active stop'), /^\$148\.10/); assert.equal(await value('Candidate stop'), '$148.00');
    step(9, 'Falling SMA does not loosen the long stop', { candidate_stop: '148.00', active_stop: '148.10', reason: 'MONOTONIC_CLAMP' });

    await harness('set?bars=STALE');
    await evaluate('STALE');
    await panel.getByText(/Stop update stale — last legitimate stop \$148\.10, last bar .* Reason: STALE_BAR_SOURCE\./).waitFor();
    assert.match(await value('Active stop'), /^\$148\.10/);
    step(11, 'Stale-bar state', { status: 'STALE', last_legitimate_stop: '148.10', reason: 'STALE_BAR_SOURCE' });

    await harness('set?bars=CURRENT');
    await harness('bar?close=148.00');
    await evaluate('ACTIVE');
    assert.match(await value('Active stop'), /^\$148\.10/);
    step(12, 'Valid bars restored', { status: 'ACTIVE', active_stop: '148.10' });

    // Persisted state survives a fresh service and repository over the same SQLite file.
    const before = await get('/paper/risk-control/sma-stop?instrument=' + INSTRUMENT);
    const reloaded = await harness('reload');
    const after = await get('/paper/risk-control/sma-stop?instrument=' + INSTRUMENT);
    assert.equal(after.stop.stop_state_id, before.stop.stop_state_id); assert.equal(after.stop.active_stop, '148.1'); assert.equal(reloaded.durability, 'SQLITE_LOCAL_STATE');
    step('12b', 'Stop state recovered from SQLite by a fresh service', { stop_state_id: after.stop.stop_state_id, active_stop: after.stop.active_stop, durability: reloaded.durability });

    // A current HOLD from the governed loop starts the OCT1-07 dwell.
    await post('/screener/reevaluation/configure', { scope: { universe: 'US_EQUITIES', search: '', sort: 'symbol', descending: false, filters: [], view: 'Overview', screen: '' }, requested_cadence_seconds: 60 });
    await post('/screener/reevaluation/start', {});
    await page.request.get(api + '/acceptance/reevaluation/tick');
    const held = await decisions();
    assert.equal(held[0].action_state, 'HOLD');
    const hold = JSON.stringify(held[0]);
    const calls = (await harness('metrics')).model_calls;

    await harness('bar?close=148.00&price=148.05');
    const tick = await (await page.request.get(api + '/acceptance/reevaluation/tick')).json();
    const cycle = (await get('/screener/reevaluation/history?limit=1')).cycles[0];
    const transition = cycle.transitions.find((t) => t.new_state === 'EXIT');
    assert.ok(transition, JSON.stringify(cycle.transitions));
    await evaluate('BREACHED');
    const breach = page.getByRole('alert', { name: 'SMA stop breached' });
    await breach.getByRole('heading', { name: 'SMA trailing stop breached' }).waitFor();
    const breachText = await breach.innerText();
    assert.match(breachText, /STOP\s+\$148\.10 · LONG stop/i); assert.match(breachText, /OBSERVED\s+\$148\.05 · last trade/i);
    step(13, 'Controlled long breach', { stop: '148.10', observed: '148.05', basis: 'LAST_TRADE_PRICE', status: 'BREACHED' });

    assert.match(breachText, /DECISION\s+EXIT/i); assert.match(breachText, /PAPER CLOSE\s+NOT SUBMITTED/i);
    const now = await decisions();
    const exit = now[0];
    assert.equal(exit.action_state, 'EXIT'); assert.equal(exit.model_proposal, null); assert.equal(exit.model.provider_id, null);
    step(14, 'Deterministic EXIT decision', { decision_id: exit.decision_id, previous_state: exit.previous_state, model_call: false, origin: exit.model.origin, paper_close: 'NOT_SUBMITTED' });

    assert.equal(exit.server_exit.policy_id, config.policy.policy_id); assert.equal(exit.server_exit.active_stop, '148.1'); assert.equal(exit.server_exit.trigger_price, '148.05');
    assert.equal(JSON.stringify(now[1]), hold, 'the earlier HOLD record is unchanged');
    const trace = exit.decision_trace_id;
    step(15, 'Stop policy and evidence in decision history', { policy_id: exit.server_exit.policy_id, active_stop: exit.server_exit.active_stop, previous_stop: exit.server_exit.previous_stop,
      trigger_price: exit.server_exit.trigger_price, triggered_at: exit.server_exit.triggered_at, evidence_ref: exit.server_exit.trigger_evidence.evidence_ref, decision_trace_id: trace, prior_hold_unchanged: true });

    const elapsed = (Date.parse(exit.decision_time) - Date.parse(held[0].decision_time)) / 1000;
    assert.ok(elapsed < 300, 'the exit happened inside the 300 second dwell: ' + elapsed);
    assert.ok(transition.reason_codes.includes('SAFETY_PRECEDENCE') && transition.reason_codes.includes('SMA_TRAILING_STOP_BREACHED'));
    assert.equal(transition.model_call, false); assert.equal(cycle.transitions.filter((t) => t.classification === 'CHURN_SUPPRESSED').length, 0);
    assert.equal((await harness('metrics')).model_calls, calls, 'no model call for the stop exit');
    step(16, 'Dwell did not block the safety exit', { seconds_since_hold: elapsed, dwell_seconds: 300, classification: transition.classification, reason_codes: transition.reason_codes, model_call: false, cycle_id: tick.cycles });

    await breach.getByRole('button', { name: 'Prepare Paper Exit', exact: true }).click();
    const quantity = page.getByLabel('Quantity', { exact: true });
    // The ticket exists before the handoff; wait for the handed-off draft to replace its default.
    await page.waitForFunction(() => [...document.querySelectorAll('label')].some((l) => /^Quantity/.test(l.textContent || '') && (l.querySelector('input') || document.getElementById(l.htmlFor) || {}).value === '7'));
    step(17, 'Existing Paper exit handoff opened', { url: page.url() });
    assert.equal(await quantity.inputValue(), '7');
    const ticket = await page.locator('.paper-cockpit-action').innerText();
    assert.match(ticket, /SELL/i);
    step(18, 'Ticket carries the current ledger quantity', { quantity: '7', side: 'SELL', quantity_authority: 'Paper ledger' });

    const afterHandoff = await harness('metrics');
    assert.equal(afterHandoff.submit_attempts, 0); assert.equal(afterHandoff.ledger_events, start.ledger_events);
    step(19, 'No automatic Paper submit', { submit_route_attempts: afterHandoff.submit_attempts, ledger_events_added: afterHandoff.ledger_events - start.ledger_events, ticket_revalidation_previews: afterHandoff.preview_attempts });
    assert.equal(afterHandoff.live_attempts, 0);
    step(20, 'No Live submit', { live_route_attempts: 0, live_env_enabled: false });

    await panel.locator('summary', { hasText: 'Replay evaluation' }).click();
    await panel.getByRole('button', { name: 'Read replay comparison', exact: true }).click();
    await panel.getByRole('heading', { name: 'Method comparison' }).waitFor();
    const evaluation = await get('/paper/risk-control/sma-stop/evaluation');
    step(21, 'Replay evaluation comparison opened', { evidence_class: evaluation.evidence_class, result_status: evaluation.result_status, episodes: evaluation.counts.episodes, evaluable: evaluation.counts.evaluable });
    const table = panel.getByRole('table', { name: /LONG episodes \(primary comparison\)/ });
    const row = async (name) => (await table.getByRole('rowheader', { name, exact: true }).locator('xpath=..').innerText()).replace(/\s+/g, ' ');
    const long = evaluation.aggregates.LONG;
    step(22, 'SMA trail compared with raw-price trail', { sma: await row('SMA trail'), raw: await row('Raw-price trail'), sma_mean_mae_bps: long.SMA_TRAIL.mean_mae_bps, raw_mean_mae_bps: long.RAW_PRICE_TRAIL.mean_mae_bps });
    step(23, 'Fixed initial stop compared', { fixed: await row('Fixed initial stop'), fixed_mean_mae_bps: long.FIXED_INITIAL_STOP.mean_mae_bps });
    step(24, 'No-trail / existing exit compared', { no_trail: await row('Existing / no-trail exit'), no_trail_mean_gross_return_bps: long.NO_TRAIL.mean_gross_return_bps, sma_mean_gross_return_bps: long.SMA_TRAIL.mean_gross_return_bps });
    const text = await panel.locator('section[aria-label="Method comparison"]').innerText();
    assert.match(text, /Conclusion: Insufficient evidence\. Evidence is insufficient for a directional or superiority claim\. Superiority claim: none\./);
    assert.doesNotMatch(text, /\b(best|superior to|outperform|optimal|profitable)\b/i);
    step(25, 'No-superiority conclusion', { conclusion: evaluation.conclusion.conclusion, in_sample_pattern: evaluation.conclusion.in_sample_pattern, superiority_claim: evaluation.conclusion.superiority_claim });
    await panel.locator('summary', { hasText: 'Provenance and hashes' }).click();
    await panel.getByText(evaluation.definition_hash).waitFor(); await panel.getByText(evaluation.result_hash).waitFor();
    step(26, 'Provenance and config hash', { definition_hash: evaluation.definition_hash, input_hash: evaluation.input_hash, result_hash: evaluation.result_hash, dataset_fingerprint: evaluation.provenance.dataset_fingerprint });
    const end = await harness('metrics');
    assert.equal(end.corpus_sha256, start.corpus_sha256); assert.equal(end.corpus_sha256, evaluation.provenance.normalized_sha256);
    step(27, 'Historical bars unchanged', { corpus_sha256_before: start.corpus_sha256, corpus_sha256_after: end.corpus_sha256, matches_receipt: true });
    fs.mkdirSync('.local', { recursive: true });
    await page.screenshot({ path: '.local/oct1-08-breach.png', fullPage: true });

    // 10: short behaviour on a controlled held-position fixture. Paper short authority is unchanged.
    await harness('set?position=-7&price=140');
    await harness('bar?close=146.00');
    await page.goto(base + '/workspace/' + INSTRUMENT);
    await page.getByText('Paper', { exact: true }).first().click();
    await panel.getByRole('heading', { name: 'Risk control — SMA trailing stop' }).waitFor();
    await page.getByTestId('sma-stop-status').waitFor();
    await evaluate('ACTIVE');
    const first = await get('/paper/risk-control/sma-stop?instrument=' + INSTRUMENT);
    assert.equal(first.stop.side, 'SHORT'); assert.notEqual(first.stop.stop_state_id, after.stop.stop_state_id);
    assert.match(await value('Active stop'), /SHORT stop$/);
    await harness('bar?close=140.00');
    await evaluate('ACTIVE');
    const tightened = await get('/paper/risk-control/sma-stop?instrument=' + INSTRUMENT);
    assert.ok(Number(tightened.stop.active_stop) < Number(first.stop.active_stop), 'a short stop tightens downward');
    await harness('bar?close=160.00');
    await evaluate('ACTIVE');
    await panel.getByText('Stop held at previous level — trailing rule does not loosen protection.').waitFor();
    const clamped = await get('/paper/risk-control/sma-stop?instrument=' + INSTRUMENT);
    assert.equal(clamped.stop.active_stop, tightened.stop.active_stop); assert.ok(Number(clamped.stop.candidate_stop) > Number(clamped.stop.active_stop));
    step(10, 'Short monotonic behaviour (controlled fixture)', { first_stop: first.stop.active_stop, tightened_stop: tightened.stop.active_stop, rising_candidate: clamped.stop.candidate_stop,
      held_stop: clamped.stop.active_stop, long_episode_closed_as: 'POSITION_REVERSED', paper_short_authority: 'UNCHANGED' });
    await page.screenshot({ path: '.local/oct1-08-short.png', fullPage: true });

    const final = await harness('metrics');
    assert.equal(final.submit_attempts, 0); assert.equal(final.live_attempts, 0); assert.equal(final.ledger_events, start.ledger_events);
    receipt.metrics = { model_calls: final.model_calls, decisions: final.decisions, cycles: final.cycles, stop_events: final.stop_events, completed_bars_fed: final.bars,
      paper_submit_attempts: final.submit_attempts, live_attempts: final.live_attempts, ticket_revalidation_previews: final.preview_attempts, ledger_events_added: final.ledger_events - start.ledger_events };
    receipt.steps.sort((a, b) => String(a.step).localeCompare(String(b.step), undefined, { numeric: true }));
    fs.writeFileSync('artifacts/oct1-08-browser.json', JSON.stringify(receipt, null, 2) + '\n');
    console.log(JSON.stringify(receipt));
  } catch (error) {
    fs.mkdirSync('.local', { recursive: true });
    fs.writeFileSync('.local/oct1-08-browser-failure.txt', await page.locator('body').innerText());
    await page.screenshot({ path: '.local/oct1-08-browser-failure.png', fullPage: true });
    throw error;
  } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exitCode = 1; });
