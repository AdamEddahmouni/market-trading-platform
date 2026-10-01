import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchScreenerSetup, SETUP_QUERY_KEY, type SetupRow } from "../../../api/screenerSetup";
import { stateText } from "../news/newsFormat";
import { ProviderSetupList } from "../setup/ProviderConfig";
import { RemedyHint } from "../setup/Remedy";
import { ErrorDetail, PanelFrame, PanelMessage, usePanelVisible } from "./shared";
import "../setup/setup.css";

const REFRESH_MS = 30_000;

function pill(row: SetupRow) {
  if (row.state === "CURRENT" && !row.remedy) return { tone: "ready", text: "ready" };
  if (row.state === "CURRENT") return { tone: "wait", text: "not started" };
  if (row.state === "LIVE_DISABLED" || row.state === "NOT_CONFIGURED" || row.state === "TERMS_ACCEPTANCE_REQUIRED") {
    return { tone: "off", text: row.state === "TERMS_ACCEPTANCE_REQUIRED" ? "needs terms" : stateText(row.state) };
  }
  return { tone: "down", text: stateText(row.state) };
}

/**
 * Each free capability, its state, and the single step that enables it (built from existing provider
 * states), then every provider setting IMP accepts: keys, tokens, and the SEC contact identity.
 */
export default function SetupPanel({ api }: IDockviewPanelProps) {
  const visible = usePanelVisible(api);
  const query = useQuery({
    queryKey: SETUP_QUERY_KEY, queryFn: ({ signal }) => fetchScreenerSetup(signal),
    enabled: visible, staleTime: 10_000, refetchInterval: visible ? REFRESH_MS : false, retry: 1,
  });
  const data = query.data;
  return <PanelFrame id="setup" instrumentScoped={false} state={data ? (data.ready_count === data.total ? "CURRENT" : "PARTIAL") : null}
    stateLabel={data ? `${data.ready_count}/${data.total} ready` : undefined}>
    {query.isError && !data ? <PanelMessage tone="error" role="alert">Setup status request failed.<ErrorDetail error={query.error} /> <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Checking capabilities…</PanelMessage>
      : <div className="setup-panel">
        <p className="setup-summary">{data.ready_count} of {data.total} free capabilities ready. Each row names the one step that enables it. Keys and the SEC contact identity are entered below; they stay on this computer and are never shown again.</p>
        <ul className="setup-list" aria-label="Setup checklist">{data.rows.map((row) => {
          const status = pill(row);
          return <li key={row.id} className="setup-row">
            <span className="setup-row-label">{row.label}</span>
            <span className={`setup-pill ${status.tone}`} title={row.reason ? `Reason: ${row.reason}` : undefined}>{status.text}</span>
            <span className="setup-row-step">{row.remedy ? <RemedyHint remedy={row.remedy} compact />
              : row.state === "CURRENT" ? <span className="setup-ready">Ready</span>
              : <span title={row.reason ?? undefined}>{row.reason ? row.reason.replace(/_/g, " ").toLowerCase() : "—"}</span>}</span>
          </li>;
        })}</ul>
        <ProviderSetupList enabled={visible} />
      </div>}
  </PanelFrame>;
}
