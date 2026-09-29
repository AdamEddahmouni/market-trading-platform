import type { ScreenerRow, ScreenerUniverse } from "../../../api/screener";
import type { ParticipantLens } from "../../../api/screenerParticipants";
import { stateText } from "./participantFormat";
import { Awards, Beneficial, Congressional, FuturesPositioning, Holdings13F, Insiders } from "./sections";
import { useParticipantInstrument } from "./useParticipantInstrument";
import "../news/news.css";
import "./participants.css";

type Props = {
  row: ScreenerRow;
  /** The settled selection: arrowing through rows never requests disclosures for each one. */
  settledId: string | null;
  universe: ScreenerUniverse;
  institutional: boolean;
  government: boolean;
  onOpen?: (lens: ParticipantLens) => void;
};

function Lens({ row, settledId, universe, lens }: Omit<Props, "institutional" | "government" | "onOpen"> & { lens: ParticipantLens }) {
  const { query, data } = useParticipantInstrument({ universe, instrumentId: row.instrument.instrument_id, settledId, lens, compact: true });
  const label = lens === "institutional" ? "Institutional & Whale" : "Congress & Government";
  if (!data) {
    return <p className="screener-preview-note" role={query.isError ? "alert" : "status"}>{query.isError
      ? <>{label} unavailable for {row.symbol}. <button type="button" onClick={() => void query.refetch()}>Retry</button></> : `Loading ${label.toLowerCase()}…`}</p>;
  }
  const s = data.sections;
  return <div aria-label={`${label} summary`}>
    <p className="screener-preview-meta"><strong>{label}</strong> · {stateText(data.state)}</p>
    {s.futures_positioning && <FuturesPositioning section={s.futures_positioning} compact />}
    {s.beneficial_ownership && <Beneficial section={s.beneficial_ownership} compact />}
    {s.insiders && <Insiders section={{ ...s.insiders, filings: ((s.insiders as { filings?: unknown[] }).filings ?? []).slice(0, 1) }} compact />}
    {s.holdings_13f && <Holdings13F section={s.holdings_13f} compact />}
    {s.congressional && <Congressional section={s.congressional} compact />}
    {s.awards && <Awards section={s.awards} compact />}
  </div>;
}

/** Compact Quick Preview of the S12 lenses; each opens its full dock panel. */
export function PreviewParticipants({ row, settledId, universe, institutional, government, onOpen }: Props) {
  return <section className="participant-preview" aria-label={`Participants and public records for ${row.symbol}`}>
    {institutional && <Lens row={row} settledId={settledId} universe={universe} lens="institutional" />}
    {government && <Lens row={row} settledId={settledId} universe={universe} lens="congress_gov" />}
    <div className="participant-actions">
      {institutional && <button type="button" className="screener-control screener-primary" onClick={() => onOpen?.("institutional")}>Open Institutional &amp; Whale</button>}
      {government && <button type="button" className="screener-control screener-primary" onClick={() => onOpen?.("congress_gov")}>Open Congress &amp; Government</button>}
    </div>
  </section>;
}
