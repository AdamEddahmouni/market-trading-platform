import type { SemanticTone } from "../../state/semanticState";

export type KnownDataIncident = {
  id: string;
  matchTokens: string[];
  tone: SemanticTone;
  title: string;
  detail: string;
  /** Operator-facing guidance — not a remediation command. */
  guidance: string;
};

/**
 * Frozen observational gaps and outages the UI must not backfill or treat as
 * transient provider failures. Match tokens are compared case-insensitively
 * against backend reason codes, attention codes, and feed unready reasons.
 */
export const KNOWN_DATA_INCIDENTS: ReadonlyArray<KnownDataIncident> = [
  {
    id: "EPOCH_121031",
    matchTokens: ["121031", "epoch_121031", "epoch-121031", "EPOCH_121031"],
    tone: "caution",
    title: "Known observational gap (epoch 121031)",
    detail:
      "Bar coverage for this epoch was never backfilled. Replay and lane charts may show a persistent hole.",
    guidance:
      "Treat as an evidence limitation, not a live provider outage. Do not expect automatic repair or historical backfill from the UI.",
  },
];

export function matchKnownDataIncident(haystack: string | null | undefined): KnownDataIncident | null {
  if (!haystack || !haystack.trim()) return null;
  const normalized = haystack.toLowerCase();
  for (const incident of KNOWN_DATA_INCIDENTS) {
    if (incident.matchTokens.some((token) => normalized.includes(token.toLowerCase()))) {
      return incident;
    }
  }
  return null;
}
