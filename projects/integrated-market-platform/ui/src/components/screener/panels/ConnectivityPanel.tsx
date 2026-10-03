import { DecisionFreshness, currentFreshness, useDecisionNow } from "../DecisionFreshness";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchConnectivity, type ConnectivityPayload } from "../../../api/screenerConnectivity";
import { ErrorDetail, PanelFrame, PanelMessage, selectionGate, usePanelVisible, useSelection } from "./shared";
import type { PanelId } from "../../../api/screener";
import "./connectivity.css";

export function ConnectivityView({ data, open, supportedPanels }: { data: ConnectivityPayload; open?: (id: PanelId) => void; supportedPanels?: ReadonlySet<PanelId> }) {
  const [inspected, setInspected] = useState<string | null>(null);
  const now = useDecisionNow(data.decision_inputs);
  const selected = data.selected_instrument.node_id;
  const others = data.nodes.filter(n => n.node_id !== selected);
  const focused = data.nodes.find(n => n.node_id === inspected);
  const links = data.edges.filter(e => e.from_node === inspected || e.to_node === inspected);
  const domains = Object.entries(data.completeness.domains);
  const drilldown: Record<string, PanelId> = { OPTIONS: "options", FUTURES: "futures", BONDS_RATES: "rates_curve" };
  const positions = new Map(data.nodes.map((n, i) => [n.node_id, n.node_id === selected ? [150, 150] :
    [150 + 110 * Math.cos((i - 1) * 2 * Math.PI / Math.max(others.length, 1)), 150 + 110 * Math.sin((i - 1) * 2 * Math.PI / Math.max(others.length, 1))]]));
  return <div className="connectivity">
    <p><strong>{data.selected_instrument.label}</strong> · {data.selected_instrument.asset_class} · {domains.filter(([, d]) => d.state === "AVAILABLE").length}/{domains.length} contexts available</p>
    <ul aria-label="Asset coverage">{domains.map(([domain, status]) => <li key={domain}>{domain}: <strong>{status.state}</strong>{status.reason && ` — ${status.reason}`}
      {!!status.missing_references?.length && <small>Missing references: {status.missing_references.join(", ")}</small>}
      {status.catalog_unavailable && <small>Catalog read unavailable; coverage may be partial.</small>}</li>)}</ul>
    <section aria-label="Cross-asset connectivity graph" className="connectivity-graph" style={{ height: Math.max(420, others.length * 85) }}>
      <svg viewBox="0 0 300 300" preserveAspectRatio="none" aria-hidden="true">{data.edges.map(e => {
        const from = positions.get(e.from_node)!; const to = positions.get(e.to_node)!;
        return <line key={e.edge_id} x1={from[0]} y1={from[1]} x2={to[0]} y2={to[1]} className={e.relationship_class.toLowerCase()} />;
      })}</svg>
      {data.nodes.map(n => {
        const position = positions.get(n.node_id)!;
        const relation = data.edges.find(e => e.from_node === n.node_id || e.to_node === n.node_id);
        return <button key={n.node_id} type="button" style={{ left: `${position[0] / 3}%`, top: `${position[1] / 3}%` }}
          aria-label={`Inspect ${n.label} · ${n.state}`} aria-pressed={inspected === n.node_id} onClick={() => setInspected(n.node_id)}>
          <strong>{n.label}</strong><small>{n.instrument_kind}</small><small>{n.decision_evidence ? `${n.decision_evidence.delivery_mode} · ${currentFreshness(n.decision_evidence, now)}` : n.state}</small>
          {relation && <small>{relation.evidence_state}</small>}
        </button>;
      })}
    </section>
    <p className="screener-panel-note">Solid: structural · Dashed: reference · Dotted: contextual mapping. All relationships are listed below.</p>
    <div className="connectivity-table"><table aria-label="Cross-asset relationships">
      <thead><tr>{["Connection", "Class / relationship", "Basis", "Evidence", "Source / as-of"].map(h => <th scope="col" key={h}>{h}</th>)}</tr></thead>
      <tbody>{data.edges.map(e => {
        const origin = data.nodes.find(n => n.node_id === e.from_node)!;
        const target = data.nodes.find(n => n.node_id === e.to_node)!;
        return <tr key={e.edge_id}><td><button type="button" onClick={() => setInspected(origin.node_id)}>{origin.label} → {target.label}</button><small>{origin.asset_class} / {target.asset_class}</small></td>
          <td>{e.relationship_class}<small>{e.relationship_type}</small></td><td>{e.basis}<small>{e.definition_version}</small></td>
          <td><strong>{e.evidence_state}</strong><small>{e.explanation}</small></td>
          <td>{[origin, target].map(n => <div key={n.node_id}>{n.label}: {n.source ?? "Source unavailable"}<small>As-of {n.as_of ?? "unavailable"} · Retrieved {n.received_at ?? "unavailable"}</small></div>)}</td></tr>;
      })}</tbody>
    </table></div>
    {!data.edges.length && <p>No supported relationships are available for this selection.</p>}
    {focused && <section aria-label="Connectivity detail inspector"><h3>Why connected</h3>
      <p><strong>{focused.label}</strong> · {focused.asset_class} · {focused.instrument_kind}</p>
      <p>Canonical identity: {focused.canonical_instrument_id ?? "Aggregate reference context; no instrument identity"}</p>
      <DecisionFreshness inputs={focused.decision_evidence ? [focused.decision_evidence] : undefined} />
      <p>{focused.state} · {focused.source ?? "Source unavailable"} · As-of {focused.as_of ?? "unavailable"} · Retrieved {focused.received_at ?? "unavailable"}</p>
      {links.map(e => <p key={e.edge_id}>{e.relationship_type} · {e.relationship_class} · {e.evidence_state} · {e.basis} · {e.explanation}</p>)}
      <details><summary>Facts and provenance</summary><pre>{JSON.stringify({ facts: focused.facts, relationships: links }, null, 2)}</pre></details>
      {open && drilldown[focused.domain] && (!supportedPanels || supportedPanels.has(drilldown[focused.domain])) && <button type="button" onClick={() => open(drilldown[focused.domain])}>Open specialist details</button>}
    </section>}
    <p className="screener-panel-note">{data.causal_note}</p>
  </div>;
}

export default function ConnectivityPanel({ api }: IDockviewPanelProps) {
  const { row, universe, settledId, actions, supportedPanels } = useSelection();
  const visible = usePanelVisible(api);
  const current = Boolean(row && row.instrument.instrument_id === settledId);
  const query = useQuery({ queryKey: ["screener-connectivity", universe, settledId],
    queryFn: ({ signal }) => fetchConnectivity(settledId!, universe, signal),
    enabled: current && visible, staleTime: 30_000, refetchInterval: visible ? 60_000 : false, retry: 1 });
  const data = current && query.data?.instrument_id === row?.instrument.instrument_id && query.data?.universe === universe ? query.data : undefined;
  return <PanelFrame id="connectivity" detail="Source-grounded research context">
    {selectionGate("connectivity", row, settledId) ?? (query.isError && !data ?
      <PanelMessage role="alert">Connectivity request failed.<ErrorDetail error={query.error} /><button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage> :
      !data ? <PanelMessage>Loading cross-asset context…</PanelMessage> :
      <ConnectivityView key={`${universe}|${data.instrument_id}`} data={data} supportedPanels={supportedPanels} open={actions.open} />)}
  </PanelFrame>;
}
