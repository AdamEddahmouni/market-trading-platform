import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { evidenceApi, type EvidenceJournal, type EvidenceKnowledge, type EvidencePlan, type EvidenceReplay,
  type EvidenceStatus } from "../../api/evidenceReview";

const unavailable = "Unavailable";
const text = (value: unknown) => value == null || value === "" ? unavailable : String(value);
const TABS = [["news", "Stored news"], ["plan", "Morning catch-up plan"], ["journal", "Decision journal"], ["replay", "Day replay"]] as const;
type Tab = typeof TABS[number][0];

export function StatusView({ status }: { status: EvidenceStatus }) {
  const s = status.session;
  return <>
    <dl className="evaluation-metrics">
      <div><dt>AI analysis window ({status.schedule_timezone})</dt><dd>{s.window}{s.allowed ? "" : ` · not eligible${s.reason ? ` (${s.reason})` : ""}`}</dd></div>
      <div><dt>New York time / trading-day basis</dt><dd><time>{text(s.local_time)}</time> / {s.trading_day_basis}</dd></div>
      <div><dt>Stored news</dt><dd>{status.knowledge.state}{status.knowledge.records != null ? ` · ${status.knowledge.records} records` : ""}{status.knowledge.reason ? ` · ${status.knowledge.reason}` : ""}</dd></div>
      <div><dt>Latest stored at</dt><dd>{text(status.knowledge.latest_ingested_time)}</dd></div>
      <div><dt>Configured AI engine / model</dt><dd>{status.model.engine} / {text(status.model.model)}</dd></div>
      <div><dt>Model access</dt><dd>{status.model.configured ? "Configured" : text(status.model.configuration_reason)} · availability not probed</dd></div>
    </dl>
    <p>Collection has its own switches and is not paused by the AI schedule: {Object.entries(status.collection).map(([name, gate]) => `${name} ${text(gate.state)}`).join(" · ")}.</p>
    <div className="evaluation-scroll"><table aria-label="AI analysis schedule"><thead><tr><th>Window</th><th>From</th><th>To</th><th>AI analysis</th></tr></thead>
      <tbody>{status.schedule.map(row => <tr key={row.window}><td>{row.window}</td><td>{row.start}</td><td>{row.end}</td><td>{row.inference_allowed ? "Eligible" : "Paused"}</td></tr>)}</tbody></table></div>
  </>;
}

export function KnowledgeView({ knowledge }: { knowledge: EvidenceKnowledge }) {
  if (knowledge.store.state === "UNAVAILABLE") return <p role="status">Stored news is unavailable: {text(knowledge.store.reason)}.</p>;
  return <>
    <p>What was stored and known as of <time>{knowledge.as_of}</time>. An article appears from the time IMP received it, never from its publication time. {knowledge.count} shown.</p>
    {!knowledge.records.length && <p role="status">No stored article was known at this time.</p>}
    {knowledge.records.length > 0 && <div className="evaluation-scroll"><table aria-label="Stored news"><thead><tr><th>Known from</th><th>Published</th><th>Headline</th><th>Source</th><th>Instruments</th><th>Evidence</th></tr></thead>
      <tbody>{knowledge.records.map(row => <tr key={row.record_id}>
        <td><time>{row.available_time}</time></td><td>{text(row.published_time)}</td>
        <td>{row.url ? <a href={row.url} target="_blank" rel="noreferrer">{text(row.headline)}</a> : text(row.headline)}{row.supersedes_record_id && <div>Corrected version of an earlier stored record</div>}</td>
        <td>{text(row.source_id)} / {text(row.provider_id)}</td><td>{row.instruments.join(", ") || unavailable}</td>
        <td>{text(row.evidence_class)}<div>{text(row.source_reference)}</div></td></tr>)}</tbody></table></div>}
  </>;
}

export function PlanView({ plan }: { plan: EvidencePlan }) {
  return <>
    <p className="evaluation-warning">Plan only. No model is called and no budget is reserved. {plan.availability_basis === "OPERATOR_ASSUMPTION_FOR_PREVIEW" ? "Model access is assumed for this preview and has not been verified." : "Model access has not been verified, so nothing can be planned until it is."}</p>
    <dl className="evaluation-metrics">
      <div><dt>Planned for / window</dt><dd><time>{plan.planned_for}</time> / {plan.session.window}{plan.session.reason ? ` (${plan.session.reason})` : ""}</dd></div>
      <div><dt>Stored articles considered</dt><dd>{plan.candidates} (evidence as of {plan.evidence_as_of})</dd></div>
      <div><dt>Planned / deferred requests</dt><dd>{plan.planned_requests} / {plan.deferred.length}</dd></div>
      <div><dt>Planned worst-case tokens</dt><dd>{plan.planned_tokens}</dd></div>
      <div><dt>Bounds: requests / tokens / backlog</dt><dd>{plan.bounds.max_requests} / {plan.bounds.max_tokens} / {plan.bounds.max_backlog}</dd></div>
      <div><dt>Daily budget used (requests / tokens)</dt><dd>{text(plan.budget.requests)} of {text(plan.budget.max_requests)} / {text(plan.budget.tokens)} of {text(plan.budget.max_tokens)} · {text(plan.budget.source)}</dd></div>
      <div><dt>Model / request check</dt><dd>{plan.model.engine} / {text(plan.model.model)} · {plan.model_route.state}</dd></div>
      <div><dt>Token estimate basis</dt><dd>{plan.estimate_basis}</dd></div>
    </dl>
    {Object.keys(plan.deferred_reasons).length > 0 && <p>Deferred because: {Object.entries(plan.deferred_reasons).map(([reason, n]) => `${reason} ×${n}`).join(", ")}. Deferred articles stay stored for the next eligible window.</p>}
    {([["Planned requests", plan.planned], ["Deferred", plan.deferred]] as const).map(([label, rows]) => rows.length > 0 && <div key={label} className="evaluation-scroll"><table aria-label={label}><thead><tr><th>{label}</th><th>Source</th><th>Known from</th><th>Worst-case tokens</th><th>Reason</th></tr></thead>
      <tbody>{rows.map((row, index) => <tr key={`${row.record_id}-${index}`}><td>{text(row.headline)}</td><td>{text(row.source_id)}</td><td>{text(row.available_time)}</td><td>{row.worst_case_tokens}</td><td>{row.reason ?? "Planned"}</td></tr>)}</tbody></table></div>)}
  </>;
}

export function JournalView({ journal, onInspect }: { journal: EvidenceJournal; onInspect: (id: string) => void }) {
  return <>
    <p>Decisions recorded on {journal.day} ({journal.day_basis}), read as of <time>{journal.observation_as_of}</time>. Each decision keeps the evidence frozen when it was made; what happened later is read separately and never rewrites it.</p>
    {!journal.items.length && <p role="status">No decision was recorded for this day at this cutoff.</p>}
    {journal.items.length > 0 && <div className="evaluation-scroll"><table aria-label="Decision journal"><thead><tr><th>Time / instrument</th><th>IMP proposal</th><th>Operator action</th><th>Paper execution</th><th>Later market observations</th><th>Evidence</th></tr></thead>
      <tbody>{journal.items.map(row => <tr key={row.decision_id}>
        <td><time>{row.decision_time}</time><div>{row.instrument_id}</div></td>
        <td>{text(row.action.action_state)}<div>{text(row.action.execution_readiness)}</div></td>
        <td>{row.action.operator_action ?? "None recorded"}</td>
        <td>{row.later_evidence.status === "AVAILABLE" ? row.later_evidence.execution_outcome?.state ?? "No Paper trade at this cutoff" : `Unavailable: ${text(row.later_evidence.reason)}`}</td>
        <td>{row.later_evidence.status === "AVAILABLE" ? `${row.later_evidence.signal_outcomes?.length ?? 0} recorded` : unavailable}</td>
        <td>{row.evidence_count} items<div><button onClick={() => onInspect(row.decision_id)}>Inspect {row.instrument_id}</button></div></td></tr>)}</tbody></table></div>}
    {journal.unjournaled.length > 0 && <><h3>Decisions not shown</h3><p>These stored decisions did not pass the journal's consistency checks. They are listed, not repaired.</p>
      <ul>{journal.unjournaled.map((row, index) => <li key={`${row.decision_id}-${index}`}>{text(row.instrument_id)} · {text(row.decision_time)} · {row.reason}</li>)}</ul></>}
    <p>Realised profit and loss is not computed here; it stays with the Paper ledger and the outcome evaluation above.</p>
  </>;
}

export function ReplayView({ replay }: { replay: EvidenceReplay }) {
  return <>
    <p className="evaluation-warning">{replay.evidence_class}: curated test data for {replay.replay_date}, rebuilt as of <time>{replay.as_of}</time>. Every policy receives the same snapshot. This shows that the comparison is fair and repeatable. It is not a performance ranking and says nothing about which policy is better.</p>
    <dl className="evaluation-metrics">
      <div><dt>Samples in view / decided</dt><dd>{replay.coverage.eligible_samples} / {replay.coverage.decision_samples}</dd></div>
      <div><dt>Withheld as later than the clock (news / AI output)</dt><dd>{replay.coverage.withheld_news} / {replay.coverage.withheld_inference}</dd></div>
      <div><dt>Repeatable</dt><dd>{replay.deterministic ? "Yes, two runs identical" : "No"}</dd></div>
      <div><dt>Any difference between policies</dt><dd>{replay.comparison.any_policy_difference ? "Yes" : "No, all verdicts equal"}</dd></div>
    </dl>
    {replay.decisions.length > 0 && <div className="evaluation-scroll"><table aria-label="Replay policy comparison"><thead><tr><th>Sample / time</th><th>Instrument</th><th>News used</th>{replay.decisions[0].policies.map(p => <th key={p.policy_id}>{p.policy_id}<div>{p.classification}</div></th>)}</tr></thead>
      <tbody>{replay.decisions.map(row => <tr key={row.sample_id}><td>{row.sample_id}<div><time>{row.as_of}</time></div></td><td>{row.instrument_id}</td><td>{row.news_event_ids.length}</td>{row.policies.map(p => <td key={p.policy_id}>{p.decision}</td>)}</tr>)}</tbody></table></div>}
    {replay.gaps.length > 0 && <p>Not decided: {replay.gaps.map(gap => `${gap.sample_id} (${gap.reason})`).join(", ")}.</p>}
    <details><summary>Limits and fingerprint</summary><ul>{replay.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>Snapshot {replay.snapshot_hash} · market data {replay.market_data_ref}</p></details>
  </>;
}

/** Draft inputs applied on request, so a half-typed time is never sent. */
function Filters<T extends Record<string, string | boolean>>({ value, onApply, fields }: { value: T; onApply: (value: T) => void; fields: [keyof T & string, string, string?][] }) {
  const [draft, setDraft] = useState(value);
  return <form className="evaluation-toolbar" onSubmit={event => { event.preventDefault(); onApply(draft); }}>
    {fields.map(([key, label, placeholder]) => typeof draft[key] === "boolean"
      ? <label key={key}><input type="checkbox" checked={draft[key] as boolean} onChange={e => setDraft({ ...draft, [key]: e.target.checked })} /> {label}</label>
      : <label key={key}>{label} <input value={draft[key] as string} placeholder={placeholder} onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></label>)}
    <button type="submit">Show</button>
  </form>;
}

export default function EvidenceReviewPanel() {  const [tab, setTab] = useState<Tab>("news");
  const [news, setNews] = useState({ as_of: "", symbol: "" });
  const [plan, setPlan] = useState({ at: "", max_requests: "", request_allowance: "4096", assume_available: false });
  const [journal, setJournal] = useState({ day: "", as_of: "" });
  const [replay, setReplay] = useState({ date: "", as_of: "" });
  const [inspect, setInspect] = useState("");
  const status = useQuery({ queryKey: ["evidence-review", "status"], queryFn: evidenceApi.status });
  const knowledge = useQuery({ queryKey: ["evidence-review", "knowledge", news], queryFn: () => evidenceApi.knowledge(news), enabled: tab === "news" });
  const planned = useQuery({ queryKey: ["evidence-review", "plan", plan], queryFn: () => evidenceApi.plan(plan), enabled: tab === "plan" });
  const entries = useQuery({ queryKey: ["evidence-review", "journal", journal], queryFn: () => evidenceApi.journal(journal), enabled: tab === "journal" });
  const entry = useQuery({ queryKey: ["evidence-review", "journal-entry", journal, inspect], queryFn: () => evidenceApi.journalEntry({ ...journal, decision_id: inspect }), enabled: tab === "journal" && Boolean(inspect) });
  const replayed = useQuery({ queryKey: ["evidence-review", "replay", replay], queryFn: () => evidenceApi.replay(replay), enabled: tab === "replay" });
  const active = { news: knowledge, plan: planned, journal: entries, replay: replayed }[tab];
  const clocks = replayed.data?.available.find(item => item.replay_date === replayed.data?.replay_date)?.clocks ?? [];
  return <section className="evaluation-detail" aria-labelledby="evidence-review-title">
    <h2 id="evidence-review-title">Evidence review</h2>
    <p>Stored information, the AI analysis schedule, recorded decisions and day replay. Read-only: nothing here contacts a data provider, runs an AI model, spends budget or places an order.</p>
    {status.error && <p role="alert">Evidence status unavailable: {String(status.error)}</p>}
    {status.data && <StatusView status={status.data} />}
    <div className="evaluation-toolbar" role="tablist" aria-label="Evidence views">{TABS.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
    {tab === "news" && <Filters value={news} onApply={setNews} fields={[["as_of", "Known as of (UTC, e.g. 2026-10-14T07:30:00Z)", "now"], ["symbol", "Symbol", "any"]]} />}
    {tab === "plan" && <Filters value={plan} onApply={setPlan} fields={[["at", "Preview clock (UTC, now or later)", "now"], ["max_requests", "Max requests", "budget limit"], ["request_allowance", "Allowance per request (tokens for prompt and answer)", "none"], ["assume_available", "Preview as if model access were confirmed"]]} />}
    {tab === "journal" && <Filters value={journal} onApply={value => { setJournal(value); setInspect(""); }} fields={[["day", "Day (New York, YYYY-MM-DD)", "today"], ["as_of", "Read as of (UTC)", "now"]]} />}
    {tab === "replay" && replayed.data && <div className="evaluation-toolbar"><label>Replay day <select value={replayed.data.replay_date} onChange={e => setReplay({ date: e.target.value, as_of: "" })}>{replayed.data.available.map(item => <option key={item.replay_date}>{item.replay_date}</option>)}</select></label><label>Clock <select value={replayed.data.as_of} onChange={e => setReplay({ date: replayed.data!.replay_date, as_of: e.target.value })}>{clocks.map(clock => <option key={clock}>{clock}</option>)}</select></label></div>}
    {active.isPending && <p>Loading…</p>}
    {active.error && <p role="alert">Unavailable: {String(active.error)}</p>}
    {tab === "news" && knowledge.data && <KnowledgeView knowledge={knowledge.data} />}
    {tab === "plan" && planned.data && <PlanView plan={planned.data} />}
    {tab === "journal" && entries.data && <JournalView journal={entries.data} onInspect={setInspect} />}
    {tab === "journal" && inspect && <section><h3>Frozen decision and evidence</h3>{entry.error && <p role="alert">{String(entry.error)}</p>}{entry.data && <><h4>What happened afterwards (read as of {entry.data.observation_as_of})</h4><pre>{JSON.stringify(entry.data.later_evidence, null, 2)}</pre><h4>Decision as recorded</h4><pre>{JSON.stringify(entry.data.entry, null, 2)}</pre></>}</section>}
    {tab === "replay" && replayed.data && <ReplayView replay={replayed.data} />}
  </section>;
}
