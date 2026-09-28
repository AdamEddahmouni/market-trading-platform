import { memo, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ScreenerFilter, ScreenerRow } from "../../../api/screener";
import { fetchBondPreview, type BondItem, type BondPreview } from "../../../api/screenerBonds";
import { bondValue, CLASS_LABEL, isoDate, provenance, reasonLabel, sourceState } from "./bondFormat";
import { PreviewNewsSection } from "../news/PreviewNewsSection";
import "./bonds.css";

const SELECTION_SETTLE_MS = 180;

export type BondQuickPreviewProps = {
  row: ScreenerRow | null;
  filters: ScreenerFilter[];
  screenLabel: string | null;
  overlay: boolean;
  width: number;
  paneRef?: React.Ref<HTMLElement>;
  onClose: () => void;
  ratesSupported: boolean;
  onOpenRates?: () => void;
  newsSupported?: boolean;
  onOpenNews?: () => void;
};

/** The provenance most of a section's values share; shown once under the section title. */
function commonProvenance(items: BondItem[]) {
  const counts = new Map<string, number>();
  for (const item of items) if (item.value !== null && item.source) counts.set(provenance(item), (counts.get(provenance(item)) ?? 0) + 1);
  const [top] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  return top && top[1] > 1 ? top[0] : "";
}

function Sections({ preview }: { preview: BondPreview }) {
  return <>{preview.sections.filter((section) => section.id !== "identity").map((section) => {
    const shared = commonProvenance(section.items);
    return <section key={section.id} className="bond-preview-section" aria-label={section.title}>
      <h3>{section.title}{shared && <small className="bond-section-source">{shared}</small>}</h3>
      <dl>{section.items.map((item) => {
        const own = item.value !== null && provenance(item) !== shared ? provenance(item) : "";
        const line = item.value === null ? item.note ?? "" : [own, item.class !== "OBSERVED" ? item.note : null].filter(Boolean).join(" · ");
        return <div key={item.id} className={`bond-item ${item.class.toLowerCase()}`}
          title={[provenance(item), item.note].filter(Boolean).join(" — ")}>
          <dt>{item.label}</dt>
          <dd><span className="bond-item-value">{bondValue(item.value, item.unit)}</span>
            {item.class !== "OBSERVED" && <span className="bond-item-class">{CLASS_LABEL[item.class]}</span>}
            {line && <small>{line}</small>}</dd>
        </div>;
      })}</dl>
    </section>;
  })}</>;
}

function BondQuickPreviewInner({ row, filters, screenLabel, overlay, width, paneRef, onClose, ratesSupported, onOpenRates, newsSupported = false, onOpenNews }: BondQuickPreviewProps) {
  const id = row?.instrument.instrument_id ?? null;
  const [requestId, setRequestId] = useState(id);
  useEffect(() => {
    const timer = window.setTimeout(() => setRequestId(id), SELECTION_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [id]);
  const filterKey = JSON.stringify(filters);
  const preview = useQuery({
    queryKey: ["screener-bond-preview", requestId, filterKey],
    queryFn: ({ signal }) => fetchBondPreview(requestId!, filters, signal),
    enabled: Boolean(requestId) && requestId === id, staleTime: 60_000, retry: 1, refetchInterval: 300_000,
  });
  const data = preview.data && preview.data.instrument.instrument_id === id ? preview.data : undefined;
  const matched = data?.why.matched;
  return <aside className={`screener-preview bond-preview${overlay ? " overlay" : ""}`} aria-label="Quick preview" ref={paneRef as React.Ref<HTMLElement>}
    tabIndex={-1} style={overlay ? undefined : { width }}
    onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } }}>
    <header className="screener-preview-header">
      <span className="screener-preview-kicker">Quick Preview · Bond</span>
      <button type="button" className="screener-preview-close" onClick={onClose} aria-label="Close quick preview">×</button>
    </header>
    {!row ? <p className="screener-preview-empty">Select a security to preview its terms, latest auction, and rates context.</p> : <>
      <div className="bond-preview-identity">
        <h2>{row.company}</h2>
        <p><span>CUSIP <strong>{row.cusip ?? row.symbol}</strong></span><span>{row.security_type}</span>
          <span>{row.issuer ?? "U.S. Treasury"}</span><span className="bond-reference-only">Reference only</span></p>
        <dl className="bond-preview-headline">
          <div><dt>Coupon</dt><dd>{bondValue(row.fields.coupon?.value ?? null, "percent")}</dd></div>
          <div><dt>Maturity</dt><dd>{isoDate(row.maturity)}</dd></div>
          <div><dt>Years</dt><dd>{bondValue(row.fields.years_to_maturity?.value ?? null, "years")}</dd></div>
          <div><dt>Price</dt><dd title="No permitted security-level Treasury price source is integrated">—</dd></div>
        </dl>
      </div>
      {preview.isError && !data ? <p className="screener-preview-note" role="alert">Preview unavailable for {row.cusip}. <button type="button" onClick={() => void preview.refetch()}>Retry</button></p> :
        !data ? <p className="screener-preview-note" aria-live="polite">Loading {row.cusip}…</p> :
        <div className="bond-preview-body" tabIndex={0} aria-label={`${row.company} details`}>
          {matched && matched.state !== "NO_ACTIVE_FILTERS" && <section className="bond-preview-section" aria-label="Why it matched">
            <h3>Why it matched{screenLabel ? <span className="screener-muted"> · {screenLabel}</span> : null}</h3>
            <ul className="screener-why-list">{matched.items.map((item) => <li key={item.filter_id} className={item.passed ? "pass" : "fail"}>
              <span aria-hidden="true">{item.passed ? "✓" : "✕"}</span><span className="sr-only">{item.passed ? "Passes: " : "Does not pass: "}</span>{item.text}</li>)}</ul>
          </section>}
          <Sections preview={data} />
          <section className="bond-preview-section" aria-label="Source clocks">
            <h3>Sources</h3>
            <ul className="bond-sources">{data.sources.map((source) => <li key={source.id}>
              <span>{source.label}</span><span className={`bond-source-state ${(source.state ?? "unavailable").toLowerCase()}`}>{sourceState(source)}</span>
              <small>{source.as_of ? (source.as_of.length > 10 ? new Date(source.as_of).toLocaleString() : isoDate(source.as_of)) : reasonLabel(source.reason)}</small></li>)}</ul>
          </section>
        </div>}
      {newsSupported && <PreviewNewsSection row={row} settledId={requestId} universe="BONDS" onOpenNews={onOpenNews} />}
      <footer className="screener-preview-footer bond-preview-footer">
        <button type="button" className="screener-control screener-primary" disabled={!ratesSupported} onClick={() => onOpenRates?.()}>Open Rates &amp; Curve</button>
        <span className="screener-muted">Reference only · no bond Workspace or execution</span>
      </footer>
    </>}
  </aside>;
}

export const BondQuickPreview = memo(BondQuickPreviewInner);
