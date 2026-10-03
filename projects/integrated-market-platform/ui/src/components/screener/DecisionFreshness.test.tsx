import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DecisionFreshness } from './DecisionFreshness';
const evidence = (mode: string, state: string) => ({capability:'quote',source:'Provider',delivery_mode:mode,freshness_status:state,decision_admissibility:state==='STALE'?'BLOCKED':'ADMISSIBLE',eligible_for_current_decision:state==='CURRENT',eligible_for_reference:false,basis:'PROVIDER_EVENT_TIME',as_of:'2026-10-02T18:32:00Z',received_at:null,fetched_at:null,age_ms:1000,stale_after_ms:60000,policy:'quote/v1',policy_version:'v1',evaluated_at:'2026-10-02T18:32:01Z',valid_until:null,reason_codes:[]});
describe('DecisionFreshness',()=>{
  it.each(['REALTIME','DELAYED','SNAPSHOT','PUBLICATION_BASED'])('shows delivery %s separately', mode=>{
    render(<DecisionFreshness inputs={[evidence(mode,'CURRENT')]} />);
    expect(screen.getByText(new RegExp(mode.replaceAll('_',' ')))).toBeInTheDocument();
    fireEvent.click(screen.getByText(/quote ·/));
    expect(screen.getByText(/PROVIDER EVENT TIME/)).toBeInTheDocument();
    expect(screen.getByText(/quote\/v1/)).toBeInTheDocument();
  });
  it.each(['STALE','UNAVAILABLE','UNKNOWN','SESSION_CLOSED'])('exposes state %s', state=>{
    render(<DecisionFreshness inputs={[evidence('REALTIME',state)]} />);
    expect(screen.getByText(new RegExp(state.replaceAll('_',' ')))).toBeInTheDocument();
  });
  it('withdraws current evidence when server deadline expires',()=>{
    vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-02T18:32:00Z'));
    render(<DecisionFreshness inputs={[{...evidence('REALTIME','CURRENT'), valid_until:'2026-10-02T18:31:59Z'}]} />);
    expect(screen.getByText(/STALE/)).toBeInTheDocument(); vi.useRealTimers();
  });
  it('replaces old instrument evidence and never retains it on withdrawal',()=>{
    const {rerender}=render(<DecisionFreshness inputs={[{...evidence('REALTIME','CURRENT'),capability:'NVDA quote'}]} />);
    rerender(<DecisionFreshness inputs={[{...evidence('SNAPSHOT','STALE'),capability:'AMD quote'}]} />);
    expect(screen.queryByText(/NVDA/)).not.toBeInTheDocument();
    rerender(<DecisionFreshness />); expect(screen.queryByText(/AMD/)).not.toBeInTheDocument();
  });
});
