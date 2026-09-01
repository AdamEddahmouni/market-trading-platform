import { useEffect, useState } from "react";
import {
  useClosePaperSessionMutation,
  useOpenPaperSessionMutation,
  usePaperPortfolioQuery,
} from "../../api/hooks";
import { ExecutionTracePanel } from "../paper/ExecutionTracePanel";
import { OrderTicket } from "../paper/OrderTicket";
import { canUsePaperActions } from "../mode-session/modeAuthority";
import { LoadingState } from "../shared/LoadingState";
import { PageHeader } from "../shared/PageHeader";
import { PaperPortfolioObservability } from "../portfolio-shared/PaperPortfolioObservability";
import { PaperOrderHistory } from "./PaperOrderHistory";

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

  useEffect(() => {
    void fetch("/paper/sessions")
      .then((response) => response.json())
      .then((payload) => setSessions(payload.sessions ?? []))
      .catch(() => undefined);
  }, [portfolioQuery.data?.session?.session_id, portfolioQuery.data?.account?.session_id]);

  if (portfolioQuery.isLoading) {
    return (
      <section className="page portfolio-page paper-portfolio-page">
        <PageHeader eyebrow="Paper-only simulation" title="Paper Portfolio" />
        <LoadingState label="Loading simulation account…" />
      </section>
    );
  }

  if (portfolioQuery.isError || !portfolioQuery.data) {
    return (
      <section className="page portfolio-page paper-portfolio-page">
        <PageHeader eyebrow="Paper-only simulation" title="Paper Portfolio" />
        <div className="capability-panel unavailable">
          <p>Simulation account observability unavailable.</p>
        </div>
      </section>
    );
  }

  const data = portfolioQuery.data;
  const { account, risk, data_health, session } = data;
  const symbol = data.active_instrument ?? null;
  const actionEligible = canUsePaperActions("PAPER", paperActionsPermitted, account);

  return (
    <section className="page portfolio-page paper-portfolio-page">
      <PageHeader
        eyebrow="Paper-only simulation"
        title="Paper Portfolio"
        meta={
          <>
            DATA: {account.data_mode.replace(/_/g, " ")} · {account.data_provider} · QUALITY {data_health.state}
            {" · "}
            EXEC: {account.execution_mode.replace(/_/g, " ")} · AUTH {account.execution_authority}
            {session ? (
              <>
                {" · "}
                Session {session.session_id.slice(0, 12)}… · cash starting{" "}
                {session.starting_cash_minor ? `${session.starting_cash_minor} minor` : "UNAVAILABLE"}
              </>
            ) : null}
          </>
        }
        actions={
          actionEligible ? (
            <div className="live-actions">
              <button
                type="button"
                onClick={() => void closeSession.mutateAsync()}
                disabled={closeSession.isPending}
              >
                Archive session
              </button>
              <button
                type="button"
                onClick={() => void openSession.mutateAsync(symbol ?? undefined)}
                disabled={openSession.isPending}
              >
                New Paper Session
              </button>
            </div>
          ) : undefined
        }
        restriction={
          actionEligible ? undefined : (
            <aside className="panel mode-restriction-note" role="note">
              <strong>Paper authority unavailable.</strong>
              <p>Order and session controls require INTERNAL SIMULATION and PAPER ONLY authority.</p>
            </aside>
          )
        }
      />

      <div className="portfolio-layout">
        <div className="portfolio-main">
          {actionEligible ? (
            <OrderTicket
              symbol={symbol}
              executionAuthority={account.execution_authority}
              executionMode={account.execution_mode}
              dataMode={account.data_mode}
              maxOrderShares={risk.limits.max_order_shares}
              onSubmitted={(intentId) => {
                if (intentId) setTraceIntentId(intentId);
              }}
            />
          ) : null}

          <PaperPortfolioObservability
            data={data}
            hideOrdersSection
            onTraceOrder={(intentId, orderId) => {
              setTraceIntentId(intentId);
              setTraceOrderId(orderId);
            }}
          />

          <PaperOrderHistory
            data={data}
            onViewTrace={(intentId, orderId) => {
              setTraceIntentId(intentId);
              setTraceOrderId(orderId);
            }}
          />

          <section className="panel session-history-panel">
            <h2>Session history</h2>
            {sessions.length === 0 ? (
              <p className="muted">No persisted sessions yet.</p>
            ) : (
              <ul>
                {sessions.map((row) => (
                  <li key={row.session_id}>
                    {row.status} · {row.session_id.slice(0, 12)}… · {row.data_mode} /{" "}
                    {row.execution_mode}
                  </li>
                ))}
              </ul>
            )}
          </section>
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
