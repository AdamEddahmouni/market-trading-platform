import type { IDockviewPanelProps } from "dockview-react";
import { Providers, stamp, stateText } from "../participants/participantFormat";
import { Awards, Congressional, Lobbying, Provenance } from "../participants/sections";
import { useParticipantInstrument } from "../participants/useParticipantInstrument";
import { PanelFrame, PanelMessage, selectionGate, usePanelVisible, useSelection } from "./shared";
import "../news/news.css";
import "../participants/participants.css";

/** S12 Congress & Government: congressional disclosures, federal awards, lobbying — public records as filed, never scored. */
export default function CongressGovPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  const { query, data } = useParticipantInstrument({ universe, instrumentId: row?.instrument.instrument_id ?? null, settledId,
    lens: "congress_gov", compact: false, enabled: visible });
  const gate = selectionGate("congress_gov", row, settledId);
  const sections = data?.sections ?? {};
  return <PanelFrame id="congress_gov" state={data?.state ?? null} stateLabel={data ? stateText(data.state) : undefined} clock={data ? `updated ${stamp(data.generated_at)}` : null}
    detail={data ? data.instrument.label : null}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">Congress &amp; Government request failed. <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row?.symbol} public records…</PanelMessage>
      : <div className="news-panel participant-panel">
        <Providers providers={data.providers} label="Congress & Government sources" />
        {sections.congressional && <Congressional section={sections.congressional} compact={false} />}
        {sections.awards && <Awards section={sections.awards} compact={false} />}
        {sections.lobbying && <Lobbying section={sections.lobbying} />}
        {universe !== "US_EQUITIES" && <p className="participant-note">Awards and lobbying are company records; they are shown for US equities only.</p>}
        <Provenance data={data} />
      </div>)}
  </PanelFrame>;
}
