import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DecisionFreshness, deliveryText, freshnessRollup, freshnessText } from './DecisionFreshness';
import { PanelFrame, SpecialistContext, type SpecialistSelection } from './panels/shared';
const evidence = (mode: string, state: string) => ({capability:'quote',source:'Provider',delivery_mode:mode,freshness_status:state,decision_admissibility:state==='STALE'?'BLOCKED':'ADMISSIBLE',eligible_for_current_decision:state==='CURRENT',eligible_for_reference:false,basis:'PROVIDER_EVENT_TIME',as_of:'2026-10-02T18:32:00Z',received_at:null,fetched_at:null,age_ms:1000,stale_after_ms:60000,policy:'quote/v1',policy_version:'v1',evaluated_at:'2026-10-02T18:32:01Z',valid_until:null,reason_codes:[]});
const inputLine = () => within(screen.getByRole('list', { name: 'Decision input freshness' })).getByText(/^Quote$/).closest('summary')!;
describe('DecisionFreshness',()=>{
  // Sprint 3 item 27: one collapsed "Data freshness" section; each input is one plain line, its record one level down.
  it.each(['REALTIME','DELAYED','SNAPSHOT','PUBLICATION_BASED'])('shows delivery %s separately', mode=>{
    render(<DecisionFreshness inputs={[evidence(mode,'CURRENT')]} />);
    expect(within(inputLine()).getByTitle(mode)).toHaveTextContent(deliveryText(mode));
    fireEvent.click(inputLine());
    expect(screen.getByTitle('PROVIDER_EVENT_TIME')).toHaveTextContent('Provider event time');
    expect(screen.getByText(/quote\/v1/)).toBeInTheDocument();
  });
  it.each(['STALE','UNAVAILABLE','UNKNOWN','SESSION_CLOSED'])('exposes state %s', state=>{
    render(<DecisionFreshness inputs={[evidence('REALTIME',state)]} />);
    expect(within(inputLine()).getByTitle(state)).toHaveTextContent(freshnessText(state));
  });
  it('withdraws current evidence when server deadline expires',()=>{
    vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-02T18:32:00Z'));
    render(<DecisionFreshness inputs={[{...evidence('REALTIME','CURRENT'), valid_until:'2026-10-02T18:31:59Z'}]} />);
    expect(within(inputLine()).getByTitle('STALE')).toHaveTextContent('stale');
    expect(screen.getByText('Server freshness window expired')).toHaveAttribute('title', 'SERVER_POLICY_EXPIRED');
    vi.useRealTimers();
  });
  it('replaces old instrument evidence and never retains it on withdrawal',()=>{
    const {rerender}=render(<DecisionFreshness inputs={[{...evidence('REALTIME','CURRENT'),capability:'NVDA quote'}]} />);
    rerender(<DecisionFreshness inputs={[{...evidence('SNAPSHOT','STALE'),capability:'AMD quote'}]} />);
    expect(screen.queryByText(/NVDA/i)).not.toBeInTheDocument();
    rerender(<DecisionFreshness />); expect(screen.queryByText(/AMD/i)).not.toBeInTheDocument();
  });
  it('is one collapsed section with a roll-up badge, worst first',()=>{
    const { container } = render(<DecisionFreshness inputs={[evidence('REALTIME','CURRENT'), evidence('SNAPSHOT','STALE'), evidence('REALTIME','UNAVAILABLE'), evidence('DELAYED','STALE')]} />);
    const outer = container.querySelector('details.decision-freshness') as HTMLDetailsElement;
    expect(outer.open).toBe(false);
    expect(container.querySelectorAll('details.decision-freshness')).toHaveLength(1);
    expect(outer.querySelector('summary')).toHaveTextContent('Data freshness 1 unavailable · 2 stale · 4 inputs');
    expect(outer.querySelector('.decision-rollup')).toHaveClass('bad');
    // No raw codes or ISO times on the lines a reader sees first.
    expect(outer.textContent).not.toMatch(/REALTIME|PROVIDER_EVENT_TIME|\d{4}-\d{2}-\d{2}T/);
  });
  it('rolls up to "All current" and renders nothing without inputs',()=>{
    expect(freshnessRollup([evidence('REALTIME','CURRENT')], Date.now())).toEqual({ tone: 'ok', text: 'All current' });
    expect(freshnessRollup([evidence('REALTIME','UNKNOWN')], Date.now())).toEqual({ tone: 'warn', text: '1 freshness unknown' });
    expect(freshnessRollup([], Date.now())).toBeNull();
    const { container } = render(<DecisionFreshness inputs={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
  it('puts the roll-up in the panel header only when an input is not current, and the detail below the content',()=>{
    const selection = { row: null, settledId: null, universe: 'US_EQUITIES', supportedPanels: new Set(), quote: undefined, filters: [], demand: null,
      actions: { close() {}, move() {}, resize() {} } } as unknown as SpecialistSelection;
    const frame = (inputs: ReturnType<typeof evidence>[]) => <SpecialistContext.Provider value={selection}>
      <PanelFrame id="options" decisionInputs={inputs}><p>Panel content</p></PanelFrame></SpecialistContext.Provider>;
    const { container, rerender } = render(frame([evidence('REALTIME','CURRENT')]));
    expect(container.querySelector('.screener-panel-header .decision-rollup')).toBeNull();
    rerender(frame([evidence('REALTIME','CURRENT'), evidence('SNAPSHOT','STALE')]));
    const badge = container.querySelector('.screener-panel-header .decision-rollup')!;
    expect(badge).toHaveTextContent('1 stale');
    expect(badge).toHaveClass('bad');
    // The collapsed detail follows the panel's own content.
    const body = container.querySelector('.screener-panel-body')!;
    expect(body.firstElementChild).toHaveTextContent('Panel content');
    expect(body.lastElementChild).toHaveClass('decision-freshness');
  });
  it('shows times as ET <time> elements with UTC on hover',()=>{
    render(<DecisionFreshness inputs={[evidence('REALTIME','CURRENT')]} />);
    fireEvent.click(inputLine());
    const asOf = document.querySelector('time[datetime="2026-10-02T18:32:00Z"]')!;
    expect(asOf.textContent).toContain('14:32');
    expect(asOf.getAttribute('title')).toContain('2026-10-02 18:32:00 UTC');
    expect(asOf.textContent).toMatch(/ ET$/);
  });
});
