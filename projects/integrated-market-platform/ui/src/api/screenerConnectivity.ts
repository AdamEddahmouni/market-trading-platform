import { DecisionEvidenceSchema, DecisionInputs } from "./decisionFreshness";
import { z } from "zod";
import { fetchJson } from "./fetchJson";
import type { ScreenerUniverse } from "./screener";

const Node = z.object({
  decision_evidence: DecisionEvidenceSchema.optional(),
  node_id: z.string(), canonical_instrument_id: z.string().nullable(), label: z.string(),
  domain: z.string(), asset_class: z.string(), instrument_kind: z.string(), state: z.string(),
  source: z.string().nullable(), as_of: z.string().nullable(), received_at: z.string().nullable(),
  facts: z.record(z.unknown()), executable: z.literal(false), role: z.string(),
});
export const ConnectivitySchema = z.object({
  decision_inputs: DecisionInputs,
  schema_version: z.literal("screener-connectivity/1.0.0"), instrument_id: z.string(), universe: z.string(),
  selected_instrument: Node, nodes: z.array(Node).max(20),
  edges: z.array(z.object({ edge_id: z.string(), from_node: z.string(), to_node: z.string(),
    relationship_type: z.string(), relationship_class: z.enum(["STRUCTURAL", "REFERENCE", "CONTEXTUAL_MAPPING", "DERIVED_COMPARISON"]),
    basis: z.string(), definition_version: z.string().nullable(),
    evidence_state: z.enum(["CONFIRMING", "CONFLICTING", "CONTEXT_ONLY", "UNKNOWN", "UNAVAILABLE"]),
    explanation: z.string(), provenance: z.record(z.unknown()) })).max(24),
  completeness: z.object({ requested_domains: z.array(z.string()), domains: z.record(z.object({
    state: z.string(), reason: z.string().nullable(), missing_references: z.array(z.string()).optional(),
    catalog_unavailable: z.boolean().optional() })) }),
  generated_at: z.string(), causal_note: z.string(),
}).superRefine((data, ctx) => {
  const ids = new Set(data.nodes.map(n => n.node_id));
  if (ids.size !== data.nodes.length || !ids.has(data.selected_instrument.node_id) ||
    data.edges.some(e => !ids.has(e.from_node) || !ids.has(e.to_node))) {
    ctx.addIssue({ code: "custom", message: "CONNECTIVITY_GRAPH_INVALID" });
  }
});
export type ConnectivityPayload = z.infer<typeof ConnectivitySchema>;
export async function fetchConnectivity(instrument: string, universe: ScreenerUniverse, signal?: AbortSignal) {
  const payload = await fetchJson(`/screener/connectivity?${new URLSearchParams({ instrument, universe })}`, ConnectivitySchema, { signal });
  if (payload.instrument_id !== instrument || payload.universe !== universe) throw new Error("CONNECTIVITY_IDENTITY_MISMATCH");
  return payload;
}
