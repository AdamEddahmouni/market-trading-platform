import type { AsOfContext, CapabilityState, OperatorDiagnostics } from "../../api/schemas";

import type { SemanticTone } from "../../state/semanticState";

import {

  diagnosticsGovernance,

  diagnosticsRuntimeSection,

  formatItem9CorpusProgress,

} from "../control/operatorDiagnosticsPresentation";



export type GovernanceFact = {

  id: string;

  label: string;

  value: string;

  tone: SemanticTone;

  raw?: string;

  detail?: string;

};



function display(value: unknown): string {

  if (value === null || value === undefined || value === "") return "UNAVAILABLE";

  return String(value);

}



function findCapability(

  capabilities: CapabilityState[] | undefined,

  pattern: RegExp,

): CapabilityState | undefined {

  return (capabilities ?? []).find((row) => pattern.test(row.capability_id));

}



/**

 * Operator governance facts from `GET /operator/diagnostics` when present.

 * Falls back to `/context` only for fields diagnostics does not own.

 */

export function buildGovernanceFacts(input: {

  asOf?: AsOfContext | null;

  capabilityStates?: CapabilityState[] | null;

  readinessRoot?: string | null;

  diagnostics?: OperatorDiagnostics | null;

}): GovernanceFact[] {

  const asOf = input.asOf;

  const capabilities = input.capabilityStates ?? [];

  const diagnostics = input.diagnostics;

  const runtime = diagnosticsRuntimeSection(diagnostics);

  const governance = diagnosticsGovernance(diagnostics);

  const corpus = formatItem9CorpusProgress(runtime?.item9_corpus_status);

  const resilienceReadiness = (

    (runtime?.runtime_resilience as Record<string, unknown> | undefined)?.readiness_vs_liveness as

      | Record<string, unknown>

      | undefined

  )?.readiness as Record<string, unknown> | undefined;



  const liveExecutionOff = governance

    ? !governance.live_execution_env

    : asOf?.execution_authority !== "AUTHORIZED" || asOf?.execution_mode !== "LIVE";



  const facts: GovernanceFact[] = [

    {

      id: "live-execution",

      label: "Live real-money execution",

      value: liveExecutionOff ? "Live OFF" : "Authorized path only",

      tone: liveExecutionOff ? "neutral" : "critical",

      raw: liveExecutionOff ? "OFF" : asOf?.execution_authority,

      detail: liveExecutionOff

        ? "LIVE-001 remains blocked; observational Live does not place broker orders."

        : "Execution authority reports AUTHORIZED — still subject to platform gates.",

    },

    {

      id: "runtime-sha",

      label: "Runtime git SHA",

      value: runtime?.git_sha ? display(runtime.git_sha) : "UNAVAILABLE",

      tone: runtime?.git_sha ? "neutral" : "neutral",

      detail: runtime?.git_sha

        ? "From GET /operator/diagnostics runtime section (API checkout SHA)."

        : "Diagnostics did not include runtime SHA.",

    },

    {

      id: "item9-rth-dates",

      label: "Distinct admitted RTH dates",

      value: corpus.distinctRthDates,

      tone: corpus.distinctRthDates === "NOT_OBSERVED" ? "neutral" : "caution",

      detail: corpus.receiptScopeNote,

    },

    {

      id: "item9-calibration",

      label: "Item 9 calibration",

      value: corpus.calibrationLabel,

      tone: /CALIBRATED/i.test(corpus.calibrationLabel) && !/NOT/i.test(corpus.calibrationLabel)

        ? "live"

        : "caution",

      raw: String(resilienceReadiness?.item9_status ?? corpus.calibrationLabel),

      detail: corpus.calibrationForbidden,

    },

  ];



  const item9Cap = findCapability(capabilities, /item9|calibration|prospective/i);

  if (item9Cap && !diagnostics) {

    const calibrated = /CALIBRATED/i.test(item9Cap.state) && !/NOT_CALIBRATED/i.test(item9Cap.state);

    const existing = facts.find((row) => row.id === "item9-calibration");

    if (existing) {

      existing.value = calibrated ? display(item9Cap.state) : display(item9Cap.state);

      existing.raw = item9Cap.state;

      existing.detail = item9Cap.reason ?? "Capability state from backend context.";

    }

  }



  const collectorCap = findCapability(capabilities, /collector|frozen/i);

  if (collectorCap) {

    facts.push({

      id: "collector-state",

      label: "Prospective collector",

      value: display(collectorCap.state),

      tone: /READY|CONNECTED/i.test(collectorCap.state) ? "live" : "caution",

      raw: collectorCap.state,

      detail: collectorCap.reason,

    });

  } else if (diagnostics) {

    const collector = (

      (runtime?.runtime_resilience as Record<string, unknown> | undefined)?.collector_process as

        | Record<string, unknown>

        | undefined

    );

    const detected = collector?.active_collector_detected === true;

    facts.push({

      id: "collector-state",

      label: "Prospective collector",

      value: detected ? "ACTIVE (process detected)" : "IDLE / NOT_OBSERVED",

      tone: detected ? "live" : "neutral",

      raw: detected ? "ACTIVE" : "NOT_OBSERVED",

      detail: "Summarized process probe from diagnostics — no raw command lines.",

    });

  }



  if (input.readinessRoot) {

    facts.push({

      id: "readiness-root",

      label: "Readiness scan root",

      value: input.readinessRoot,

      tone: "neutral",

      detail: "Local workstation path from operator readiness (not empirical receipt SHA).",

    });

  }



  return facts;

}

