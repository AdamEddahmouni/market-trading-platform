import { Link } from "react-router-dom";
import type { Mode } from "../mode-session/types";
import type { WorkspaceLaneModuleId } from "./laneRegistry";
import { createLanePaperOrderDraft, LANE_DRAFT_PLACEHOLDER_NOTE } from "../paper-now/paperOrderDraft";
import type { LaneModeContent, LaneQueryState } from "./laneModeContentTypes";
import { laneProvenanceSummary } from "./laneProvenance";
import { modeSpecificEmptyMessage } from "./laneQueryState";

type Props = {
  mode: Mode;
  moduleId: WorkspaceLaneModuleId;
  instrumentId: string;
  queryState: LaneQueryState;
  content: LaneModeContent;
};

function modePanelClass(mode: Mode): string {
  if (mode === "DEMO") return "lane-mode-panel demo-lane-mode-panel";
  if (mode === "PAPER") return "lane-mode-panel paper-lane-mode-panel";
  return "lane-mode-panel live-lane-mode-panel";
}

function decisionHintLabel(hint: NonNullable<LaneModeContent["decisionHint"]>): string {
  if (hint === "supports") return "Leans supportive";
  if (hint === "contradicts") return "Leans contradictory";
  if (hint === "insufficient") return "Insufficient evidence";
  return "Mixed / confirm manually";
}

export function LaneModeContextPanel({ mode, moduleId, instrumentId, queryState, content }: Props) {
  const showEmptyNote =
    queryState.phase === "empty" ||
    queryState.phase === "error" ||
    (queryState.phase === "ready" && queryState.degraded);
  const emptyMessage = modeSpecificEmptyMessage(mode, queryState.phase);
  const provenanceSummary = laneProvenanceSummary(queryState.provenance);

  return (
    <section
      className={modePanelClass(mode)}
      aria-labelledby={`lane-mode-${moduleId}-headline`}
      data-mode={mode}
      data-module={moduleId}
    >
      <header className="lane-mode-panel-header">
        <span className="lane-mode-eyebrow">
          {mode === "DEMO" ? "Demo lane context" : mode === "PAPER" ? "Paper lane context" : "Live lane context"}
        </span>
        <h2 id={`lane-mode-${moduleId}-headline`}>{content.headline}</h2>
        <p className="lane-mode-summary">{content.summary}</p>
        {provenanceSummary ? (
          <p className="lane-mode-provenance" role="status">
            {provenanceSummary}
          </p>
        ) : null}
        {content.decisionHint && mode === "PAPER" ? (
          <p className={`lane-decision-hint lane-decision-hint-${content.decisionHint}`} role="status">
            Simulation hint: {decisionHintLabel(content.decisionHint)}
          </p>
        ) : null}
      </header>

      {showEmptyNote && emptyMessage ? (
        <p className="lane-mode-empty-note">{emptyMessage}</p>
      ) : null}

      {queryState.stale ? (
        <p className="lane-mode-stale-note">
          Evidence may be stale — {mode === "LIVE" ? "verify provider freshness before relying on this lane." : "re-fetch before drafting."}
        </p>
      ) : null}

      {content.sections.map((section) => (
        <article key={section.title} className={`lane-mode-section emphasis-${section.emphasis ?? "neutral"}`}>
          <h3>{section.title}</h3>
          <p>{section.body}</p>
          {section.bullets && section.bullets.length > 0 ? (
            <ul>
              {section.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          ) : null}
        </article>
      ))}

      {content.limitations && content.limitations.length > 0 ? (
        <aside className="lane-mode-limitations">
          <strong>Limitations</strong>
          <ul>
            {content.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </aside>
      ) : null}

      {content.relatedLinks && content.relatedLinks.length > 0 ? (
        <nav className="lane-mode-related" aria-label={`Related links for ${instrumentId} ${moduleId}`}>
          {content.relatedLinks.map((link) => (
            <Link key={link.to} to={link.to}>
              {link.label}
            </Link>
          ))}
        </nav>
      ) : null}

      {mode === "PAPER" && queryState.phase !== "error" ? (
        <div className="lane-mode-paper-draft">
          <Link
            to={`/workspace/${instrumentId}`}
            state={createLanePaperOrderDraft(instrumentId, moduleId, {
              lanePayload: queryState.provenance ? { lane_provenance: queryState.provenance } : undefined,
            })}
            aria-describedby={`lane-draft-note-${moduleId}`}
          >
            Draft paper order from lane
          </Link>
          <p id={`lane-draft-note-${moduleId}`} className="lane-draft-placeholder-note" role="note">
            {LANE_DRAFT_PLACEHOLDER_NOTE} Provenance: lane:{moduleId}.
            {queryState.provenance?.source_kind === "unknown"
              ? " Lane source time unavailable — handoff time used at navigation."
              : null}
          </p>
        </div>
      ) : null}
    </section>
  );
}
