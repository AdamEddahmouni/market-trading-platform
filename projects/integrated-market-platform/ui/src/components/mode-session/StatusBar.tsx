import { useNavigate } from "react-router-dom";
import type { ContextResponse } from "../../api/client";
import { resolveSemanticState } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { evaluateModeContext } from "./modeAuthority";
import type { Mode } from "./types";

type Props = {
  mode: Mode;
  /** Parsed `/context` response; undefined while unavailable. */
  context?: ContextResponse;
  contextState: "loading" | "ready" | "error";
};

function formatAsOfTime(iso: string | undefined, timezone: string | undefined): string {
  if (!iso) return "unknown time";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "unknown time";
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: timezone || undefined,
      timeZoneName: "short",
    }).format(date);
  } catch {
    return date.toISOString();
  }
}

/**
 * The one status bar: ModeBadge + execution authority + data health +
 * as-of/scope, with raw enums and timestamps behind the L4 details
 * disclosure. Replaces the stacked ModeEnvironmentBar + ContextBar pair.
 * Fail-closed messaging (mismatch / unavailable context) is preserved as a
 * banner row beneath the bar.
 */
export function StatusBar({ mode, context, contextState }: Props) {
  const navigate = useNavigate();
  const asOf = context?.as_of_context;
  const evaluation = evaluateModeContext(mode, asOf);
  const modeState = resolveSemanticState("mode", mode);
  const authorityState = resolveSemanticState(
    "executionAuthority",
    asOf?.execution_authority ?? (contextState === "ready" ? "BLOCKED" : undefined),
  );
  const healthState = resolveSemanticState("dataHealth", context?.quality_summary.state);
  const dataState = resolveSemanticState("session", asOf?.data_mode, {
    params: { provider: asOf?.data_provider },
  });
  const scope = context?.scope_symbols ?? [];
  const scopeLabel = scope.length ? scope.join(", ") : "No instrument selected";
  // Replay/frozen data does not decay (semantic-state-system §6): show the
  // as-of time only. Freshness banding applies to live/delayed data.
  const isLiveData =
    asOf?.data_mode === "LIVE_OBSERVATIONAL" || asOf?.data_mode === "BROKER_DELAYED";

  const showMismatch = contextState === "ready" && evaluation.status === "mismatch";
  const showUnavailable =
    contextState === "error" || (contextState !== "loading" && evaluation.status === "unavailable");

  return (
    <div className="imp-status-bar-stack">
      <section
        className="imp-status-bar"
        aria-label="Session environment"
        data-mode={mode}
        data-testid="imp-status-bar"
      >
        <span className="imp-status-bar-mode" data-testid="imp-status-bar-mode">
          <StatePill tone={modeState.tone} label={modeState.label} raw={mode} />
          {modeState.sentence ? (
            <span className="imp-status-bar-mode-sentence">{modeState.sentence}</span>
          ) : null}
        </span>
        <span className="imp-status-bar-item" data-testid="imp-status-bar-authority">
          <StatePill
            tone={authorityState.tone}
            label={authorityState.label}
            raw={asOf?.execution_authority}
            size="sm"
          />
        </span>
        <button
          type="button"
          className="imp-status-bar-health"
          onClick={() => navigate("/diagnostics/provider")}
          data-testid="imp-status-bar-health"
        >
          <StatePill
            tone={healthState.tone}
            label={healthState.label}
            raw={context?.quality_summary.state}
            size="sm"
          />
          {asOf && isLiveData ? (
            <FreshnessIndicator asOf={asOf.as_of_time} cadenceSeconds={5} />
          ) : null}
          {!asOf ? <FreshnessIndicator backendLabel="UNKNOWN" /> : null}
        </button>
        <span className="imp-status-bar-item imp-status-bar-data">
          {dataState.label}
          {asOf ? (
            <>
              {" · "}
              <time dateTime={asOf.as_of_time}>
                as of {formatAsOfTime(asOf.as_of_time, asOf.timezone)}
              </time>
            </>
          ) : null}
        </span>
        <span className="imp-status-bar-item imp-status-bar-scope" title={scopeLabel}>
          {scopeLabel}
        </span>
        <details className="imp-status-bar-details">
          <summary>Technical details</summary>
          <dl className="imp-status-bar-details-grid">
            <div>
              <dt>UI mode</dt>
              <dd>{mode}</dd>
            </div>
            <div>
              <dt>Data</dt>
              <dd>{asOf?.data_mode ?? "UNAVAILABLE"}</dd>
            </div>
            <div>
              <dt>Execution</dt>
              <dd>{asOf?.execution_mode ?? "UNAVAILABLE"}</dd>
            </div>
            <div>
              <dt>Authority</dt>
              <dd>{asOf?.execution_authority ?? "UNAVAILABLE"}</dd>
            </div>
            <div>
              <dt>Quality</dt>
              <dd>{context?.quality_summary.state ?? "UNAVAILABLE"}</dd>
            </div>
            <div>
              <dt>Scope</dt>
              <dd>{scopeLabel}</dd>
            </div>
            <div>
              <dt>As of (raw)</dt>
              <dd>{asOf?.as_of_time ?? "UNAVAILABLE"}</dd>
            </div>
          </dl>
        </details>
      </section>
      {contextState === "loading" ? (
        <p className="imp-status-bar-note" role="status">
          Verifying backend context…
        </p>
      ) : null}
      {showUnavailable ? (
        <AttentionBanner
          tone="caution"
          affects="Execution controls remain locked."
          action={{ label: "Open Control", href: "/control" }}
        >
          Backend context unavailable.
        </AttentionBanner>
      ) : null}
      {showMismatch ? (
        <AttentionBanner tone="critical" affects="UI mode selection does not change backend authority.">
          Selected {mode}; backend reports {evaluation.actualSummary}. Switch mode or restart the
          backend session.
        </AttentionBanner>
      ) : null}
    </div>
  );
}
