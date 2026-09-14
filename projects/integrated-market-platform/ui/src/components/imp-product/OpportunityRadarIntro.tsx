import type { ReactNode } from "react";

type Props = {
  children?: ReactNode;
};

export function OpportunityRadarIntro({ children }: Props) {
  return (
    <p className="opportunity-radar-banner">
      <strong>Opportunity Radar</strong> — ranked discovery queue from admitted screeners.{" "}
      {children ?? "Paper and demo surfaces stay observational; live execution remains off."}
    </p>
  );
}
