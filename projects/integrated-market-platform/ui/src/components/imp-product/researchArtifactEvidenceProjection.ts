import type { OpportunityEvidenceResponse } from "../../api/opportunityClient";

export type ResearchArtifactEvidenceBlock = {
  authority_class?: string;
  readiness?: string;
  attachments?: Array<Record<string, unknown>>;
};

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : undefined;
}

function projectEdgeStatsLines(ctx: Record<string, unknown>): string[] {
  const lines: string[] = [];
  lines.push(
    `[Edge Stats evidence] ${displayValue(ctx.artifact_type)} · sample N ${displayValue(ctx.sample_n)} · estimate ${displayValue(ctx.estimate)}`,
  );
  const ci = asRecord(ctx.confidence_interval);
  if (ci) {
    lines.push(
      `CI [${displayValue(ci.ci_lower)}, ${displayValue(ci.ci_upper)}] · status ${displayValue(ci.status)}`,
    );
  }
  const stability = asRecord(ctx.stability_status);
  if (stability) {
    lines.push(`Stability ${displayValue(stability.status)} · divergence ${displayValue(stability.relative_divergence)}`);
  }
  return lines;
}

function projectPrintQuoteAge(quoteAge: Record<string, unknown> | undefined): string {
  if (!quoteAge) return "quote age UNAVAILABLE";
  if (quoteAge.available === false) {
    return `quote age UNAVAILABLE (${displayValue(quoteAge.reason)})`;
  }
  return `quote age ${displayValue(quoteAge.quote_age_ms)} ms · ${displayValue(quoteAge.staleness)}`;
}

function projectPrintAggressor(aggressor: Record<string, unknown> | undefined): string {
  if (!aggressor) return "aggressor confidence UNAVAILABLE";
  if (aggressor.available === false) return "aggressor confidence UNAVAILABLE";
  return `aggressor ${displayValue(aggressor.band)} (${displayValue(aggressor.confidence)})`;
}

function projectPrintSourceQuality(signedFlow: Record<string, unknown> | undefined): string {
  if (!signedFlow) return "signed flow UNAVAILABLE";
  const flags = signedFlow.quality_flags;
  const flagText = Array.isArray(flags) && flags.length ? flags.join(", ") : "none";
  return `flow ${displayValue(signedFlow.direction)} · ${displayValue(signedFlow.open_close)} · quality flags ${flagText}`;
}

function projectOptionsFlowLines(ctx: Record<string, unknown>): string[] {
  const lines: string[] = [];
  lines.push(
    `[Options flow replay] ${displayValue(ctx.artifact_type)} · replay ${displayValue(ctx.replay_mode)} · live feed ${displayValue(ctx.live_feed_claim)}`,
  );
  lines.push(
    `Prints ${displayValue(ctx.print_count)} · classes ${JSON.stringify(ctx.trade_class_counts ?? {})}`,
  );
  const missingUnion = ctx.missing_data_fields_union;
  if (Array.isArray(missingUnion) && missingUnion.length) {
    lines.push(`Missing-data union: ${missingUnion.join(", ")}`);
  } else {
    lines.push("Missing-data union: none reported");
  }
  const exclusions = ctx.explicit_exclusions;
  if (Array.isArray(exclusions) && exclusions.length) {
    lines.push(`Excluded vendor scores: ${exclusions.join(", ")}`);
  }
  const prints = ctx.decomposed_prints;
  if (Array.isArray(prints)) {
    for (const row of prints) {
      const print = asRecord(row);
      if (!print) continue;
      const trade = asRecord(print.trade_classification);
      const quoteAge = asRecord(print.quote_age);
      const aggressor = asRecord(print.aggressor_confidence);
      const signedFlow = asRecord(print.signed_flow);
      const missingFields = print.missing_data_fields;
      const missingText =
        Array.isArray(missingFields) && missingFields.length ? missingFields.join(", ") : "none";
      lines.push(
        `Print ${displayValue(print.print_index)}: ${displayValue(trade?.trade_class)} ${displayValue(print.option_type)} ${displayValue(print.strike)}/${displayValue(print.expiry)} · ${projectPrintQuoteAge(quoteAge)} · ${projectPrintAggressor(aggressor)} · ${projectPrintSourceQuality(signedFlow)} · missing ${missingText}`,
      );
    }
  }
  return lines;
}

export function researchArtifactEvidenceFromEvidence(
  evidence?: OpportunityEvidenceResponse | null,
): ResearchArtifactEvidenceBlock | undefined {
  const block = evidence?.research_artifact_evidence;
  if (!block || typeof block !== "object") return undefined;
  return block as ResearchArtifactEvidenceBlock;
}

export function projectResearchArtifactEvidenceLines(
  block: ResearchArtifactEvidenceBlock | null | undefined,
): string[] {
  if (!block) return [];
  const lines: string[] = [];
  lines.push(
    `Research artifact evidence · authority ${displayValue(block.authority_class)} (EVIDENCE_NOT_PREDICTION — not rank / not execution)`,
  );
  if (block.readiness) {
    lines.push(`Readiness ${displayValue(block.readiness)}`);
  }
  const attachments = block.attachments ?? [];
  if (!attachments.length) {
    lines.push("No research artifact attachments on this opportunity yet (cold start).");
    return lines;
  }
  for (const attachment of attachments) {
    const att = asRecord(attachment);
    if (!att) continue;
    if (att.status === "UNRESOLVED") {
      lines.push(
        `Attachment ${displayValue(att.attachment_id)}: UNRESOLVED catalog lookup (fixture/replay only; not live feed)`,
      );
      continue;
    }
    const edge = asRecord(att.historical_statistical_context);
    if (edge) lines.push(...projectEdgeStatsLines(edge));
    const options = asRecord(att.options_flow_transparent_context);
    if (options) lines.push(...projectOptionsFlowLines(options));
    if (!edge && !options) {
      lines.push(
        `Attachment ${displayValue(att.attachment_id)}: resolved opaque artifact ${displayValue(att.artifact_type)}`,
      );
    }
  }
  return lines;
}
