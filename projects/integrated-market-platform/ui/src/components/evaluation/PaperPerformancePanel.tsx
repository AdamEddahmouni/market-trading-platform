import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { performanceApi, type PerformanceReport } from "../../api/paperPerformance";

const money = (value: number | string | null | undefined) => value == null ? "Unavailable" :
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value) / 100);
const reasonLabels: Record<string, string> = {
  MANUAL_FILLS: "Manual trades",
  CONFIGURATION_CHANGED: "Settings changed during the run",
  PRESTART_FILLS: "Trades before the evaluation start",
  EXPERIMENT_CLOSED: "Experiment closed",
  COVERAGE_GAP: "Missing observation coverage",
  BENCHMARK_UNAVAILABLE: "SPY comparison unavailable",
  OPEN_NOT_OBSERVED: "Opening observation missing",
  CLOSE_NOT_OBSERVED: "Closing observation missing",
  INCOMPLETE_VALUATION: "Incomplete account valuation",
  CLOSING_VALUATION_UNAVAILABLE: "Closing account value unavailable",
  CALENDAR_UNAVAILABLE: "Trading calendar unavailable",
};
const reason = (code: string) => reasonLabels[code] ?? "Evidence unavailable";

function EquityCurve({ report }: { report: PerformanceReport }) {
  const rows = report.sessions;
  const values = rows.flatMap(row => [row.equity_minor, row.spy_equity_minor])
    .filter((value): value is string | number => value !== null).map(Number);
  if (!values.length) return <p>The equity curve will appear after the first session closes.</p>;
  const low = Math.min(report.initial_capital_minor, ...values);
  const high = Math.max(report.initial_capital_minor, ...values);
  const span = high - low || 100;
  const point = (value: number, i: number) =>
    `${40 + 700 * i / Math.max(1, rows.length - 1)},${215 - (value - low) / span * 170}`;
  return <figure className="performance-curve">
    <svg viewBox="0 0 780 260" role="img" aria-label="Account and SPY equity; gaps are not connected">
      <path d="M40 25V230H750" fill="none" stroke="currentColor" opacity=".4" />
      <text x="45" y="20" fill="currentColor" fontSize="12">{money(high)}</text>
      <text x="45" y="250" fill="currentColor" fontSize="12">{money(low)}</text>
      {(["equity_minor", "spy_equity_minor"] as const).map(field => {
        const color = field === "equity_minor" ? "#60a5fa" : "#fb923c";
        const segments: string[][] = [];
        let current: string[] = [];
        for (const [i, row] of rows.entries()) {
          if (row[field] === null || !row.covered) {
            if (current.length) segments.push(current);
            current = [];
          } else current.push(point(Number(row[field]), i));
        }
        if (current.length) segments.push(current);
        return <g key={field}>{segments.map((points, i) =>
          <polyline key={i} points={points.join(" ")} fill="none" stroke={color} strokeWidth="2" />)}
          {rows.map((row, i) => row[field] !== null && row.covered ?
            <circle key={row.session_date} cx={point(Number(row[field]), i).split(",")[0]}
              cy={point(Number(row[field]), i).split(",")[1]} r="3" fill={color}>
              <title>{row.session_date}: {field === "equity_minor" ? "Paper account" : "SPY"} {money(row[field])}</title>
            </circle> : null)}
        </g>;
      })}
    </svg>
    <figcaption><span className="performance-account-key">● Paper account</span>{" · "}
      <span className="performance-spy-key">● SPY with reinvested dividends</span>. Both start at {money(report.initial_capital_minor)}.
      Missing coverage is left as a gap. Exact daily values are below.</figcaption>
  </figure>;
}

export function PaperPerformanceView({ report, onDownload, downloading = false }: {
  report: PerformanceReport; onDownload: (format: "html" | "csv") => void; downloading?: boolean;
}) {
  const mixed = report.sessions.some(row => row.mixed || row.reasons.includes("MANUAL_FILLS")) ||
    Object.values(report.milestones).some(row => row.reasons.includes("MANUAL_FILLS"));
  const last = report.sessions[report.sessions.length - 1];
  return <section aria-labelledby="paper-performance-heading">
    <h2 id="paper-performance-heading">Day 10 and day 20 results</h2>
    <p>{report.fixed_sessions} scheduled sessions · {report.covered_sessions} covered sessions.
      Evaluation starts {report.first_session} with {money(report.initial_capital_minor)} in simulated capital.</p>
    <p>Day 10: account value above its start. Day 20: at least 30 completed trades, positive return after costs,
      and return above SPY including dividends.</p>
    <p>One completed trade means a position opened and fully closed. Partial fills and reductions do not add trades.</p>
    {mixed && <p className="evaluation-warning">Manual trades make this a mixed run. Its account results remain visible,
      but it cannot receive an AI pass.</p>}
    <div className="evaluation-scroll"><table aria-label="Paper evaluation milestones">
      <thead><tr><th>Milestone</th><th>Session</th><th>Result</th><th>Account value</th><th>Completed trades</th><th>Evidence</th></tr></thead>
      <tbody>{Object.values(report.milestones).map(row =>
        <tr key={row.clock + row.day}><th>{row.clock === "fixed" ? "Fixed" : "Covered"} day {row.day}</th>
          <td>{row.session_date ?? "Waiting for covered sessions"}</td><td><strong>{row.status}</strong></td>
          <td>{money(row.equity_minor)}</td><td>{row.completed_trades}</td>
          <td>{row.reasons.length ? row.reasons.map(reason).join("; ") : row.status === "Not due" ? "Milestone not reached" : "Recorded"}
            {Object.entries(row.conditions).map(([key, value]) => <div key={key}>
              {{ above_start: "Account above start", completed_30_trades: "30 completed trades", above_spy: "Above SPY" }[key] ?? key}:
              {" "}{value === null ? "Unavailable" : value ? "Yes" : "No"}</div>)}
          </td></tr>)}</tbody>
    </table></div>
    <p>Fixed milestones keep their original dates. Covered milestones are supplemental and keep every intervening gain,
      loss, and cost; they do not erase gaps or replace the original results.</p>
    <EquityCurve report={report} />
    {last && <dl className="evaluation-metrics">
      <div><dt>Commissions</dt><dd>{money(last.costs.commission_minor)}</dd></div>
      <div><dt>Transaction fees</dt><dd>{money(last.costs.fees_minor)}</dd></div>
      <div><dt>Posted borrow fees</dt><dd>{money(last.costs.posted_borrow_minor)}</dd></div>
      <div><dt>Unposted borrow</dt><dd>{money(last.costs.unposted_borrow_minor)}</dd></div>
    </dl>}
    <p>Account values include costs once, including the separately shown unposted borrow.
      SPY assumes fractional shares, dividend reinvestment, no transaction fees, and no tax.</p>
    <div className="evaluation-toolbar">
      <button disabled={downloading} onClick={() => onDownload("html")}>Download HTML</button>
      <button disabled={downloading} onClick={() => onDownload("csv")}>Download CSV</button>
    </div>
    <details><summary>Daily values and coverage</summary><div className="evaluation-scroll">
      <table aria-label="Daily account and SPY values"><thead><tr><th>Session</th><th>Paper account</th><th>SPY</th>
        <th>Completed trades</th><th>Coverage</th></tr></thead><tbody>{report.sessions.map(row =>
        <tr key={row.session_date}><th>{row.session_date}</th><td>{money(row.equity_minor)}</td>
          <td>{money(row.spy_equity_minor)}</td><td>{row.completed_trades}</td>
          <td>{row.covered ? "Covered" : [...new Set([...row.reasons, ...row.coverage.reasons])].map(reason).join("; ") || "Incomplete"}
            {row.coverage.gaps.map(gap => <div key={gap.start_ns}>Observation gap: {gap.seconds} seconds</div>)}</td></tr>)}
      </tbody></table></div></details>
  </section>;
}

export default function PaperPerformancePanel({ account, experimentId, prospective, mode }: {
  account?: string; experimentId?: string; prospective: boolean; mode: "DEMO" | "PAPER" | "LIVE";
}) {
  const client = useQueryClient();
  const [selected, setSelected] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const runs = useQuery({ queryKey: ["paper-performance-runs", account], queryFn: performanceApi.list,
    enabled: Boolean(account) && mode !== "DEMO" });
  const selectedId = runs.data?.runs.find(row => row.run_id === selected)?.run_id ?? runs.data?.runs[0]?.run_id;
  const report = useQuery({ queryKey: ["paper-performance-report", account, selectedId],
    queryFn: () => performanceApi.read(selectedId!), enabled: Boolean(selectedId) && mode !== "DEMO", refetchInterval: 60000 });
  const enroll = useMutation({ mutationFn: () => performanceApi.enroll(experimentId!),
    onSuccess: async run => { setSelected(run.run_id); await client.invalidateQueries({ queryKey: ["paper-performance-runs", account] }); } });
  const refresh = useMutation({ mutationFn: () => performanceApi.refreshBenchmark(selectedId!) });
  if (mode === "DEMO") return null;
  async function download(format: "html" | "csv") {
    if (!report.data) return;
    setDownloading(true); setDownloadError("");
    try {
      const value = report.data.report;
      const blob = await performanceApi.download(value.run_id, value.report_id, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = "paper-performance." + format;
      document.body.append(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setDownloadError("The saved report could not be downloaded. Please try again."); }
    finally { setDownloading(false); }
  }
  return <section className="performance-panel" aria-label="Paper performance evaluation">
    {runs.isPending && account && <p>Loading Paper evaluations…</p>}
    {runs.error && <p role="alert">Paper evaluations could not be loaded.</p>}
    {runs.data && runs.data.runs.length === 0 && <><h2>Evaluate a continuous Paper run</h2>
      <p>No evaluation has been enrolled. Use a new, untraded Paper experiment with automation configured.
        Enrollment schedules measurement from the next full trading session; it does not start trading.</p>
      {mode === "PAPER" && <button disabled={!experimentId || !prospective || enroll.isPending}
        onClick={() => enroll.mutate()}>Start evaluation for this Paper experiment</button>}</>}
    {enroll.error && <p role="alert">Evaluation could not be enrolled. Check that this is a new, untraded Paper experiment
      with automation and an AI engine configured.</p>}
    {runs.data && runs.data.runs.length > 0 && <label>Paper evaluation run{" "}
      <select value={selectedId} onChange={event => setSelected(event.target.value)}>
        {runs.data.runs.map(run => <option key={run.run_id} value={run.run_id}>Starting {run.first_session} · {run.run_id.slice(-8)}</option>)}
      </select></label>}
    {report.error && <p role="alert">The saved Paper evaluation could not be loaded.</p>}
    {report.data && <>
      {report.data.durability !== "SQLITE_LOCAL_STATE" && <p className="evaluation-warning">This evaluation is stored only
        in memory and will not survive a restart.</p>}
      {mode === "PAPER" && <button disabled={refresh.isPending} onClick={() => refresh.mutate()}>Refresh saved SPY evidence</button>}
      {refresh.isSuccess && <p role="status">SPY evidence refresh queued. New results will be saved as a separate report revision.</p>}
      {refresh.error && <p role="alert">The SPY evidence refresh could not be queued.</p>}
      <PaperPerformanceView report={report.data.report} onDownload={format => void download(format)} downloading={downloading} />
      <p className="muted">Last saved observation: {report.data.last_observation_ns ?
        new Date(report.data.last_observation_ns / 1000000).toLocaleString() : "Waiting for the first session"}.
        Viewing this page does not collect prices or run the AI.</p>
    </>}
    {downloadError && <p role="alert">{downloadError}</p>}
  </section>;
}
