import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/endpoints";
import type { LifecycleAction, OperatorLifecycleStatus, ProviderReadiness } from "../../api/schemas";
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
import { ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { PageHeader } from "../shared/PageHeader";
import { evaluateModeContext } from "../mode-session/modeAuthority";
import type { Mode } from "../mode-session/types";
import { humanizeUnreadyReason } from "../opportunity/opportunityPresentation";
import {
  CONTROL_SECTIONS,
  authoritySummary,
  buildAttentionItems,
  partitionProviders,
  presentProviderRole,
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

  const [message, setMessage] = useState<string | null>(null);
  const [busyProvider, setBusyProvider] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<LifecycleAction | null>(null);
  const [confirmingUpdate, setConfirmingUpdate] = useState(false);

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
  useEffect(() => {
    if (!hash || settledHash === hash) return;
    const target = document.getElementById(hash);
    if (!target) return;
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ block: "start" });
    }
    setSettledHash(hash);
  });

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

  const refreshAll = () => {
    setMessage(null);
    void diagnosticsQuery.refetch();
    void configQuery.refetch();
    void contextQuery.refetch();
    if (mode === "PAPER") void paperPortfolioQuery.refetch();
  };

  const runLifecycleAction = async (action: LifecycleAction) => {
    setBusyAction(action);
    setMessage(null);
    try {
      await api.runOperatorLifecycleAction(action);
      setMessage(`${action.replace(/_/g, " ")} queued.`);
      await diagnosticsQuery.refetch();
    } catch {
      setMessage(`Could not queue ${action.replace(/_/g, " ")}. Start the local platform first.`);
    } finally {
      setBusyAction(null);
      setConfirmingUpdate(false);
    }
  };

  const refreshProvider = async (provider: ProviderReadiness) => {
    setBusyProvider(provider.provider);
    setMessage(null);
    try {
      await api.refreshOperatorProvider(provider.provider);
      setMessage(`Refresh queued for ${providerLabel(provider)}.`);
      await diagnosticsQuery.refetch();
    } catch {
      setMessage(`Refresh could not be queued for ${providerLabel(provider)}.`);
    } finally {
      setBusyProvider(null);
    }
  };

  const readinessState = readiness
    ? resolveSemanticState("platform", readiness.status)
    : null;
  const lifecycleState = lifecycle
    ? resolveSemanticState("platform", lifecycle.status)
    : null;
  const updateAvailable = lifecycle?.update?.status === "AVAILABLE";

  return (
    <section className="page control-page">
      <PageHeader
        eyebrow="Control"
        title="Platform control"
        subtitle="Operating state, execution authority, data providers, and the opportunity feed — what is wrong, what it affects, and what you can safely do next."
        actions={
          <button
            type="button"
            onClick={refreshAll}
            disabled={diagnosticsQuery.isFetching}
          >
            {diagnosticsQuery.isFetching ? "Checking…" : "Check again"}
          </button>
        }
      />

      {message ? (
        <p className="control-message" role="status">
          {message}
        </p>
      ) : null}

      {/* A. System operating state */}
      <section
        className="control-panel control-hero"
        id={CONTROL_SECTIONS.overview}
        aria-labelledby="control-overview-heading"
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
                <span className="control-checking">Checking…</span>
              ) : diagnosticsQuery.isError || !readinessState ? (
                <StatePill tone="neutral" label="Unavailable" raw="UNAVAILABLE" />
              ) : (
                <StatePill
                  tone={readinessState.tone}
                  label={readinessState.label}
                  raw={readiness?.status}
                />
              )}
            </dd>
          </div>
          <div className="control-fact">
            <dt>Platform runtime</dt>
            <dd>
              {diagnosticsQuery.isLoading ? (
                <span className="control-checking">Checking…</span>
              ) : diagnosticsQuery.isError || !lifecycleState ? (
                <StatePill tone="neutral" label="Unavailable" raw="UNAVAILABLE" />
              ) : (
                <StatePill
                  tone={lifecycleState.tone}
                  label={lifecycleState.label}
                  raw={lifecycle?.status}
                />
              )}
            </dd>
          </div>
          <div className="control-fact">
            <dt>Backend context</dt>
            <dd>
              {contextState === "loading" ? (
                <span className="control-checking">Verifying…</span>
              ) : contextState === "error" ? (
                <StatePill tone="caution" label="Unavailable — controls locked" raw="UNAVAILABLE" />
              ) : (
                <StatePill
                  tone={evaluation.status === "mismatch" ? "critical" : "live"}
                  label={evaluation.status === "mismatch" ? "UI and backend disagree" : "Connected"}
                  raw={evaluation.status}
                />
              )}
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
                ) — methodology blocked, not a platform failure. See System status.
              </p>
            ) : null}
          </>
        ) : null}
        <div className="control-hero-actions" role="group" aria-label="Platform actions">
          <button
            type="button"
            onClick={() => void runLifecycleAction("restart")}
            disabled={busyAction !== null}
          >
            {busyAction === "restart" ? "Queueing…" : "Restart platform"}
          </button>
          <button
            type="button"
            onClick={() => void runLifecycleAction("check_update")}
            disabled={busyAction !== null}
          >
            {busyAction === "check_update" ? "Checking…" : "Check for updates"}
          </button>
          {confirmingUpdate && updateAvailable ? (
            <span className="control-confirm-group" role="group" aria-label="Confirm update">
              <button
                type="button"
                className="control-confirm-action"
                onClick={() => void runLifecycleAction("apply_update")}
                disabled={busyAction !== null}
              >
                {busyAction === "apply_update" ? "Applying…" : "Confirm apply and restart"}
              </button>
              <button type="button" onClick={() => setConfirmingUpdate(false)}>
                Cancel
              </button>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingUpdate(true)}
              disabled={!updateAvailable || busyAction !== null}
              title={
                updateAvailable
                  ? (lifecycle?.update?.detail ?? "Apply the available fast-forward update.")
                  : (lifecycle?.update?.detail ?? "A fast-forward update must be available.")
              }
            >
              Apply fast-forward update
            </button>
          )}
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
        aria-labelledby="control-system-status-heading"
        data-highlighted={hash === CONTROL_SECTIONS.systemStatus ? "true" : undefined}
      >
        <div className="control-panel-heading">
          <div>
            <div className="control-panel-kicker">Diagnostics</div>
            <h2 id="control-system-status-heading">System status</h2>
          </div>
        </div>
        <p className="control-muted">
          Composed from <code>GET /operator/diagnostics</code> — lifecycle, readiness, Item 9
          preflight, runtime resilience, and governance policy. Truth classes stay separate; missing
          evidence is not upgraded to healthy.
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
        aria-labelledby="control-authority-heading"
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
          aria-labelledby="control-attention-heading"
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
        aria-labelledby="control-providers-heading"
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
          <p className="control-checking" role="status">
            Checking providers…
          </p>
        ) : diagnosticsQuery.isError ? (
          <ErrorState
            title="Provider readiness is unavailable."
            affects="Provider states are unknown until the local platform responds."
            onRetry={() => void diagnosticsQuery.refetch()}
          />
        ) : (
          <ProviderGroups
            providers={readiness?.providers ?? []}
            busyProvider={busyProvider}
            onRefresh={(provider) => void refreshProvider(provider)}
          />
        )}
      </section>

      {/* D. Opportunity / feed readiness */}
      <section
        className="control-panel"
        id={CONTROL_SECTIONS.feed}
        aria-labelledby="control-feed-heading"
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
          <p className="control-checking" role="status">
            Checking the opportunity feed…
          </p>
        ) : diagnosticsQuery.isError ? (
          <ErrorState
            title="Opportunity feed status could not be loaded."
            affects="Feed readiness is unknown; the ranked queue may be incomplete."
            onRetry={() => void diagnosticsQuery.refetch()}
          />
        ) : opportunitySurface ? (
          <FeedReadiness
            mode={mode}
            feedStatus={feedStatus}
            unreadyReason={opportunitySurface.unready_reason}
            humanizedReason={humanizedReason}
            nextAction={undefined}
            itemCount={undefined}
            qualityState={opportunitySurface.quality_summary?.state}
          />
        ) : null}
      </section>

      {/* F. Deeper technical status */}
      <section
        className="control-panel"
        id={CONTROL_SECTIONS.technical}
        aria-labelledby="control-technical-heading"
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
              {(lifecycle.services ?? []).map((service) => (
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
  busyProvider,
  onRefresh,
}: {
  providers: ProviderReadiness[];
  busyProvider: string | null;
  onRefresh: (provider: ProviderReadiness) => void;
}) {
  const groups = partitionProviders(providers);
  if (!providers.length) {
    return <p className="control-muted">No provider readiness rows are available yet.</p>;
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
            busy={busyProvider === provider.provider}
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
                busy={busyProvider === provider.provider}
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
  busy,
  onRefresh,
}: {
  provider: ProviderReadiness;
  busy: boolean;
  onRefresh: () => void;
}) {
  const transport = resolveSemanticState("providerHealth", provider.transport_state);
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
        <button
          type="button"
          onClick={onRefresh}
          disabled={busy}
          aria-label={`Refresh ${providerLabel(provider)}`}
        >
          {busy ? "Queueing…" : "Refresh"}
        </button>
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
  nextAction,
  itemCount,
  qualityState,
}: {
  mode: Mode;
  feedStatus?: string;
  unreadyReason?: string;
  humanizedReason: string | null;
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
}: {
  provider: OperatorConfig["providers"][number];
  onSaved: (config: OperatorConfig) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const next = await api.saveOperatorProviderConfig(provider.provider, values);
      onSaved(next);
      setValues({});
      setMessage("Saved. Restart the API if the provider is already running.");
    } catch {
      setMessage("Configuration was not saved. Check the fields and operator permissions.");
    } finally {
      setSaving(false);
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
      <button type="button" onClick={() => void save()} disabled={saving}>
        {saving ? "Saving…" : `Save ${provider.label}`}
      </button>
      {message ? (
        <p className="control-config-message" role="status">
          {message}
        </p>
      ) : null}
    </article>
  );
}
