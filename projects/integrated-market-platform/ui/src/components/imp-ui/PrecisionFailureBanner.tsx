import type { ReactNode } from "react";
import type { KnownDataIncident } from "../operator-shared/knownDataIncidents";
import { AttentionBanner } from "./AttentionBanner";

type PrecisionFailureBannerProps = {
  incident: KnownDataIncident;
  children?: ReactNode;
};

/**
 * Precise treatment for known evidence gaps — distinct from generic STALE_DATA
 * or provider outage banners.
 */
export function PrecisionFailureBanner({ incident, children }: PrecisionFailureBannerProps) {
  return (
    <AttentionBanner tone={incident.tone} affects={incident.guidance}>
      <strong>{incident.title}</strong>
      <p className="imp-precision-failure-detail">{incident.detail}</p>
      {children}
    </AttentionBanner>
  );
}
