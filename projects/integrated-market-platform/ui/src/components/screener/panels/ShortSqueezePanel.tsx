import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchScreenerSqueeze } from "../../../api/screenerSqueeze";
import { SqueezeLifecycle } from "../../squeeze/SqueezeLifecycle";
import { Coverage, MetricList, StateSummary, WhyListed } from "../squeeze/SqueezeEvidence";
import { Age, ErrorDetail, PanelFrame, PanelMessage, selectionGate, usePanelVisible, useSelection } from "./shared";

export default function ShortSqueezePanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe, filters, demand } = useSelection();
  const visible = usePanelVisible(api);
  const filterKey = JSON.stringify(filters);
  const tradeDemandHeld = Boolean(demand?.instrument_id === settledId && demand.panels.includes("short_squeeze"));
  const query = useQuery({
    queryKey: ["screener-squeeze", universe, settledId, "detail", filterKey, tradeDemandHeld],
    queryFn: ({ signal }) => fetchScreenerSqueeze(settledId!, { universe, view: "detail", filters, signal }),
    enabled: visible && universe === "US_EQUITIES" && Boolean(settledId) && settledId === row?.instrument.instrument_id,
    staleTime: 30_000, refetchInterval: visible ? 30_000 : false, retry: 1,
  });
  const data = query.data?.instrument_id === row?.instrument.instrument_id && query.data?.universe === universe ? query.data : undefined;
  const gate = selectionGate("short_squeeze", row, settledId);
  return <PanelFrame decisionInputs={data?.decision_inputs} id="short_squeeze" detail={data ? `${data.market_session} · source clocks below` : null}
    clock={data?.generated_at ? <>Assessed {new Date(data.generated_at).toLocaleTimeString()} (<Age iso={data.generated_at} staleMs={75_000} /> ago)</> : null}>
    {universe !== "US_EQUITIES" ? <PanelMessage>Short Squeeze evidence is available for US equities only.</PanelMessage> : gate ??
      (query.isError && !data ? <PanelMessage tone="error" role="alert">Squeeze evidence unavailable.<ErrorDetail error={query.error} /> <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
        : !data ? <PanelMessage>Loading {row!.symbol} squeeze evidence…</PanelMessage> :
          <div className="screener-panel-scroll screener-squeeze-detail">
            <StateSummary data={data} />
            <SqueezeLifecycle state={data.assessment.state} stages={data.assessment.lifecycle} />
            <Coverage data={data} />
            <div className="screener-squeeze-grid">
              <MetricList title="Structural pressure" items={data.sections.structural_pressure} />
              <MetricList title="Ignition" items={data.sections.ignition} />
              <MetricList title="Live confirmation" items={data.sections.live_confirmation} />
            </div>
            <section className="screener-squeeze-section" aria-label="Evidence details"><h3>Evidence</h3>
              <div className="screener-squeeze-evidence-grid">
                <div><h4>Supporting</h4><ul>{data.evidence.supporting.map((item) => <li key={item.code}>{item.label} · {item.detail}</li>)}</ul></div>
                <div><h4>Conflicting</h4><ul>{data.evidence.conflicting.map((item) => <li key={item.code}>{item.label} · {item.detail}</li>)}</ul></div>
                <div><h4>Unavailable</h4><ul>{data.evidence.missing.map((item) => <li key={item.code}>{item.label}{item.reason ? ` · ${item.reason.replace(/_/g, " ").toLowerCase()}` : ""}</li>)}</ul></div>
              </div>
            </section>
            <WhyListed data={data} />
            <p className="screener-panel-note">{data.disclaimer}</p>
          </div>)}
  </PanelFrame>;
}
