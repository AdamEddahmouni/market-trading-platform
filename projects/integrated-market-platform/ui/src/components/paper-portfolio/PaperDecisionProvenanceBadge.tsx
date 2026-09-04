import type { PaperOperationalProvenance } from "./paperDecisionProvenance";

type Props = {
  provenance: PaperOperationalProvenance;
};

export function PaperDecisionProvenanceBadge({ provenance }: Props) {
  const category = provenance.sourceCategory.toLowerCase().replace(/_/g, "-");
  return (
    <span className={`paper-provenance-badge paper-provenance-badge--${category}`}>
      {provenance.badgeLabel}
    </span>
  );
}
