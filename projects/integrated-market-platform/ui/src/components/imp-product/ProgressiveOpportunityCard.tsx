import type { ReactNode } from "react";
import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityEvidenceResponse, OpportunityReviewRow } from "../../api/opportunityClient";
import { attentionItemFromOpportunity } from "../now/OpportunityReviewCard";
import { opportunityRankLabel } from "./impOpportunityDisplay";
import {
  buildProgressiveOpportunitySections,
  type ProgressivePresentationState,
} from "./progressiveOpportunityModel";
import { TradeReviewLearningPanel } from "./TradeReviewLearningPanel";

const STATE_LABEL: Record<ProgressivePresentationState, string> = {
  DETECTED: "Detected",
  PROVISIONAL: "Provisional",
  VERIFYING: "Verifying",
  VERIFIED: "Verified",
  CONTRADICTED: "Contradicted",
  EXPIRED: "Expired",
};

export type ProgressiveOpportunityCardProps = {
  row: OpportunityReviewRow;
  evidence?: OpportunityEvidenceResponse | null;
  evidencePhase?: "idle" | "loading" | "ready" | "error";
  paperAccountId?: string;
  paperActions?: boolean;
  readOnly?: boolean;
  density?: "cockpit" | "review";
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

function MetaGrid({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <dl className="progressive-opp-meta-grid">
      {items.map((item) => (
        <div key={item.label} className="progressive-opp-meta-row">
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Section({
  title,
  children,
  id,
}: {
  title: string;
  id: string;
  children: ReactNode;
}) {
  return (
    <section className="progressive-opp-section" aria-labelledby={id}>
      <h4 id={id}>{title}</h4>
      {children}
    </section>
  );
}

export function ProgressiveOpportunityCard({
  row,
  evidence,
  evidencePhase = "idle",
  paperAccountId,
  paperActions = false,
  readOnly = false,
  density = "cockpit",
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: ProgressiveOpportunityCardProps) {
  const attention = attentionItemFromOpportunity(row);
  const model = buildProgressiveOpportunitySections(row, { evidence, paperActions, readOnly });
  const rank = opportunityRankLabel(row);
  const basis = row.ranking_vector?.basis;
  const provisionalBanner = Boolean(basis && basis !== "COMPARATOR_LEXICOGRAPHIC");
  const dimensions = row.ranking_vector?.dimensions ?? [];
  const quality = row.data_quality ?? {};
  const qualityStatus = quality.status == null || quality.status === "" ? "UNAVAILABLE" : String(quality.status);
  const overlay = row.decision_support;
  const canOpen = model.actionReadiness.canPreviewWorkspace;

  return (
    <article
      className={`progressive-opportunity-card progressive-opportunity-card--${density}`}
      data-presentation={model.presentationState}
      data-stable-key={model.stableKey}
      data-identity={row.identity_kind ?? "NOT_OPPORTUNITY_V1"}
    >
      <header className="progressive-opp-head">
        <div>
          <span className="progressive-opp-state" data-state={model.presentationState}>
            {STATE_LABEL[model.presentationState]}
          </span>
          <h3>{row.headline}</h3>
          <p className="progressive-opp-identity">
            {row.identity_kind === "OPPORTUNITY_V1" ? "OpportunityV1" : "not OpportunityV1"}
            {rank ? ` · ${rank}` : ""}
            {row.lifecycle_state ? ` · ${row.lifecycle_state}` : ""}
          </p>
        </div>
        <div className="progressive-opp-instrument">
          {row.instrument_id ? <code>{row.instrument_id}</code> : <span className="unavailable">Instrument UNAVAILABLE</span>}
        </div>
      </header>

      <dl className="progressive-opp-surface-meta">
        <div><dt>Entity</dt><dd>{model.entityLabel}</dd></div>
        <div><dt>Event</dt><dd>{model.eventType}</dd></div>
        <div><dt>Age (decision time)</dt><dd>{model.ageLabel}</dd></div>
        <div><dt>Freshness</dt><dd>{model.freshnessLabel}</dd></div>
        <div><dt>Expiry</dt><dd>{model.expiryLabel}</dd></div>
        <div><dt>Urgency / rank</dt><dd>{model.urgencyLabel}</dd></div>
        <div className="progressive-opp-surface-why"><dt>Why surfaced</dt><dd>{model.surfacedWhy}</dd></div>
      </dl>

      {provisionalBanner ? (
        <p className="opportunity-provisional">Provisional order — not FTEP-tuned / not campaign-calibrated</p>
      ) : null}

      {density === "review" ? (
        <>
          <ul className="reason-codes">
            {dimensions.map((dimension) => (
              <li key={dimension.name}>
                <code>{dimension.name}</code>{" "}
                {dimension.status === "PRESENT" ? String(dimension.value ?? "UNAVAILABLE") : "UNAVAILABLE"}
                {dimension.unit && dimension.status === "PRESENT" ? ` ${dimension.unit}` : ""}
                {dimension.reason_code ? ` (${dimension.reason_code})` : ""}
              </li>
            ))}
          </ul>
          <p className="opportunity-quality">
            Data quality {qualityStatus}
            {quality.freshness ? ` · freshness ${String(quality.freshness)}` : ""}
          </p>
        </>
      ) : null}

      <Section title="Deterministic evidence" id={`${model.stableKey}-evidence`}>
        <MetaGrid items={model.deterministicEvidence} />
        {evidencePhase === "loading" ? <p className="muted" role="status">Loading evidence projection…</p> : null}
        {evidencePhase === "error" ? <p className="unavailable" role="alert">Evidence projection unavailable.</p> : null}
      </Section>

      <Section title="Verification" id={`${model.stableKey}-verification`}>
        <MetaGrid items={model.verification} />
      </Section>

      <Section title="Contradictions" id={`${model.stableKey}-contradictions`}>
        <MetaGrid items={model.contradictions} />
      </Section>

      <Section title="Historical context" id={`${model.stableKey}-historical`}>
        {model.historicalContext.status === "UNAVAILABLE" ? (
          <p className="unavailable">{model.historicalContext.lines[0]}</p>
        ) : (
          <ul className="progressive-opp-lines">
            {model.historicalContext.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Risk / liquidity" id={`${model.stableKey}-risk`}>
        <MetaGrid items={model.riskLiquidity} />
        {overlay ? (
          <p className="opportunity-decision-support">
            Risk overlay {overlay.authority ?? "DOWNSTREAM_RISK_NOT_RANKING"} · kill switch{" "}
            {overlay.kill_switch ?? "UNAVAILABLE"}
          </p>
        ) : null}
      </Section>

      <Section title="Trade review" id={`${model.stableKey}-trade-review`}>
        <TradeReviewLearningPanel row={row} />
      </Section>

      <Section title="Action readiness" id={`${model.stableKey}-actions`}>
        <p className="opportunity-next">
          Next safe action: {model.actionReadiness.nextSafeAction}
          {model.actionReadiness.blockedReason ? ` (${model.actionReadiness.blockedReason})` : ""}
        </p>
        {paperAccountId ? (
          <p className="opportunity-account">
            Paper account <code>{paperAccountId}</code>
          </p>
        ) : null}
        <p className="muted progressive-opp-visibility-note">
          Visibility ≠ actionability. Presentation state does not grant execution authority.
        </p>
        <div className="card-actions progressive-opp-actions">
          <button type="button" onClick={() => onExplain(attention)}>Explain</button>
          <button type="button" onClick={() => onInspect(attention)}>Inspect</button>
          {canOpen ? (
            <button type="button" onClick={() => onOpenWorkspace(attention)}>
              {density === "review" ? "Open workspace" : "Preview workspace"}
            </button>
          ) : null}
          {model.actionReadiness.canRevalidate && canOpen ? (
            <button type="button" onClick={() => onOpenWorkspace(attention)}>Revalidate in workspace</button>
          ) : null}
          {paperAccountId && onAck && model.actionReadiness.canWatch ? (
            <>
              <button type="button" onClick={() => onAck(row, "review")}>Mark reviewed</button>
              <button type="button" onClick={() => onAck(row, "watch")}>Watch</button>
              <button type="button" onClick={() => onAck(row, "dismiss")}>Dismiss</button>
            </>
          ) : null}
          {readOnly ? <span className="muted">Demo is read-only.</span> : null}
          {!paperActions && !readOnly ? (
            <span className="muted">Paper actions unavailable in this mode.</span>
          ) : null}
        </div>
      </Section>
    </article>
  );
}
