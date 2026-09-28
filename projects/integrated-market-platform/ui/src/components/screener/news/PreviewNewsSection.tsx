import { useEffect, useState } from "react";
import type { ScreenerRow, ScreenerUniverse } from "../../../api/screener";
import { PreviewNews } from "./PreviewNews";

/** Collapsed News section for previews without tabs; news is requested only once expanded. */
export function PreviewNewsSection({ row, settledId, universe, onOpenNews }:
  { row: ScreenerRow; settledId: string | null; universe: ScreenerUniverse; onOpenNews?: () => void }) {
  const [open, setOpen] = useState(false);
  // A universe change collapses the section again.
  useEffect(() => setOpen(false), [universe]);
  const regionId = `preview-news-${universe.toLowerCase()}`;
  return <div className="news-preview-section">
    <button type="button" className="news-preview-toggle" aria-expanded={open} aria-controls={regionId} onClick={() => setOpen(!open)}>
      <span aria-hidden="true">{open ? "▾" : "▸"}</span> News</button>
    <div id={regionId}>{open && <PreviewNews row={row} settledId={settledId} universe={universe} onOpenNews={onOpenNews} />}</div>
  </div>;
}
