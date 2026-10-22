import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { evaluationApi, type EvaluationSummary, type EvaluationRecord, type EvaluationMetrics } from "../../api/prospectiveEvaluation";
import { usePaperPortfolioQuery } from "../../api/hooks";
import { tradeLifecycle } from "../../api/screenerLifecycle";
import LifecycleDetail from "../screener/lifecycle/LifecycleDetail";
import "./evaluation.css";

const unavailable = "Unavailable";
const money = (value: unknown) => value == null ? unavailable : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value) / 100);
const number = (value: unknown) => value == null ? unavailable : String(value);
const percent = (value: unknown) => value == null ? unavailable : `${(Number(value) * 100).toFixed(2)}%`;
function MetricGrid({ metrics: m }: { metrics: EvaluationMetrics }) {
  const items = [
    ["Completed trades / open censored / unavailable", `${m.completed_trades} / ${m.open_censored} / ${m.unavailable}`],
    ["Wins / losses / flat", `${m.wins} / ${m.losses} / ${m.flat}`], ["Win rate (completed nonflat)", percent(m.win_rate)],
    ["Net completed Paper P&L", money(m.net_pnl_minor)], ["Gross completed Paper P&L", money(m.gross_pnl_minor)],
    ["Explicit costs", money(m.costs_minor)], ["Average win / loss", `${money(m.average_win_minor)} / ${money(m.average_loss_minor)}`],
    ["Median win / loss", `${money(m.median_win_minor)} / ${money(m.median_loss_minor)}`],
    ["Payoff ratio", number(m.payoff_ratio)], ["Expectancy / completed trade", money(m.expectancy_minor)],
    ["Profit factor", `${number(m.profit_factor)} (${m.profit_factor_status})`],
    ["Longest / current losing streak", `${m.longest_losing_streak} / ${m.current_losing_streak}`],
    ["Exposure seconds / elapsed time in market", `${number(m.exposure_seconds)} / ${percent(m.time_in_market_fraction)}`],
    ["Executed notional / turnover", `${money(m.executed_notional_minor)} / ${number(m.turnover)}`],
    ["Average / peak gross notional to equity", `${number(m.average_gross_notional_to_equity)} / ${number(m.peak_gross_notional_to_equity)}`],
    ["Signal observations / mean market move", `${m.signal_outcomes} / ${percent(m.signal_market_return_mean)}`],
    ["Mean directional signal return (not P&L)", percent(m.signal_directional_return_mean)],
  ];
  return <dl className="evaluation-metrics">{items.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}
export function EvaluationView({ report, records, onDetail, onFilter }: { report: EvaluationSummary; records: EvaluationRecord[]; onDetail: (id: string) => void; onFilter?: (dimension:string,label:string)=>void }) {
  const [dimension, setDimension] = useState("setup");
  const [label, setLabel] = useState("");
  const group = report.segments[dimension] ?? [];
  const selected = group.find(g => g.label === label);
  const rows = label ? records.filter(r => (r.segments?.[dimension] ?? "UNAVAILABLE") === label) : records;
  const dd = report.portfolio_metrics.drawdown;
  return <>
    <h1>Prospective outcome evaluation</h1>
    <div className="evaluation-boundary"><strong>{report.evidence_class}</strong><span>USD · N decisions {report.metrics.decisions} · N completed {report.metrics.completed_trades}</span><span>Cutoff <time>{report.cutoff}</time></span></div>
    <p className="evaluation-warning">{report.conclusion}: Insufficient sample for strong performance conclusions. Paper uses simulated fills. This view grants no live capital, model promotion, or FTEP authority.</p>
    <div className="evaluation-toolbar"><label>Group by <select value={dimension} onChange={e => { setDimension(e.target.value); setLabel(""); onFilter?.(e.target.value, ""); }}>{Object.keys(report.segments).map(d => <option key={d}>{d}</option>)}</select></label><label>Segment <select value={label} onChange={e => {setLabel(e.target.value);onFilter?.(dimension,e.target.value);}}><option value="">All admitted</option>{group.map(g => <option key={g.label}>{g.label}</option>)}</select></label></div>
    <h2>{selected ? `Segment: ${selected.label}` : "Admitted decision cohort"}</h2><MetricGrid metrics={selected?.metrics ?? report.metrics} />
    <h2>Account equity observations</h2><p>Whole selected Paper account; no AI causal attribution. {report.portfolio_metrics.snapshot_count} stored current snapshots; {report.portfolio_metrics.resolution}. Missing periods are not interpolated.</p>
    <dl className="evaluation-metrics"><div><dt>Observed equity endpoints / return</dt><dd>{money(report.portfolio_metrics.starting_equity_minor)} / {money(report.portfolio_metrics.ending_equity_minor)} / {percent(report.portfolio_metrics.observed_equity_return)}</dd></div><div><dt>Maximum observed drawdown</dt><dd>{dd ? `${money(dd.amount_minor)} / ${percent(dd.fraction)}` : unavailable}</dd></div><div><dt>Peak / trough / recovery / duration seconds</dt><dd>{dd ? `${dd.start ?? unavailable} / ${dd.trough ?? unavailable} / ${dd.recovered_at ?? "Unrecovered at last observation"} / ${number(dd.duration_seconds)}` : unavailable}</dd></div></dl>
    <h2>Weekly Paper results</h2><p>America/New_York Monday weeks; closed episodes allocated by close time. Equity returns use observed endpoints and may cover only part of a week.</p>
    <div className="evaluation-scroll"><table aria-label="Weekly Paper results"><thead><tr><th>Week</th><th>N closed</th><th>Net / costs</th><th>Observed equity return</th><th>Drawdown</th><th>Coverage</th></tr></thead><tbody>{report.weekly.map(w => <tr key={w.week}><td>{w.week}</td><td>{w.metrics.completed_trades}</td><td>{money(w.metrics.net_pnl_minor)} / {money(w.metrics.costs_minor)}</td><td>{percent(w.return_fraction)}</td><td>{w.drawdown ? money(w.drawdown.amount_minor) : unavailable}</td><td>{w.coverage}</td></tr>)}</tbody></table></div>{!report.weekly.length && <p>No completed-trade week available.</p>}
    <h2>Segment comparison</h2><p>Descriptive comparisons only. Labels come from frozen records; missing labels remain UNAVAILABLE.</p><div className="evaluation-scroll"><table aria-label="Segment comparison"><thead><tr><th>Stored label</th><th>N decisions / closed</th><th>Net P&L</th><th>Expectancy</th><th>Profit factor</th></tr></thead><tbody>{group.map(g => <tr key={g.label}><td>{g.label}</td><td>{g.metrics.decisions} / {g.metrics.completed_trades}</td><td>{money(g.metrics.net_pnl_minor)}</td><td>{money(g.metrics.expectancy_minor)}</td><td>{number(g.metrics.profit_factor)}</td></tr>)}</tbody></table></div>
    <h2>Admission and exclusions</h2><p>Considered {report.admission.total_considered}; admitted {report.admission.admitted}; excluded {report.admission.excluded}.</p><ul>{Object.entries(report.admission.reasons).map(([reason, n]) => <li key={reason}>{reason}: {n}</li>)}</ul>
    <h2>Decision records</h2><p>Each row retains its original proposal and evidence references. Signal market moves and Paper execution results are separate.</p><div className="evaluation-scroll"><table aria-label="Evaluation records"><thead><tr><th>Instrument / action</th><th>Class / quality</th><th>Execution</th><th>Net / costs</th><th>Signals</th><th>Admission</th><th>Evidence</th></tr></thead><tbody>{rows.map(r => <tr key={r.evaluation_id}><td>{r.instrument_id} / {r.action_state}</td><td>{r.evidence_class} / {number(r.quality)}</td><td>{r.execution_outcome?.state ?? unavailable}</td><td>{money(r.execution_outcome?.net_pnl_minor)} / {money(r.execution_outcome?.costs_minor)}</td><td>{r.signal_outcomes.length}</td><td>{r.excluded_reason ?? "Admitted"}</td><td><button onClick={() => onDetail(r.evaluation_id)}>Inspect {r.instrument_id}</button></td></tr>)}</tbody></table></div>
    <h2>Review findings</h2><ul>{report.review.map(text => <li key={text}>{text}</li>)}</ul><h2>Limitations</h2><ul>{report.limitations.map(text => <li key={text}>{text}</li>)}</ul>
    <details><summary>Reproducibility metadata</summary><dl className="evaluation-metadata">{Object.entries({run:report.run_id,cutoff:report.cutoff,code:report.git_sha,policy:report.evaluation_policy_id,metrics:report.metric_definition_version,fingerprint:report.input_fingerprint}).map(([k,v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></details>
  </>;
}
export default function EvaluationPage({mode}: {mode: "DEMO" | "PAPER" | "LIVE"}) {
  const portfolio = usePaperPortfolioQuery(mode === "DEMO" ? "DEMO" : "PAPER");
  const account = portfolio.data?.account.paper_account_id;
  const [filter,setFilter] = useState({dimension:"",label:""});
  const [cohort,setCohort] = useState("PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA");
  const [run,setRun] = useState(""); const [offset,setOffset] = useState(0); const [detailId,setDetailId] = useState("");
  const [message,setMessage] = useState(""); const [busy,setBusy] = useState(false); const [showLifecycle,setShowLifecycle] = useState(false);
  const params = new URLSearchParams(run ? {run_id:run} : {evidence_class:cohort});
  const summary = useQuery({queryKey:["evaluation",account,mode,run,cohort],queryFn:()=>evaluationApi.summary(params),enabled:Boolean(account)});
  const runs = useQuery({queryKey:["evaluation-runs",account],queryFn:evaluationApi.runs,enabled:Boolean(account)});
  const report = summary.data;
  const frozenParams = new URLSearchParams(run ? {run_id:run} : {evidence_class:cohort,cutoff:report?.cutoff ?? ""});
  const records = useQuery({queryKey:["evaluation-records",account,report?.run_id,offset,filter.dimension,filter.label],queryFn:()=>evaluationApi.records(new URLSearchParams({...Object.fromEntries(frozenParams),offset:String(offset),...(filter.label ? filter : {})})),enabled:Boolean(report)});
  const detail = useQuery({queryKey:["evaluation-detail",account,report?.run_id,detailId],queryFn:()=>evaluationApi.detail(new URLSearchParams({...Object.fromEntries(frozenParams),evaluation_id:detailId})),enabled:Boolean(report && detailId)});
  const lifecycle = useQuery({queryKey:["evaluation-lifecycle",account,detail.data?.lifecycle_id],queryFn:()=>tradeLifecycle(detail.data!.lifecycle_id!),enabled:Boolean(showLifecycle && detail.data?.lifecycle_id)});
  async function action(kind: "freeze" | "rerun") { if (!report) return; setBusy(true);try { if(kind==="freeze") {const saved=await evaluationApi.finalize(report.cutoff,cohort);setRun(saved.run_id);await runs.refetch();setMessage(`Frozen ${saved.run_id}`);} else {const result=await evaluationApi.rerun(report.run_id);setMessage(`Metrics ${result.status}; original sources ${result.source_reconstruction}`);} } catch(e) {setMessage(String(e));} finally {setBusy(false);} }
  return <main className="evaluation-page"><Link to="/portfolio">Back to Paper portfolio</Link><div className="evaluation-toolbar"><label>Evidence cohort <select value={cohort} disabled={Boolean(run)} onChange={e=>{setCohort(e.target.value);setFilter({dimension:"",label:""});setOffset(0);setDetailId("");}}>{["PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA","PROSPECTIVE_SIGNAL_ONLY","SOFTWARE_CONTROLLED","HISTORICAL_REPLAY","FIXTURE"].map(c=><option key={c}>{c}</option>)}</select></label><label>Evaluation run <select value={run} onChange={e=>{setRun(e.target.value);setFilter({dimension:"",label:""});setOffset(0);setDetailId("");}}><option value="">Current bounded projection</option>{runs.data?.runs.map(r=><option key={r.run_id} value={r.run_id}>{r.cutoff} · {r.evidence_class}</option>)}</select></label><button disabled={busy || !report || Boolean(run) || mode!=="PAPER"} onClick={()=>void action("freeze")}>Finalize frozen run</button><button disabled={busy || !run} onClick={()=>void action("rerun")}>Rerun stored metrics</button><button onClick={()=>void summary.refetch()}>Refresh projection</button></div>{message && <p role="status">{message}</p>}{summary.isPending && <p>Loading evaluation…</p>}{summary.error && <p role="alert">Evaluation unavailable: {String(summary.error)}</p>}{report && <EvaluationView key={report.run_id} onFilter={(dimension,label)=>{setFilter({dimension,label});setOffset(0);}} report={report} records={records.data?.records ?? []} onDetail={id=>{setDetailId(id);setShowLifecycle(false);}} />}{records.error && <p role="alert">{String(records.error)}</p>}{records.data && <div className="evaluation-toolbar"><span>Records {offset+1}–{Math.min(offset+25,records.data.total_count)} of {records.data.total_count}</span><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-25))}>Previous records</button><button disabled={records.data.next_offset===null} onClick={()=>setOffset(records.data!.next_offset!)}>Next records</button></div>}{detailId && <section className="evaluation-detail"><h2>Original decision evidence</h2>{detail.error && <p role="alert">{String(detail.error)}</p>}{detail.data && <><p>Original source reconstruction: {detail.data.source_reconstruction}</p><h3>Frozen outcome record</h3><pre>{JSON.stringify(detail.data.record,null,2)}</pre><h3>Stored actual proposal, model, prompt and PIT evidence</h3><dl className="evaluation-metrics"><div><dt>Original action / origin</dt><dd>{detail.data.record.action_state} / {detail.data.record.origin}</dd></div><div><dt>Frozen decision cutoff</dt><dd>{number(detail.data.record.decision_cutoff)}</dd></div><div><dt>Original provider / model / model version</dt><dd>{number(detail.data.record.model?.provider_id)} / {number(detail.data.record.model?.model_id)} / {number(detail.data.record.model?.model_version)}</dd></div><div><dt>Original prompt / version / hash</dt><dd>{number(detail.data.record.model?.prompt_id)} / {number(detail.data.record.model?.prompt_version)} / {number(detail.data.record.model?.prompt_hash)}</dd></div><div><dt>Source time / available time</dt><dd>{number(detail.data.record.evidence_max_time)} / {number(detail.data.record.evidence_available_time)}</dd></div></dl><pre>{JSON.stringify(detail.data.decision,null,2)}</pre>{detail.data.lifecycle_id && <button onClick={()=>setShowLifecycle(true)}>View current trade lifecycle</button>}{showLifecycle && <p>Current lifecycle is a separate read; it does not replace frozen outcomes.</p>}{lifecycle.data && <LifecycleDetail lifecycle={lifecycle.data} />}</>}</section>}</main>;
}
