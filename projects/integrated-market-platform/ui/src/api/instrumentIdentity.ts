/** Canonical instrument route/query serialization helpers. */

export function encodeInstrumentRouteParam(canonicalId: string): string {
  const text = canonicalId.trim();
  if (!text) return "";
  return encodeURIComponent(text);
}

export function decodeInstrumentRouteParam(routeParam: string): string {
  const text = routeParam.trim();
  if (!text) return "";
  return decodeURIComponent(text);
}

export function workspacePathForInstrument(canonicalId: string, suffix = ""): string {
  const encoded = encodeInstrumentRouteParam(canonicalId);
  return suffix ? `/workspace/${encoded}/${suffix}` : `/workspace/${encoded}`;
}

export type InstrumentSelectionAction =
  | "OPEN_EQUITY_WORKSPACE"
  | "OPEN_OPTIONS_WORKSPACE"
  | "OPEN_FUTURES_WORKSPACE"
  | "OPEN_FUTURE_FAMILY_REFERENCE"
  | "OPEN_CONTINUOUS_REFERENCE"
  | "OPEN_CRYPTO_REFERENCE"
  | "OPEN_OPTION_CHAIN"
  | "REFERENCE_ONLY"
  | "UNSUPPORTED_INSTRUMENT"
  | "OPEN_WORKSPACE";

export type CanonicalSelectorResult = {
  instrument_id: string;
  asset_class: string;
  instrument_kind: string;
  display_label: string;
  tradability: string;
  execution_eligible: boolean;
  selection_action: InstrumentSelectionAction;
  provider_availability: string;
  metadata: Record<string, string | null | undefined>;
};

export function selectionWorkspaceSuffix(result: CanonicalSelectorResult): string | null {
  switch (result.selection_action) {
    case "OPEN_OPTIONS_WORKSPACE":
      return "options";
    case "OPEN_FUTURES_WORKSPACE":
      return "futures";
    case "OPEN_EQUITY_WORKSPACE":
    case "OPEN_WORKSPACE":
      return "";
    default:
      return null;
  }
}

export function selectionDisabledReason(result: CanonicalSelectorResult): string | null {
  if (result.execution_eligible) return null;
  if (result.selection_action === "OPEN_FUTURE_FAMILY_REFERENCE") {
    return "Future family is reference-only — select a specific contract to trade.";
  }
  if (result.selection_action === "OPEN_CONTINUOUS_REFERENCE") {
    return "Continuous series is reference-only — not executable.";
  }
  if (result.selection_action === "REFERENCE_ONLY") {
    return "Reference-only identity — no execution surface.";
  }
  if (result.instrument_kind === "TRADABLE_SECURITY" && result.selection_action !== "OPEN_EQUITY_WORKSPACE") {
    return "Option underlying opens discovery — select a specific contract to trade.";
  }
  return "Unsupported instrument for execution.";
}
