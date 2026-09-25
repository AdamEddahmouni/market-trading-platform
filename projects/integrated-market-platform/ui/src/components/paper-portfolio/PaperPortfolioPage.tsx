import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  useClosePaperSessionMutation,
  useOpenPaperSessionMutation,
  usePaperPortfolioQuery,
} from "../../api/hooks";
import { humanizeEnum, resolveSemanticState } from "../../state/semanticState";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { StatePill } from "../imp-ui/StatePill";
import { ExecutionTracePanel } from "../paper/ExecutionTracePanel";
import { canUsePaperActions } from "../mode-session/modeAuthority";
import { LoadingState } from "../shared/LoadingState";
import { PageHeader } from "../shared/PageHeader";
import {
  PaperPortfolioObservability,
  PortfolioGlanceStrip,
  PortfolioPositionsSection,
} from "../portfolio-shared/PaperPortfolioObservability";
import { PaperStrategyProfitabilityObservability } from "../paper-strategy-profitability/PaperStrategyProfitabilityObservability";
import { PaperOrderHistory } from "./PaperOrderHistory";
import { paperCapitalHonesty } from "./paperPortfolioPresentation";
import { AttentionBanner } from "../imp-ui/AttentionBanner";

type StoredSession = {
  session_id: string;
  status: string;
  created_at?: number;
  closed_at?: number | null;
  data_mode?: string;
  execution_mode?: string;
};

type Props = {
  paperActionsPermitted: boolean;
};

export function PaperPortfolioPage({ paperActionsPermitted }: Props) {
  const portfolioQuery = usePaperPortfolioQuery();
  const openSession = useOpenPaperSessionMutation();
  const closeSession = useClosePaperSessionMutation();
  const [traceIntentId, setTraceIntentId] = useState<string | undefined>();
  const [traceOrderId, setTraceOrderId] = useState<string | undefined>();
  const [sessions, setSessions] = useState<StoredSession[]>([]);
  const [sessionsError, setSessionsError] = useState(false);

  function loadSessions() {
    setSessionsError(false);
    void fetch("/paper/sessions")
      .then(async (response) => {
        if (!response.ok) throw new Error("SESSION_LIST_HTTP_ERROR");
        const payload = await response.json();
        if (
          !Array.isArray(payload?.sessions) ||
          !payload.sessions.every(
            (row: StoredSession) =>
              row && typeof row.session_id === "string" && typeof row.status === "string",
          )
        ) {
          throw new Error("SESSION_LIST_INVALID_RESPONSE");
        }
        setSessions(payload.sessions);
      })
      .catch(() => {
        setSessionsError(true);
        setSessions([]);
      });
  }

  useEffect(() => {
    loadSessions();
  }, [portfolioQuery.data?.session?.session_id, portfolioQuery.data?.account?.session_id]);

  if (portfolioQuery.isLoading) {
    return (
      <section className="page portfolio-page paper-portfolio-page">
        <PageHeader
          eyebrow="Paper-only simulation"
          title="Paper Portfolio"
          subtitle="Simulated positions, cash, and P&L — not live capital. Submit stays in Workspace."
        />
        <LoadingState label="Loading simulation account…" />
      </section>
    );
  }

  if (portfolioQuery.isError || !portfolioQuery.data) {
    return (
      <section className="page portfolio-page paper-portfolio-page">
        <PageHeader
          eyebrow="Paper-only simulation"
          title="Paper Portfolio"
          subtitle="Simulated positions, cash, and P&L — not live capital. Submit stays in Workspace."
        />
        <ErrorState
          title="Simulation account observability is unavailable."
          affects="Positions, cash, P&L, and session controls cannot be shown."
          onRetry={() => void portfolioQuery.refetch()}
        />
      </section>
    );
  }

  const data = portfolioQuery.data;
  const { account } = data;
  const actionEligible = canUsePaperActions("PAPER", paperActionsPermitted, account);
  const activeInstrument = data.active_instrument?.trim();
  const workspaceHref = activeInstrument
    ? `/workspace/${encodeURIComponent(activeInstrument)}`
    : "/workspace";
  const honesty = paperCapitalHonesty("PAPER");
  const onTraceOrder = (intentId?: string, orderId?: string) => {
    setTraceIntentId(intentId);
    setTraceOrderId(orderId);
  };

  return (
    <section className="page portfolio-page paper-portfolio-page">
      <PageHeader
        eyebrow="Paper-only simulation"
        title="Paper Portfolio"
        subtitle="Exposure and active execution state. Orders are submitted from Workspace."
        actions={
          <div className="portfolio-header-actions">
            <Link className="portfolio-header-action" to={workspaceHref}>
              Open Workspace
            </Link>
            {actionEligible ? (
              <>
                <button
                  type="button"
                  onClick={() => void closeSession.mutateAsync()}
                  disabled={closeSession.isPending}
                >
                  Archive session
                </button>
                <button
                  type="button"
                  onClick={() => void openSession.mutateAsync(activeInstrument)}
                  disabled={openSession.isPending || !activeInstrument}
                  title={activeInstrument ? undefined : "Choose an instrument in Workspace first."}
                >
                  New Paper Session
                </button>
              </>
            ) : null}
          </div>
        }
        restriction={
          actionEligible ? undefined : (
            <aside className="panel mode-restriction-note" role="note">
              <strong>Paper authority unavailable.</strong>
              <p>
                Session archive/new require INTERNAL SIMULATION and PAPER ONLY authority. Order
                submit remains in Workspace even when those session actions are available.
              </p>
            </aside>
          )
        }
      />

      <div className="portfolio-layout">
        <div className="portfolio-main">
          <AttentionBanner tone={honesty.tone} affects={honesty.affects}>
            {honesty.sentence}
          </AttentionBanner>

          <PortfolioGlanceStrip data={data} />

          <PaperPortfolioObservability
            data={data}
            viewMode="PAPER"
            hideOrdersSection
            onTraceOrder={onTraceOrder}
            sections={["attention"]}
          />

          <PortfolioPositionsSection data={data} viewMode="PAPER" />

          <PaperOrderHistory
            data={data}
            onViewTrace={onTraceOrder}
            canCancelOrders={actionEligible}
          />

          <details className="portfolio-secondary-disclosure" data-testid="portfolio-secondary">
            <summary>
              <span>Account detail, fills and strategy lineage</span>
              <small>Secondary detail</small>
            </summary>
            <div className="portfolio-secondary-body">
              <PaperPortfolioObservability
                data={data}
                viewMode="PAPER"
                hideOrdersSection
                onTraceOrder={onTraceOrder}
                sections={["account", "exposure", "fills"]}
              />
              <PaperStrategyProfitabilityObservability />
            </div>
          </details>

          <details className="portfolio-session-history-disclosure" data-testid="portfolio-session-history">
            <summary>
              <span>Session history</span>
              <small>Secondary history</small>
            </summary>
            <section className="panel session-history-panel" aria-labelledby="portfolio-sessions-heading">
              <div className="paper-order-history-header">
                <h2 id="portfolio-sessions-heading">Session history</h2>
                <button type="button" onClick={loadSessions}>
                  Refresh sessions
                </button>
              </div>
              {sessionsError ? (
                <p className="muted">Session list unavailable. Refresh to retry. The current account session above remains authoritative.</p>
              ) : sessions.length === 0 ? (
                <p className="muted">No persisted sessions yet.</p>
              ) : (
                <ul className="portfolio-session-list">
                  {sessions.map((row) => {
                    const status = resolveSemanticState("session", row.status);
                    return (
                      <li key={row.session_id}>
                        <StatePill tone={status.tone} label={status.label} raw={status.raw} size="sm" />
                        <CopyableIdentifier value={row.session_id} />
                        <span>
                          {row.data_mode ? humanizeEnum(row.data_mode) : "Data mode unavailable"}
                          {" / "}
                          {row.execution_mode
                            ? humanizeEnum(row.execution_mode)
                            : "Execution mode unavailable"}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </details>

        </div>

        {traceIntentId || traceOrderId ? (
          <ExecutionTracePanel
            intentId={traceIntentId}
            orderId={traceOrderId}
            onClose={() => {
              setTraceIntentId(undefined);
              setTraceOrderId(undefined);
            }}
          />
        ) : null}
      </div>
    </section>
  );
}
