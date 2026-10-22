import { useAiScreenerRuns } from "../ai/useAiScreenerRuns";
import { PanelFrame, useSelection } from "./shared";

/**
 * The dock entry is a shortcut: the AI Screener lives in the right rail's AI tab. Its controls are never mounted here as
 * well, so reevaluation, Paper automation and decision timers run once. The status is read from the cache the AI strip
 * already keeps current; this panel starts no request of its own.
 */
export default function AiScreenerPanel() {
  const { openAiRail } = useSelection();
  const data = useAiScreenerRuns(false).runs.data;
  const selected = data?.latest?.summary?.selected.length;
  const status = !data ? null : data.active ? "A run is in progress." : data.latest
    ? `Latest pass: ${data.latest.state.toLowerCase()}${selected !== undefined ? ` · ${selected} selected` : ""}.` : "No pass yet.";
  return <PanelFrame id="ai_screener" instrumentScoped={false}>
    <p className="ai-screener-shortcut">AI Screener results, decisions and reevaluation controls are in the right rail’s AI tab.</p>
    {status && <p className="ai-screener-meta">{status}</p>}
    <button type="button" className="screener-primary ai-screener-run" onClick={() => openAiRail?.()} disabled={!openAiRail}>Show in right rail</button>
  </PanelFrame>;
}
