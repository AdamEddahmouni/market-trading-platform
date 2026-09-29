import type { IDockviewPanelProps } from "dockview-react";
import { Providers, stamp, stateText } from "../participants/participantFormat";
import { Beneficial, FuturesPositioning, Holdings13F, Insiders, LargeActivity, Provenance, RecentFilings } from "../participants/sections";
import { useParticipantInstrument } from "../participants/useParticipantInstrument";
import { PanelFrame, PanelMessage, selectionGate, usePanelVisible, useSelection } from "./shared";
import "../news/news.css";
import "../participants/participants.css";

/** S12 Institutional & Whale: disclosed holders, insiders, 13F, CFTC positioning, and unknown-participant activity — each separate. */
export default function InstitutionalPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe, supportedPanels, actions } = useSelection();
  const visible = usePanelVisible(api);
  const { query, data } = useParticipantInstrument({ universe, instrumentId: row?.instrument.instrument_id ?? null, settledId,
    lens: "institutional", compact: false, enabled: visible });
  const gate = selectionGate("institutional", row, settledId);
  const sections = data?.sections ?? {};
  const openOrderFlow = supportedPanels.has("order_flow") && actions.open ? () => actions.open?.("order_flow") : undefined;
  return <PanelFrame id="institutional" state={data?.state ?? null} stateLabel={data ? stateText(data.state) : undefined} clock={data ? `updated ${stamp(data.generated_at)}` : null}
    detail={data ? `${data.instrument.label} · ${data.providers.filter((item) => !["NOT_CONFIGURED", "LIVE_DISABLED"].includes(item.state)).length}/${data.providers.length} sources active` : null}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">Institutional &amp; Whale request failed. <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row?.symbol} ownership evidence…</PanelMessage>
      : <div className="news-panel participant-panel">
        {data.state === "NOT_CONFIGURED" && <PanelMessage tone="warn">Official ownership sources are not configured. This is a source state, not an absence of holders.</PanelMessage>}
        <Providers providers={data.providers} label="Institutional & Whale sources" />
        {sections.futures_positioning && <FuturesPositioning section={sections.futures_positioning} compact={false} />}
        {sections.beneficial_ownership && <Beneficial section={sections.beneficial_ownership} compact={false} />}
        {sections.insiders && <Insiders section={sections.insiders} compact={false} />}
        {sections.holdings_13f && <Holdings13F section={sections.holdings_13f} compact={false} />}
        {sections.recent_filings && <RecentFilings section={sections.recent_filings} />}
        {sections.large_activity && <LargeActivity section={sections.large_activity} onOpenOrderFlow={openOrderFlow} />}
        <Provenance data={data} />
        <p className="participant-note">Overall: {stateText(data.state)}. No smart-money, whale, or ownership score is computed.</p>
      </div>)}
  </PanelFrame>;
}
