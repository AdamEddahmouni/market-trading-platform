import { z } from 'zod';
export const DecisionEvidenceSchema = z.object({
  capability: z.string(), source: z.string().nullable(), delivery_mode: z.string(),
  freshness_status: z.string(), decision_admissibility: z.string(),
  eligible_for_current_decision: z.boolean(), eligible_for_reference: z.boolean(),
  basis: z.string(), as_of: z.string().nullable(), received_at: z.string().nullable(), fetched_at: z.string().nullable(),
  age_ms: z.number().nullable(), stale_after_ms: z.number().nullable(),
  policy: z.string(), policy_version: z.string(), evaluated_at: z.string(), valid_until: z.string().nullable(),
  reason_codes: z.array(z.string()),
}).passthrough();
export const DecisionInputs = z.array(DecisionEvidenceSchema).optional();
export type DecisionEvidence = z.infer<typeof DecisionEvidenceSchema>;
