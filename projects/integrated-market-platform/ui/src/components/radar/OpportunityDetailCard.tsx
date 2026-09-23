import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { AttentionItem } from "../../api/client";
import type {
  OpportunityAckAction,
  OpportunityEvidenceResponse,
  OpportunityReviewRow,
} from "../../api/opportunityClient";
import { resolveSemanticState } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";
import { buildOpportunityDetailSections } from "../opportunity/opportunityDetailModel";
import { buildDecisionProvenancePresentation } from "../opportunity/decisionProvenancePresentation";
import {
  buildOpportunityEpistemicLayers,
  epistemicLayerTitle,
  hasNonFactualResearchOutput,
  type EpistemicLayerKey,
} from "../opportunity/opportunityEpistemicLayers";
import {
  buildOpportunityOperatorBrief,
  opportunityFreshnessQueueLabel,
  readProviderLinkageWarnings,
  type OperatorBriefFeedContext,
} from "../opportunity/opportunityOperatorBrief";
import {
  attentionItemFromOpportunity,
  evidenceInputsSentence,
  hasProvisionalOrder,
  OPPORTUNITY_STATE_LABEL,
  OPPORTUNITY_STATE_TONE,
  opportunityRankLabel,
} from "../opportunity/opportunityPresentation";
import { TradeReviewLearningPanel } from "../imp-product/TradeReviewLearningPanel";

export type OpportunityDetailCardProps = {
  row: OpportunityReviewRow;
  evidence?: OpportunityEvidenceResponse | null;
  evidencePhase?: "idle" | "loading" | "ready" | "error";
  paperAccountId?: string;
  paperActions?: boolean;
  readOnly?: boolean;
  feed?: OperatorBriefFeedContext | null;
  withheldRankedCount?: number;
  bookHonesty?: string;
  unreadyReason?: string;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

function MetaGrid({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <dl className="imp-radar-meta-grid">
      {items.map((item) => (
        <div key={`${item.label}:${item.value}`} className="imp-radar-meta-row">
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Disclosure({
  title,
  id,
  defaultOpen = false,
  children,
}: {
  title: string;
  id: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="imp-radar-disclosure" open={defaultOpen}>
      <summary id={id}>{title}</summary>
      <div className="imp-radar-disclosure-body" aria-labelledby={id}>
        {children}
      </div>
    </details>
  );
}

/**
 * Selected-opportunity detail with progressive disclosure:
 * L1 decision summary always visible; L2 evidence/verification, L3
 * historical/research context, and L4 technical detail behind disclosures.
 * Content derives from `buildOpportunityDetailSections` (backend fields
 * only — no invented truth).
 */
export function OpportunityDetailCard({
  row,
  evidence,
  evidencePhase = "idle",
  paperAccountId,
  paperActions = false,
  readOnly = false,
  feed = null,
  withheldRankedCount,
  bookHonesty,
  unreadyReason,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: OpportunityDetailCardProps) {
  const attention = attentionItemFromOpportunity(row);
  const model = buildOpportunityDetailSections(row, { evidence, paperActions, readOnly });
  const operatorBrief = buildOpportunityOperatorBrief(row, evidence, {
    paperActions,
    readOnly,
    feed,
    withheldRankedCount,
    bookHonesty,
    unreadyReason,
  });
  const epistemic = buildOpportunityEpistemicLayers(row, evidence);
  const decisionProvenance = buildDecisionProvenancePresentation(evidence, row);
  const epistemicLayerOrder: EpistemicLayerKey[] = [
    "observed",
    "derived",
    "model_research",
    "hypothesis",
    "unknown",
    "contradiction",
  ];
  const rank = opportunityRankLabel(row);
  const provisionalOrder = hasProvisionalOrder(row);
  const quality = row.data_quality ?? {};
  const linkageWarnings = readProviderLinkageWarnings(row);
  const nextAction = resolveSemanticState("research", model.actionReadiness.nextSafeAction);
  const eligibility = row.eligibility_state
    ? resolveSemanticState("research", row.eligibility_state)
    : null;
  const canOpen = model.actionReadiness.canPreviewWorkspace;

  return (
    <article
      className="imp-radar-detail-card"
      data-presentation={model.presentationState}
      data-stable-key={model.stableKey}
      data-testid="imp-radar-detail-card"
    >
      {/* L1 — decision summary */}
      <header className="imp-radar-detail-head">
        <div className="imp-radar-detail-state-row">
          <StatePill
            tone={OPPORTUNITY_STATE_TONE[model.presentationState]}
            label={OPPORTUNITY_STATE_LABEL[model.presentationState]}
            raw={model.presentationState}
          />
          {eligibility && row.eligibility_state !== "ELIGIBLE" ? (
            <StatePill tone={eligibility.tone} label={eligibility.label} raw={eligibility.raw} />
          ) : null}
          {row.identity_kind === "OPPORTUNITY_V1" ? (
            <StatePill tone="research" label="OpportunityV1" raw={row.identity_kind} size="sm" />
          ) : null}
        </div>
        <h3 className="imp-radar-detail-title">{row.headline}</h3>
        <p className="imp-radar-detail-identity">
          {row.instrument_id ? (
            <code>{row.instrument_id}</code>
          ) : (
            <span className="imp-radar-unavailable">Instrument unavailable</span>
          )}
          {rank ? ` · Rank ${rank}` : ""}
          {row.lifecycle_state ? ` · ${row.lifecycle_state.replace(/_/g, " ").toLowerCase()}` : ""}
        </p>
        <dl className="imp-radar-detail-summary">
          <div>
            <dt>Why it surfaced</dt>
            <dd>{model.surfacedWhy}</dd>
          </div>
          <div>
            <dt>Evidence</dt>
            <dd data-testid="imp-radar-detail-evidence">{evidenceInputsSentence(row)}</dd>
          </div>
          <div>
            <dt>Freshness</dt>
            <dd>
              <FreshnessIndicator backendLabel={opportunityFreshnessQueueLabel(row, evidence)} />
            </dd>
          </div>
          <div>
            <dt>Surfaced</dt>
            <dd>{model.ageLabel}</dd>
          </div>
          {linkageWarnings.length ? (
            <div data-testid="imp-radar-provider-linkage-warnings">
              <dt>Provider linkage</dt>
              <dd>{linkageWarnings.join(", ")}</dd>
            </div>
          ) : null}
        </dl>
      </header>

      <section
        className="imp-radar-operator-brief"
        aria-label="Operator questions"
        data-testid="imp-radar-operator-brief"
      >
        <h4 className="imp-radar-subhead">Operator questions</h4>
        <dl className="imp-radar-brief-grid">
          {operatorBrief.map((item) => (
            <div key={item.question} className="imp-radar-brief-row" data-honesty={item.honesty}>
              <dt>{item.question}</dt>
              <dd>
                {item.answer}
                <span className="imp-radar-brief-honesty">{item.honesty}</span>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {decisionProvenance.present ? (
        <section
          className="imp-radar-decision-provenance"
          aria-label="Decision provenance"
          data-testid="imp-radar-decision-provenance"
        >
          <h4 className="imp-radar-subhead">Decision provenance</h4>
          <p className="imp-radar-muted">
            Admitted-opportunity audit trail. Thesis language is derived or asserted — never an observed
            market fact.
          </p>
          <dl className="imp-radar-brief-grid">
            {decisionProvenance.fields.map((item) => (
              <div
                key={`${item.label}:${item.value}`}
                className="imp-radar-brief-row"
                data-honesty={item.honesty}
              >
                <dt>{item.label}</dt>
                <dd>
                  {item.value}
                  <span className="imp-radar-brief-honesty">{item.honesty}</span>
                </dd>
              </div>
            ))}
          </dl>
          <div
            className="imp-radar-ai-assisted-notes"
            data-testid="imp-radar-ai-assisted-notes"
            data-authority="non-authoritative"
          >
            <h5 className="imp-radar-subhead">AI-assisted notes (non-authoritative)</h5>
            <p className="imp-radar-muted">
              Visually separated from deterministic provenance. AI notes never authorize state changes
              or Live execution.
            </p>
            <ul className="imp-radar-lines">
              {decisionProvenance.aiAssistedNotes.map((note) => (
                <li key={`${note.label}:${note.value}`}>{note.value}</li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {hasNonFactualResearchOutput(epistemic) ? (
        <AttentionBanner tone="caution">
          Model and research outputs below are not grounded market facts. Treat agent enrichment and
          research artifacts as interpretive unless a grounded-fact disposition is present.
        </AttentionBanner>
      ) : null}
      {provisionalOrder ? (
        <AttentionBanner tone="caution">
          Provisional order — not FTEP-tuned or campaign-calibrated.
        </AttentionBanner>
      ) : null}
      {model.actionReadiness.blockedReason ? (
        <AttentionBanner tone="critical">
          {model.actionReadiness.blockedReason}. Do not act on this opportunity.
        </AttentionBanner>
      ) : null}

      <div className="imp-radar-detail-next">
        <span>
          Next safe action: <strong>{nextAction.label}</strong>
        </span>
        {paperAccountId ? (
          <p className="imp-radar-muted">
            Paper account <code>{paperAccountId}</code>
          </p>
        ) : null}
        <div className="imp-radar-detail-actions">
          {canOpen ? (
            <button type="button" onClick={() => onOpenWorkspace(attention)}>
              Open workspace
            </button>
          ) : null}
          <button type="button" onClick={() => onExplain(attention)}>
            Explain
          </button>
          <button type="button" onClick={() => onInspect(attention)}>
            Inspect
          </button>
          {paperAccountId && onAck && model.actionReadiness.canWatch ? (
            <>
              <button type="button" onClick={() => onAck(row, "watch")}>
                Watch
              </button>
              <button type="button" onClick={() => onAck(row, "review")}>
                Mark reviewed
              </button>
              <button type="button" onClick={() => onAck(row, "dismiss")}>
                Dismiss
              </button>
            </>
          ) : null}
          {readOnly ? <span className="imp-radar-muted">Read-only in this mode.</span> : null}
          {!paperActions && !readOnly ? (
            <span className="imp-radar-muted">Paper actions unavailable in this mode.</span>
          ) : null}
        </div>
        <p className="imp-radar-muted imp-radar-visibility-note">
          Visibility is not actionability. Presentation state does not grant execution authority.
        </p>
      </div>

      {/* L2 — epistemic layers */}
      <Disclosure title="Evidence layers" id={`${model.stableKey}-evidence`} defaultOpen>
        {evidencePhase === "loading" ? (
          <p className="imp-radar-muted" role="status">
            Loading evidence projection…
          </p>
        ) : null}
        {evidencePhase === "error" ? (
          <p className="imp-radar-unavailable" role="alert">
            Evidence projection unavailable.
          </p>
        ) : null}
        {epistemicLayerOrder.map((layerKey) => {
          const items = epistemic[layerKey];
          if (layerKey === "model_research" && !items.length) return null;
          if (layerKey === "hypothesis" && !items.length) return null;
          return (
            <section key={layerKey} className="imp-radar-epistemic-layer" data-layer={layerKey}>
              <h4 className="imp-radar-subhead">{epistemicLayerTitle(layerKey)}</h4>
              <MetaGrid
                items={items.map((item) => ({
                  label: item.label,
                  value: item.value,
                }))}
              />
              {layerKey === "model_research" ? (
                <p className="imp-radar-muted">Simulation, replay, and model outputs — not live facts.</p>
              ) : null}
            </section>
          );
        })}
      </Disclosure>

      {/* L2 — risk & liquidity */}
      <Disclosure title="Risk & liquidity" id={`${model.stableKey}-risk`}>
        <MetaGrid items={model.riskLiquidity} />
        {row.decision_support ? (
          <p className="imp-radar-muted">
            Risk overlay {row.decision_support.authority ?? "DOWNSTREAM_RISK_NOT_RANKING"} · kill
            switch {row.decision_support.kill_switch ?? "UNAVAILABLE"}
          </p>
        ) : null}
      </Disclosure>

      {/* L3 — historical & research context */}
      <Disclosure title="Historical & research context" id={`${model.stableKey}-historical`}>
        {model.historicalContext.status === "UNAVAILABLE" ? (
          <p className="imp-radar-unavailable">{model.historicalContext.lines[0]}</p>
        ) : (
          <ul className="imp-radar-lines">
            {model.historicalContext.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
        <p className="imp-radar-lines">
          <Link to="/research/evidence">Open Research evidence</Link> — interpretation-first view of
          the research behind attachments like these.
        </p>
        <TradeReviewLearningPanel row={row} />
      </Disclosure>

      {/* L4 — technical detail */}
      <Disclosure title="Technical details" id={`${model.stableKey}-technical`}>
        <JsonDetailPanel
          title="Ranking vector"
          value={row.ranking_vector ?? { unavailable: true }}
        />
        <JsonDetailPanel title="Data quality" value={quality} />
        <JsonDetailPanel
          title="Identifiers"
          value={{
            summary_id: row.summary_id,
            opportunity_id: row.opportunity_id ?? null,
            identity_kind: row.identity_kind ?? null,
            explanation_ref: row.explanation_ref ?? null,
            unavailable_fields: row.unavailable_fields ?? [],
          }}
        />
      </Disclosure>
    </article>
  );
}
