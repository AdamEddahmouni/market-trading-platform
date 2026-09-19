import { Link } from "react-router-dom";
import { StatePill } from "../imp-ui/StatePill";
import {
  claimFollowAccessibleName,
  type ClaimHop,
  type ClaimPathRelation,
  type ResearchClaimNode,
  type ResearchClaimNodeKey,
} from "./researchPresentation";

type GraphNode = ResearchClaimNode & { relation?: ClaimPathRelation };

type GraphProps = {
  nodes: ReadonlyArray<GraphNode>;
  activeKey?: ResearchClaimNodeKey;
};

/**
 * Overview claim graph: eight operator hops with payload status or an honest
 * gap. Links navigate; gap nodes stay visible without inventing objects.
 * Finding-scoped lineage marks off-path nodes without hiding them.
 */
export function ResearchClaimGraph({ nodes, activeKey }: GraphProps) {
  return (
    <nav className="research-claim-graph" aria-label="Claim navigation">
      <ol className="research-claim-graph-list">
        {nodes.map((node) => {
          const body = (
            <>
              <div className="research-claim-graph-meta">
                <span className="research-claim-graph-title">{node.title}</span>
                <StatePill tone={node.statusTone} label={node.statusLabel} size="sm" />
              </div>
              <p className="research-claim-graph-role">{node.role}</p>
              <p className="research-muted">{node.detail}</p>
              <p className="research-evidence-class">{node.evidenceClass}</p>
            </>
          );
          return (
            <li
              key={node.key}
              className="research-claim-graph-item"
              data-kind={node.destinationKind}
              data-relation={node.relation}
              data-active={activeKey === node.key ? "true" : undefined}
            >
              {node.href ? (
                <Link
                  to={node.href}
                  className="research-claim-graph-link"
                  aria-current={activeKey === node.key ? "page" : undefined}
                >
                  {body}
                </Link>
              ) : (
                <div className="research-claim-graph-link research-claim-graph-link--static">{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

type HopProps = {
  hops: ReadonlyArray<ClaimHop>;
  label?: string;
};

/** Compact follow-this-claim hops for section pages (no extra fetches). */
export function ResearchClaimHops({ hops, label = "Follow this claim" }: HopProps) {
  return (
    <nav className="research-claim-hops" aria-label={label}>
      <p className="research-panel-kicker">{label}</p>
      <ul>
        {hops.map((hop) => (
          <li key={hop.key}>
            {hop.href ? (
              <Link to={hop.href} aria-label={claimFollowAccessibleName(hop.title)}>
                {hop.title}
              </Link>
            ) : (
              <span>{hop.title}</span>
            )}
            <span className="research-muted"> — {hop.note}</span>
          </li>
        ))}
      </ul>
    </nav>
  );
}
