import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/endpoints";
import type { LifecycleAction, OperatorDiagnostics, OperatorLifecycleStatus, ProviderReadiness } from "../../api/schemas";
import type { OperatorActionResultState } from "../../state/operatorAction";
import { actionExplanation } from "../../state/operatorAction";
import { OperatorActionButton } from "../operator-action/OperatorActionButton";
import { ActionResult } from "../operator-action/ActionResult";
import {
  applyUpdateAction,
  checkUpdateAction,
  providerConfigSaveAction,
  providerRefreshAction,
  reloadControlAction,
  restartPlatformAction,
  type LifecycleSnapshot,
} from "./controlOperatorActions";
import {
  queryKeys,
  useContextQuery,
  useOperatorConfigQuery,
  useOperatorDiagnosticsQuery,
  usePaperPortfolioQuery,
} from "../../api/hooks";
import { resolveSemanticState, SEMANTIC_TONE_ICON } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { EmptyState, ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { PageHeader } from "../shared/PageHeader";
import { evaluateModeContext } from "../mode-session/modeAuthority";
import type { Mode } from "../mode-session/types";
import { liveFeedClockHonesty } from "../opportunity/opportunityOperatorBrief";
import { humanizeUnreadyReason } from "../opportunity/opportunityPresentation";
import {
  CONTROL_SECTIONS,
  CONTROL_SECTION_NAV,
  authoritySummary,
  buildAttentionItems,
  isLiveClockWithheldFeed,
  partitionProviders,
  presentProviderRole,
  presentProviderTransport,
  providerNeedsAction,
} from "./controlPresentation";
import { buildGovernanceFacts } from "../operator-shared/governanceStatusPresentation";
import { OperatorSystemStatusSection } from "./OperatorSystemStatusSection";
import {
  diagnosticsLifecycle,
  diagnosticsOpportunitySurface,
  diagnosticsReadiness,
  diagnosticsRuntimeSection,
  formatItem9CorpusProgress,
  item9CorpusProgressIsCalendarIncomplete,
} from "./operatorDiagnosticsPresentation";

type Props = {
  mode: Mode;
};

type OperatorConfig = Awaited<ReturnType<typeof api.getOperatorConfig>>;

function providerLabel(provider: ProviderReadiness): string {
  return provider.label ?? provider.provider;
}

function CheckingFact({ children }: { children: string }) {
  return (
    <span className="control-checking" role="status" aria-busy="true">
      {children}
    </span>
  );
}

/**
 * Control — the operator's destination for "can IMP operate correctly and
 * safely right now?": operating state, execution authority, provider/data
 * health, opportunity-feed readiness, and the legitimate corrective actions
 * for each. Deep engineering telemetry stays in Diagnostics; persistent
 * preferences stay in Settings. Every state rendered here is a translation of
 * a real backend contract value via the shared semantic adapter — unknown or
 * unavailable state renders honestly, never as healthy.
 */
export function OperatorControlCenterPage({ mode }: Props) {
  const location = useLocation();
  const queryClient = useQueryClient();
  const diagnosticsQuery = useOperatorDiagnosticsQuery();
  const configQuery = useOperatorConfigQuery();
  const contextQuery = useContextQuery();
  const paperPortfolioQuery = usePaperPortfolioQuery("PAPER", mode === "PAPER");

  const diagnostics = diagnosticsQuery.data;
  const readiness = diagnosticsReadiness(diagnostics);
  const lifecycle = diagnosticsLifecycle(diagnostics) as OperatorLifecycleStatus | undefined;
  const opportunitySurface = diagnosticsOpportunitySurface(diagnostics);

  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [actionResults, setActionResults] = useState<Record<string, OperatorActionResultState | null>>({});

  const contextState = contextQuery.isLoading
    ? "loading"
    : contextQuery.error || !contextQuery.data
      ? "error"
      : "ready";
  const asOf = contextQuery.data?.as_of_context;
  const evaluation = evaluateModeContext(mode, asOf);

  // Hash deep-links (Command "Open Control" → #control-feed, StatusBar →
  // #control-authority): scroll to the section once it has rendered and mark
  // it so the operator sees where they landed.
  const hash = location.hash.replace(/^#/, "");
  const [settledHash, setSettledHash] = useState<string | null>(null);

  const feedStatus = opportunitySurface?.feed_status;
  const humanizedReason = humanizeUnreadyReason(opportunitySurface?.unready_reason);
  const governanceFacts = buildGovernanceFacts({
    asOf,
    capabilityStates: contextQuery.data?.capability_states,
    readinessRoot: readiness?.root ?? null,
    diagnostics,
  });
  const paperSessionOpen =
    mode === "PAPER" && paperPortfolioQuery.data
      ? Boolean(paperPortfolioQuery.data.session)
      : undefined;

  const attentionItems = buildAttentionItems({
    mode,
    contextState,
    evaluation: contextState === "ready" ? evaluation : undefined,
    readiness,
    readinessError: diagnosticsQuery.isError,
    lifecycleStatus: lifecycle?.status,
    lifecycleError: diagnosticsQuery.isError,
    feedStatus,
    feedUnreadyReason: opportunitySurface?.unready_reason,
    feedError: diagnosticsQuery.isError,
    paperSessionOpen,
    humanizedUnreadyReason: humanizedReason,
    diagnosticsError: diagnosticsQuery.isError,
  });

  const allSettled = !diagnosticsQuery.isLoading && contextState !== "loading";

  useEffect(() => {
    if (!hash || settledHash === hash) return;
    const target = document.getElementById(hash);
    if (!target) return;
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ block: "start" });
    }
    if (typeof target.focus === "function") {
      target.focus({ preventScroll: true });
    }
    setSettledHash(hash);
  }, [
    hash,
    settledHash,
    diagnosticsQuery.isLoading,
    diagnosticsQuery.isError,
    contextState,
    attentionItems.length,
  ]);

  const lifecycleSnapshot = (): LifecycleSnapshot => {
    const state = queryClient.getQueryState(queryKeys.operatorDiagnostics);
    const data = queryClient.getQueryData<OperatorDiagnostics>(queryKeys.operatorDiagnostics);
    return {
      loading: state?.fetchStatus === "fetching" && data == null,
      failed: state?.status === "error",
      lifecycle: diagnosticsLifecycle(data),
    };
  };

  const rememberResult = (id: string, result: OperatorActionResultState | null) => {
    setActionResults((current) => ({ ...current, [id]: result }));
  };

  const reloadStatus = async () => {
    const action = reloadControlAction();
    if (pendingActionId) return;
    setPendingActionId(action.id);
    rememberResult(action.id, null);
    const diagnostics = await diagnosticsQuery.refetch();
    await Promise.all([
      configQuery.refetch(),
      contextQuery.refetch(),
      mode === "PAPER" ? paperPortfolioQuery.refetch() : Promise.resolve(),
    ]);
    if (diagnostics.isError) {
      rememberResult(action.id, {
        kind: "REQUEST_FAILED",
        message: "Status could not be reloaded.",
      });
    } else {
      rememberResult(action.id, {
        kind: "SUCCESS",
        message: "Status reloaded from the local platform.",
      });
    }
    setPendingActionId(null);
  };

  const runLifecycleAction = async (kind: LifecycleAction) => {
    const descriptor =
      kind === "restart"
        ? restartPlatformAction(lifecycleSnapshot())
        : kind === "check_update"
          ? checkUpdateAction(lifecycleSnapshot())
          : applyUpdateAction(lifecycleSnapshot());
    if (pendingActionId) return;
    if (descriptor.availability !== "AVAILABLE") {
      rememberResult(descriptor.id, {
        kind: "REQUEST_FAILED",
        message: actionExplanation(descriptor),
        reasonCode: descriptor.reason?.code,
      });
      return;
    }
    setPendingActionId(descriptor.id);
    rememberResult(descriptor.id, null);
    const queuedLabel = `${kind.replace(/_/g, " ")} queued.`;
    try {
      const operation = await api.runOperatorLifecycleAction(kind);
      if (operation.status === "BLOCKED") {
        rememberResult(descriptor.id, {
          kind: "REQUEST_FAILED",
          message: operation.detail?.trim() || `${queuedLabel} The platform refused the action.`,
          reasonCode: "UPDATE_BLOCKED",
        });
        return;
      }
      const refreshed = await diagnosticsQuery.refetch();
      if (refreshed.isError) {
        rememberResult(descriptor.id, {
          kind: "REFRESH_FAILED_AFTER_MUTATION",
          message: `${queuedLabel} Platform status could not be reloaded afterward.`,
        });
        return;
      }
      const verified = operation.status === "SUCCEEDED";
      rememberResult(descriptor.id, {
        kind: verified ? "SUCCESS" : "RESULT_UNVERIFIED",
        message: verified
          ? queuedLabel
          : `${queuedLabel} The refreshed snapshot does not prove the operation finished.`,
      });
    } catch {
      rememberResult(descriptor.id, {
        kind: "REQUEST_FAILED",
        message: `Could not queue ${kind.replace(/_/g, " ")}. Start the local platform first.`,
      });
    } finally {
      setPendingActionId(null);
    }
  };

  const refreshProvider = async (provider: ProviderReadiness) => {
    const descriptor = providerRefreshAction(provider);
    if (pendingActionId) return;
    setPendingActionId(descriptor.id);
    rememberResult(descriptor.id, null);
    const label = providerLabel(provider);
    try {
      const operation = await api.refreshOperatorProvider(provider.provider);
      if (operation.status === "BLOCKED") {
        rememberResult(descriptor.id, {
          kind: "REQUEST_FAILED",
          message: `Refresh could not be queued for ${label}.`,
          reasonCode: "PROVIDER_REFRESH_BLOCKED",
        });
        return;
      }
      const refreshed = await diagnosticsQuery.refetch();
      const queued = `Refresh queued for ${label}.`;
      if (refreshed.isError) {
        rememberResult(descriptor.id, {
          kind: "REFRESH_FAILED_AFTER_MUTATION",
          message: `${queued} Provider status could not be reloaded afterward.`,
        });
        return;
      }
      rememberResult(descriptor.id, {
        kind: operation.status === "SUCCEEDED" ? "SUCCESS" : "RESULT_UNVERIFIED",
        message:
          operation.status === "SUCCEEDED"
            ? queued
            : `${queued} The refreshed snapshot does not prove the refresh finished.`,
      });
    } catch {
      rememberResult(descriptor.id, {
        kind: "REQUEST_FAILED",
        message: `Refresh could not be queued for ${label}.`,
      });
    } finally {
      setPendingActionId(null);
    }
  };

  const readinessState = readiness
    ? resolveSemanticState("platform", readiness.status)
    : null;
  const lifecycleState = lifecycle
    ? resolveSemanticState("platform", lifecycle.status)
    : null;
  const lifecycleActions = {
    restart: restartPlatformAction({
      loading: diagnosticsQuery.isLoading,
      failed: diagnosticsQuery.isError,
      lifecycle,
    }),
    checkUpdate: checkUpdateAction({
      loading: diagnosticsQuery.isLoading,
      failed: diagnosticsQuery.isError,
      lifecycle,
    }),
    applyUpdate: applyUpdateAction({
      loading: diagnosticsQuery.isLoading,
      failed: diagnosticsQuery.isError,
      lifecycle,
    }),
  };
  const reloadAction = reloadControlAction();

  return (
    <section className="page control-page">
      <a className="control-skip-link" href={`#${CONTROL_SECTIONS.systemStatus}`}>
        Skip to system status
      </a>
      <PageHeader
        eyebrow="Control"
        title="Platform control"
        subtitle="Can this workstation operate safely right now? Status is translated into trader language; canonical tokens stay visible. Calendar waits are IDLE, not DEGRADED."
        actions={
          <OperatorActionButton
            action={reloadAction}
            pending={pendingActionId === reloadAction.id}
            result={actionResults[reloadAction.id]}
            onActivate={reloadStatus}
          />
        }
      />

      <nav className="control-page-nav" aria-label="Control sections">
        {CONTROL_SECTION_NAV.map((item) => (
          <a key={item.id} href={`#${item.id}`} aria-current={hash === item.id ? "location" : undefined}>
            {item.label}
          </a>
        ))}
      </nav>

      {/* A. System operating state */}
      <section
        className="control-panel control-hero"
        id={CONTROL_SECTIONS.overview}
        tabIndex={-1}
        aria-labelledby="control-overview-heading"
        aria-busy={diagnosticsQuery.isLoading || contextState === "loading" || undefined}
        data-highlighted={hash === CONTROL_SECTIONS.overview ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Operating state</div>
            <h2 id="control-overview-heading">Platform status</h2>
          </div>
          {diagnosticsQuery.dataUpdatedAt ? (
            <FreshnessIndicator asOf={diagnosticsQuery.dataUpdatedAt} cadenceSeconds={60} />
          ) : null}
        </div>
        <dl className="control-fact-grid">
          <div className="control-fact">
            <dt>Setup readiness</dt>
            <dd>
              {diagnosticsQuery.isLoading ? (
                <CheckingFact>Checking…</CheckingFact>
              ) : diagnosticsQuery.isError || !readinessState ? (
                <StatePill tone="neutral" label="Unavailable" raw="UNAVAILABLE" />
              ) : (
                <StatePill
                  tone={readinessState.tone}
                  label={readinessState.label}
                  raw={readiness?.status}
                />
              )}
              <p className="control-fact-hint">Workstation setup. Missing dates are not a failed setup.</p>
            </dd>
          </div>
          <div className="control-fact">
            <dt>Platform runtime</dt>
            <dd>
              {diagnosticsQuery.isLoading ? (
                <CheckingFact>Checking…</CheckingFact>
              ) : diagnosticsQuery.isError || !lifecycleState ? (
                <StatePill tone="neutral" label="Unavailable" raw="UNAVAILABLE" />
              ) : (
                <StatePill
                  tone={lifecycleState.tone}
                  label={lifecycleState.label}
                  raw={lifecycle?.status}
                />
              )}
              <p className="control-fact-hint">Local services running or stopped — not trading skill.</p>
            </dd>
          </div>
          <div className="control-fact">
            <dt>Backend context</dt>
            <dd>
              {contextState === "loading" ? (
                <CheckingFact>Verifying…</CheckingFact>
              ) : contextState === "error" ? (
                <StatePill tone="caution" label="Unavailable — controls locked" raw="UNAVAILABLE" />
              ) : (
                <StatePill
                  tone={evaluation.status === "mismatch" ? "critical" : "live"}
                  label={evaluation.status === "mismatch" ? "UI and backend disagree" : "Connected"}
                  raw={evaluation.status}
                />
              )}
              <p className="control-fact-hint">UI mode cannot override backend authority.</p>
            </dd>
          </div>
          <div className="control-fact">
            <dt>Market data</dt>
            <dd>
              {contextState !== "ready" ? (
                <StatePill tone="neutral" label="Unknown" raw="UNKNOWN" />
              ) : (
                (() => {
                  const quality = resolveSemanticState(
                    "dataHealth",
                    contextQuery.data?.quality_summary.state,
                  );
                  return (
                    <StatePill
                      tone={quality.tone}
                      label={quality.label}
                      raw={contextQuery.data?.quality_summary.state}
                    />
                  );
                })()
              )}
              <p className="control-fact-hint">Quotes and research coverage — never live execution.</p>
            </dd>
          </div>
        </dl>
        {allSettled && attentionItems.length === 0 ? (
          <>
            <p className="control-all-clear" role="status">
              No blocking issues detected across readiness, authority, providers, and the opportunity
              feed.
            </p>
            {item9CorpusProgressIsCalendarIncomplete(diagnostics) ? (
              <p className="control-muted" role="note">
                Item 9 prospective sample gate is calendar-incomplete (
                {formatItem9CorpusProgress(diagnosticsRuntimeSection(diagnostics)?.item9_corpus_status)
                  .distinctRthDates}
                ) — IDLE, not DEGRADED. Methodology waits for more regular-trading-hours dates; the
                workstation is not failing. See System status.
              </p>
            ) : null}
          </>
        ) : null}
        <div className="control-hero-actions" role="group" aria-label="Platform actions">
          <OperatorActionButton
            action={lifecycleActions.restart}
            pending={pendingActionId === lifecycleActions.restart.id}
            result={actionResults[lifecycleActions.restart.id]}
            onActivate={() => runLifecycleAction("restart")}
          />
          <OperatorActionButton
            action={lifecycleActions.checkUpdate}
            pending={pendingActionId === lifecycleActions.checkUpdate.id}
            result={actionResults[lifecycleActions.checkUpdate.id]}
            onActivate={() => runLifecycleAction("check_update")}
          />
          <OperatorActionButton
            action={lifecycleActions.applyUpdate}
            pending={pendingActionId === lifecycleActions.applyUpdate.id}
            result={actionResults[lifecycleActions.applyUpdate.id]}
            onActivate={() => runLifecycleAction("apply_update")}
            confirmId="control-confirm-apply"
          />
        </div>
        {lifecycle?.update ? (
          <p className="control-muted">
            Updates: {lifecycle.update.detail ?? resolveSemanticState("platform", lifecycle.update.status).label}
          </p>
        ) : null}
        <p className="control-muted">
          Lifecycle controls manage this local workstation only — they do not change trading
          authority. Live execution remains locked.
        </p>
      </section>

      <section
        className="control-panel control-system-status-panel"
        id={CONTROL_SECTIONS.systemStatus}
        tabIndex={-1}
        aria-labelledby="control-system-status-heading"
        aria-busy={diagnosticsQuery.isLoading || undefined}
        data-highlighted={hash === CONTROL_SECTIONS.systemStatus ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Diagnostics</div>
            <h2 id="control-system-status-heading">System status</h2>
          </div>
        </div>
        <p className="control-muted">
          One composed snapshot of whether the platform can operate: services, setup, Item 9 sample
          gate, and safety locks. Truth classes stay separate; missing evidence is not upgraded to
          healthy. Calendar waits stay IDLE.
        </p>
        <p className="control-muted">
          Technical source: <code>GET /operator/diagnostics</code> (API snapshot). The workstation
          page for this truth is Control system status.
        </p>
        <OperatorSystemStatusSection
          diagnostics={diagnostics}
          isLoading={diagnosticsQuery.isLoading}
          isError={diagnosticsQuery.isError}
          onRetry={() => void diagnosticsQuery.refetch()}
        />
      </section>

      {/* Governance & empirical honesty (read-only) */}
      <section
        className="control-panel"
        id={CONTROL_SECTIONS.governance}
        tabIndex={-1}
        aria-labelledby="control-governance-heading"
        data-highlighted={hash === CONTROL_SECTIONS.governance ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Governance</div>
            <h2 id="control-governance-heading">Program gates & runtime truth</h2>
          </div>
        </div>
        <p className="control-muted">
          Calibration, collector, and runtime SHA come from backend contracts only. Missing fields stay
          explicit — the UI never fabricates Item 9 3/3 or backfills observational gaps.
        </p>
        <dl className="control-fact-grid">
          {governanceFacts.map((fact) => (
            <div key={fact.id} className="control-fact">
              <dt>{fact.label}</dt>
              <dd>
                <StatePill tone={fact.tone} label={fact.value} raw={fact.raw ?? fact.value} />
                {fact.detail ? <p className="control-muted">{fact.detail}</p> : null}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {/* B. Execution / authority */}
      <section
        className="control-panel"
        id={CONTROL_SECTIONS.authority}
        tabIndex={-1}
        aria-labelledby="control-authority-heading"
        aria-busy={contextState === "loading" || undefined}
        data-highlighted={hash === CONTROL_SECTIONS.authority ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Safety</div>
            <h2 id="control-authority-heading">Execution & authority</h2>
          </div>
        </div>
        {contextState === "error" ? (
          <AttentionBanner
            tone="caution"
            affects="Execution controls remain locked until the backend context is reachable."
          >
            Backend context unavailable.
          </AttentionBanner>
        ) : null}
        {contextState === "ready" && evaluation.status === "mismatch" ? (
          <AttentionBanner
            tone="critical"
            affects="UI mode selection does not change backend authority."
          >
            Selected {mode}; backend reports {evaluation.actualSummary}. Switch mode or restart the
            backend session.
          </AttentionBanner>
        ) : null}
        <dl className="control-fact-grid control-authority-grid">
          <div className="control-fact">
            <dt>Mode</dt>
            <dd>
              <StatePill
                tone={resolveSemanticState("mode", mode).tone}
                label={resolveSemanticState("mode", mode).label}
                raw={mode}
              />
            </dd>
          </div>
          <div className="control-fact">
            <dt>Data</dt>
            <dd>
              {(() => {
                const dataState = resolveSemanticState("session", asOf?.data_mode, {
                  params: { provider: asOf?.data_provider },
                });
                return (
                  <StatePill tone={dataState.tone} label={dataState.label} raw={asOf?.data_mode} />
                );
              })()}
            </dd>
          </div>
          <div className="control-fact">
            <dt>Execution</dt>
            <dd>
              {(() => {
                const execState = resolveSemanticState("executionAuthority", asOf?.execution_mode);
                return (
                  <StatePill
                    tone={execState.tone}
                    label={execState.label}
                    raw={asOf?.execution_mode}
                  />
                );
              })()}
            </dd>
          </div>
          <div className="control-fact">
            <dt>Authority</dt>
            <dd>
              {(() => {
                const authorityState = resolveSemanticState(
                  "executionAuthority",
                  asOf?.execution_authority ?? (contextState === "ready" ? "BLOCKED" : undefined),
                );
                return (
                  <StatePill
                    tone={authorityState.tone}
                    label={authorityState.label}
                    raw={asOf?.execution_authority}
                  />
                );
              })()}
            </dd>
          </div>
        </dl>
        <p className="control-authority-summary">{authoritySummary(mode, contextState, evaluation)}</p>
        {mode === "PAPER" && contextState === "ready" ? (
          <p className="control-muted">
            {paperPortfolioQuery.isLoading ? (
              "Checking paper account…"
            ) : paperPortfolioQuery.isError ? (
              "Paper account state unavailable — order entry stays locked."
            ) : paperPortfolioQuery.data?.session ? (
              <>
                Paper session open · account{" "}
                <CopyableIdentifier
                  value={paperPortfolioQuery.data.account.paper_account_id}
                  chars={4}
                />
              </>
            ) : (
              <>
                No paper session open — open one from{" "}
                <Link to="/portfolio">Portfolio</Link> before submitting paper orders.
              </>
            )}
          </p>
        ) : null}
        <p className="control-muted">
          Data availability, execution capability, and execution authority are separate: live market
          data never implies live execution. Live execution remains locked.
        </p>
      </section>

      {/* E. Required operator attention — only real, actionable issues */}
      {attentionItems.length > 0 ? (
        <section
          className="control-panel control-attention"
          id={CONTROL_SECTIONS.attention}
          tabIndex={-1}
          aria-labelledby="control-attention-heading"
          aria-live="polite"
          data-highlighted={hash === CONTROL_SECTIONS.attention ? "true" : undefined}
        >
          <div className="control-panel-heading">
            <div>
              <div className="control-panel-kicker">Actionable</div>
              <h2 id="control-attention-heading">Needs your attention</h2>
            </div>
          </div>
          <ul className="control-attention-list">
            {attentionItems.map((item) => (
              <li key={item.id} className="control-attention-item" data-tone={item.tone}>
                <span className="control-attention-icon" aria-hidden="true">
                  {SEMANTIC_TONE_ICON[item.tone]}
                </span>
                <div className="control-attention-body">
                  <strong>{item.title}</strong>
                  {item.detail ? <p>{item.detail}</p> : null}
                </div>
                {item.action ? <Link to={item.action.href}>{item.action.label}</Link> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* C. Data / provider health */}
      <section
        className="control-panel"
        id={CONTROL_SECTIONS.providers}
        tabIndex={-1}
        aria-labelledby="control-providers-heading"
        aria-busy={diagnosticsQuery.isLoading || undefined}
        data-highlighted={hash === CONTROL_SECTIONS.providers ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Data connections</div>
            <h2 id="control-providers-heading">Providers</h2>
          </div>
          <Link to="/diagnostics/provider" className="control-section-link">
            View provider diagnostics
          </Link>
        </div>
        {diagnosticsQuery.isLoading ? (
          <p className="control-checking" role="status" aria-live="polite" aria-busy="true">
            Checking providers… this is a load wait, not an off-by-configuration provider.
          </p>
        ) : diagnosticsQuery.isError ? (
          <>
            {Object.entries(actionResults).map(([id, result]) =>
              id.startsWith("platform.provider-refresh.") && result ? (
                <ActionResult key={id} result={result} />
              ) : null,
            )}
            <ErrorState
              title="Provider readiness is unavailable."
              affects="This is a load failure. Provider states are unknown until the local platform responds."
              rawDetail="GET /operator/diagnostics sections.readiness.providers"
              onRetry={() => void diagnosticsQuery.refetch()}
            />
          </>
        ) : (
          <ProviderGroups
            providers={readiness?.providers ?? []}
            pendingActionId={pendingActionId}
            results={actionResults}
            onRefresh={(provider) => refreshProvider(provider)}
          />
        )}
      </section>

      {/* D. Opportunity / feed readiness */}
      <section
        className="control-panel"
        id={CONTROL_SECTIONS.feed}
        tabIndex={-1}
        aria-labelledby="control-feed-heading"
        aria-busy={diagnosticsQuery.isLoading || undefined}
        data-highlighted={hash === CONTROL_SECTIONS.feed ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Opportunities</div>
            <h2 id="control-feed-heading">Opportunity feed readiness</h2>
          </div>
          <Link to="/radar" className="control-section-link">
            Open Radar
          </Link>
        </div>
        {diagnosticsQuery.isLoading ? (
          <p className="control-checking" role="status" aria-live="polite" aria-busy="true">
            Checking the opportunity feed… this is a load wait, not an empty queue.
          </p>
        ) : diagnosticsQuery.isError ? (
          <ErrorState
            title="Opportunity feed status could not be loaded."
            affects="This is a load failure. Feed readiness is unknown; the ranked queue may be incomplete."
            rawDetail="GET /operator/diagnostics sections.opportunity_surface"
            onRetry={() => void diagnosticsQuery.refetch()}
          />
        ) : opportunitySurface ? (
          <FeedReadiness
            mode={mode}
            feedStatus={feedStatus}
            unreadyReason={opportunitySurface.unready_reason ?? undefined}
            humanizedReason={humanizedReason}
            withheldRankedCount={opportunitySurface.withheld_ranked_count}
            bookHonesty={opportunitySurface.book_honesty}
            nextAction={undefined}
            itemCount={undefined}
            qualityState={opportunitySurface.quality_summary?.state}
          />
        ) : (
          <EmptyState
            title="Opportunity feed status was not included"
            reason="The snapshot responded but did not include an opportunity-surface section. That is NOT_OBSERVED, not a ready queue."
          />
        )}
      </section>

      {/* F. Deeper technical status */}
      <section
        className="control-panel"
        id={CONTROL_SECTIONS.technical}
        tabIndex={-1}
        aria-labelledby="control-technical-heading"
        data-highlighted={hash === CONTROL_SECTIONS.technical ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Deeper status</div>
            <h2 id="control-technical-heading">Technical detail</h2>
          </div>
        </div>
        <nav className="control-related-links" aria-label="Related operator pages">
          <Link to="/diagnostics/provider">Provider diagnostics</Link>
          <Link to="/settings">Settings</Link>
          <Link to="/live-canary">Live canary safety</Link>
        </nav>
        {lifecycle ? (
          <details className="control-details">
            <summary>Runtime services and update detail</summary>
            <dl className="control-details-grid">
              <div>
                <dt>Lifecycle status (raw)</dt>
                <dd>{lifecycle.status}</dd>
              </div>
              <div>
                <dt>Last action</dt>
                <dd>{lifecycle.last_action ?? "—"}</dd>
              </div>
              <div>
                <dt>Update status (raw)</dt>
                <dd>{lifecycle.update?.status ?? "—"}</dd>
              </div>
              {(lifecycle.services ?? []).map((service: Record<string, unknown>) => (
                <div key={String(service.name)}>
                  <dt>{String(service.name)}</dt>
                  <dd>
                    pid {String(service.pid ?? "—")} ·{" "}
                    {service.owned ? "owned" : "not owned"}
                  </dd>
                </div>
              ))}
            </dl>
            {(lifecycle.logs ?? []).length ? (
              <p className="control-muted">Logs: {(lifecycle.logs ?? []).join(", ")}</p>
            ) : null}
          </details>
        ) : null}
        {readiness ? (
          <details className="control-details">
            <summary>Setup checks</summary>
            <ul className="control-check-list">
              {readiness.checks.map((check) => {
                const checkState = resolveSemanticState("platform", check.status);
                return (
                  <li key={check.id} className="control-check" data-tone={checkState.tone}>
                    <StatePill
                      tone={checkState.tone}
                      label={checkState.label}
                      raw={check.status}
                      size="sm"
                    />
                    <div>
                      <strong>{check.label}</strong>
                      <p>{check.detail}</p>
                      {check.next_action ? <small>Next: {check.next_action}</small> : null}
                    </div>
                  </li>
                );
              })}
              {!readiness.checks.length ? (
                <li className="control-muted">No setup checks reported.</li>
              ) : null}
            </ul>
          </details>
        ) : null}
      </section>

      {/* Advanced: credential configuration (configuration, not status) */}
      <details className="control-panel control-advanced">
        <summary>
          Provider credentials (advanced)
        </summary>
        <p className="control-muted">
          Configuration, not current status — values stay on this workstation and are never
          displayed. Saving credentials does not change trading authority.
        </p>
        {configQuery.isLoading ? (
          <p className="control-checking" role="status">
            Loading configuration…
          </p>
        ) : configQuery.isError ? (
          <ErrorState
            title="Provider configuration is unavailable."
            affects="Credentials cannot be edited until the local platform responds."
            onRetry={() => void configQuery.refetch()}
          />
        ) : (
          <div className="control-config-grid">
            {(configQuery.data?.providers ?? []).map((provider) => (
              <ProviderConfigCard
                key={provider.provider}
                provider={provider}
                onSaved={(next) => queryClient.setQueryData(queryKeys.operatorConfig, next)}
                savePending={pendingActionId === `platform.provider-config.${provider.label}`}
                onSaveStart={() => setPendingActionId(`platform.provider-config.${provider.label}`)}
                onSaveFinish={() => setPendingActionId(null)}
              />
            ))}
            {!configQuery.data?.providers?.length ? (
              <p className="control-muted">No editable provider configuration is available yet.</p>
            ) : null}
          </div>
        )}
      </details>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Providers                                                                  */
/* -------------------------------------------------------------------------- */

function ProviderGroups({
  providers,
  pendingActionId,
  results,
  onRefresh,
}: {
  providers: ProviderReadiness[];
  pendingActionId: string | null;
  results: Record<string, OperatorActionResultState | null>;
  onRefresh: (provider: ProviderReadiness) => Promise<void>;
}) {
  const groups = partitionProviders(providers);
  if (!providers.length) {
    return (
      <EmptyState
        title="No provider rows yet"
        reason="The snapshot has no provider readiness rows. That is empty, not a failed provider. Off-by-configuration providers appear under the disclosure when present."
      />
    );
  }
  return (
    <>
      <p className="control-muted" role="status">
        {groups.active.length + groups.attention.length} active · {groups.attention.length} need
        attention · {groups.inactive.length} off by configuration
      </p>
      <div className="control-provider-list">
        {[...groups.attention, ...groups.active].map((provider) => (
          <ProviderRow
            key={provider.provider}
            provider={provider}
            pendingActionId={pendingActionId}
            result={results[providerRefreshAction(provider).id]}
            onRefresh={() => onRefresh(provider)}
          />
        ))}
      </div>
      {groups.inactive.length ? (
        <details className="control-details">
          <summary>Off by configuration ({groups.inactive.length})</summary>
          <div className="control-provider-list">
            {groups.inactive.map((provider) => (
              <ProviderRow
                key={provider.provider}
                provider={provider}
                pendingActionId={pendingActionId}
                result={results[providerRefreshAction(provider).id]}
                onRefresh={() => onRefresh(provider)}
              />
            ))}
          </div>
        </details>
      ) : null}
    </>
  );
}

function ProviderRow({
  provider,
  pendingActionId,
  result,
  onRefresh,
}: {
  provider: ProviderReadiness;
  pendingActionId: string | null;
  result?: OperatorActionResultState | null;
  onRefresh: () => Promise<void>;
}) {
  const transport = presentProviderTransport(provider);
  const credential = resolveSemanticState("providerHealth", provider.credential_state);
  const gate = resolveSemanticState("providerHealth", provider.gate_state);
  const role = presentProviderRole(provider.role);
  const needsAction = providerNeedsAction(provider);
  return (
    <article className="control-provider-row" data-attention={needsAction || undefined}>
      <div className="control-provider-main">
        <div className="control-provider-title">
          <h3>{providerLabel(provider)}</h3>
          <StatePill
            tone={transport.tone}
            label={transport.label}
            raw={provider.transport_state}
            size="sm"
          />
        </div>
        {role ? <p className="control-provider-capability">{role.capability}</p> : null}
        {transport.sentence ? (
          <p className="control-provider-transport-meaning">{transport.sentence}</p>
        ) : null}
        {needsAction && role?.impact ? (
          <p className="control-provider-impact">{role.impact}</p>
        ) : null}
        {needsAction ? <p className="control-provider-next">Next: {provider.next_action}</p> : null}
        <p className="control-provider-secondary">
          Credentials: {credential.label} · Gate: {gate.label}
          {provider.freshness ? ` · ${provider.freshness}` : ""}
        </p>
      </div>
      <div className="control-provider-actions">
        <OperatorActionButton
          action={providerRefreshAction(provider)}
          pending={pendingActionId === providerRefreshAction(provider).id}
          result={result}
          accessibleName={`Refresh ${providerLabel(provider)}`}
          onActivate={onRefresh}
        />
      </div>
    </article>
  );
}

/* -------------------------------------------------------------------------- */
/* Opportunity feed readiness                                                 */
/* -------------------------------------------------------------------------- */

function FeedReadiness({
  mode,
  feedStatus,
  unreadyReason,
  humanizedReason,
  withheldRankedCount,
  bookHonesty,
  nextAction,
  itemCount,
  qualityState,
}: {
  mode: Mode;
  feedStatus?: string;
  unreadyReason?: string;
  humanizedReason: string | null;
  withheldRankedCount?: number;
  bookHonesty?: string;
  nextAction?: string;
  itemCount?: number;
  qualityState?: string;
}) {
  const feedState = resolveSemanticState("research", feedStatus);
  const quality = qualityState ? resolveSemanticState("dataHealth", qualityState) : null;
  const nextActionHref = nextAction?.startsWith("/") ? nextAction : null;
  const nextActionText = nextAction && !nextAction.startsWith("/") ? nextAction : null;

  return (
    <div className="control-feed">
      <div className="control-feed-status">
        <StatePill tone={feedState.tone} label={feedState.label} raw={feedStatus} />
        {quality ? (
          <StatePill tone={quality.tone} label={quality.label} raw={qualityState} size="sm" />
        ) : null}
      </div>

      {feedStatus === "READY" ? (
        <p className="control-muted">
          The ranked opportunity queue is ready
          {itemCount != null
            ? ` — ${itemCount} ${itemCount === 1 ? "opportunity" : "opportunities"} currently listed`
            : " — row count not included in diagnostics snapshot"}
          . An empty queue is valid: nothing has been minted for the current coverage.
        </p>
      ) : null}

      {feedStatus === "UNREADY" ? (
        isLiveClockWithheldFeed({ feedStatus, feedUnreadyReason: unreadyReason }) ? (
          <div className="control-feed-detail" data-tone="neutral">
            <p>
              <strong>Why:</strong> {humanizedReason ?? "The live clock is unavailable."}
            </p>
            <p>
              <strong>Impact:</strong>{" "}
              {liveFeedClockHonesty({ unreadyReason, withheldRankedCount }) ??
                "Ranked live rows stay withheld until a live receive clock is attached. This is not Item 9 calibration. Live execution stays OFF."}
            </p>
            {bookHonesty ? (
              <p className="control-muted">
                Book honesty: <code>{bookHonesty}</code>
              </p>
            ) : null}
            {unreadyReason ? (
              <p className="control-muted">
                Raw reason code: <code>{unreadyReason}</code>
              </p>
            ) : null}
          </div>
        ) : (
          <div className="control-feed-detail" data-tone="caution">
            <p>
              <strong>Why:</strong> {humanizedReason ?? "The feed has not reported a reason."}
            </p>
            <p>
              <strong>Impact:</strong> The ranked opportunity queue may be incomplete — treat Radar
              results with caution until the feed reports ready.
            </p>
            {nextActionText ? (
              <p>
                <strong>Next:</strong> {nextActionText}
              </p>
            ) : null}
            {unreadyReason ? (
              <p className="control-muted">
                Raw reason code: <code>{unreadyReason}</code>
              </p>
            ) : null}
          </div>
        )
      ) : null}

      {feedStatus === "UNAVAILABLE" ? (
        mode === "LIVE" ? (
          <p className="control-muted">
            Live mode has no opportunity engine — this is by design. Use Radar screeners and
            workspace evidence to investigate instruments.
          </p>
        ) : (
          <div className="control-feed-detail" data-tone="critical">
            <p>
              <strong>Impact:</strong> Ranked opportunities cannot be trusted right now. Screeners
              and workspace evidence remain available.
            </p>
            {nextActionText ? (
              <p>
                <strong>Next:</strong> {nextActionText}
              </p>
            ) : (
              <p>
                <strong>Next:</strong> check provider states above, then{" "}
                <Link to="/diagnostics/provider">provider diagnostics</Link> if the cause is not
                visible here.
              </p>
            )}
          </div>
        )
      ) : null}

      {feedStatus === "EMPTY" ? (
        <p className="control-muted">
          No opportunities right now — an empty queue is valid: nothing has been minted for the
          current coverage.
        </p>
      ) : null}

      {feedStatus && !["READY", "UNREADY", "UNAVAILABLE", "EMPTY"].includes(feedStatus) ? (
        <p className="control-muted">
          The feed reported an unrecognized state (<code>{feedStatus}</code>). Treat the ranked
          queue with caution.
        </p>
      ) : null}

      {nextActionHref && nextActionHref !== "/control" ? (
        <p className="control-muted">
          Suggested next step: <Link to={nextActionHref}>{nextActionHref}</Link>
        </p>
      ) : null}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Provider credential configuration (advanced)                               */
/* -------------------------------------------------------------------------- */

function ProviderConfigCard({
  provider,
  onSaved,
  savePending,
  onSaveStart,
  onSaveFinish,
}: {
  provider: OperatorConfig["providers"][number];
  onSaved: (config: OperatorConfig) => void;
  savePending: boolean;
  onSaveStart: () => void;
  onSaveFinish: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<OperatorActionResultState | null>(null);
  const saveAction = providerConfigSaveAction(provider.label);

  async function save() {
    if (savePending) return;
    onSaveStart();
    setResult(null);
    try {
      const next = await api.saveOperatorProviderConfig(provider.provider, values);
      onSaved(next);
      setValues({});
      setResult({
        kind: "SUCCESS",
        message: "Saved. Restart the API if the provider is already running.",
      });
    } catch {
      setResult({
        kind: "REQUEST_FAILED",
        message: "Configuration was not saved. Check the fields and operator permissions.",
      });
    } finally {
      onSaveFinish();
    }
  }

  return (
    <article className="control-config-card">
      <div className="control-provider-title">
        <h3>{provider.label}</h3>
      </div>
      {provider.fields.map((field) => (
        <label className="control-config-field" key={field.key}>
          <span>{field.label}</span>
          <input
            type={field.sensitive ? "password" : "text"}
            value={values[field.key] ?? ""}
            placeholder={field.configured ? "Configured — leave blank to keep" : "Not configured"}
            autoComplete="off"
            onChange={(event) =>
              setValues((current) => ({ ...current, [field.key]: event.target.value }))
            }
          />
          <small>{field.configured ? "A value is stored locally." : "No value is stored."}</small>
        </label>
      ))}
      <OperatorActionButton
        action={saveAction}
        pending={savePending}
        result={result}
        onActivate={save}
      />
    </article>
  );
}
