import type { ProviderConfig, ProviderField, ProviderSetup } from "../../../api/providerConfig";

/** Test fixture shaped like GET /operator/config (operator-config/1.1). Never contains a value. */
export function field(key: string, overrides: Partial<ProviderField> = {}): ProviderField {
  return { key, label: "API key", kind: "API_KEY", sensitive: true, required: true, configured: false, source: "NONE",
    editable: true, removable: false, help: null, example: null, hint: null, ...overrides };
}

export function providerEntry(provider: string, overrides: Partial<ProviderSetup> = {}): ProviderSetup {
  return { provider, label: provider, group: "NEWS", access: "FREE_ACCOUNT", about: `${provider} about`, unlocks: [`${provider} data`],
    configurable: true, external_setup: null, state: "NEEDS_SETUP", live_gates: [], applies: "NEXT_REQUEST", applies_note: null,
    verification: "ON_FIRST_USE", fields: [], ...overrides };
}

export const SEC_UNLOCKS = ["SEC filings in News", "SEC press releases", "13F institutional ownership",
  "Fail-to-deliver data (Short Squeeze)", "Automatic Senate eFD downloads (also needs the attested folder)"];

export function secEntry(configured = false): ProviderSetup {
  return providerEntry("sec", {
    label: "SEC EDGAR", group: "REGULATORY", access: "FREE", state: configured ? "CONFIGURED" : "NEEDS_SETUP",
    about: "The SEC's Fair Access policy requires every automated request to say who is asking and how to reach them.",
    unlocks: SEC_UNLOCKS,
    live_gates: [{ name: "IMP_EDGAR_LIVE", enabled: configured, source: configured ? "PRIVATE_FILE" : "NONE" },
      { name: "IMP_SEC_FTD_LIVE", enabled: configured, source: configured ? "PRIVATE_FILE" : "NONE" }],
    fields: [field("SEC_USER_AGENT", { label: "Contact identity", kind: "CONTACT_IDENTITY", sensitive: false,
      configured, source: configured ? "PRIVATE_FILE" : "NONE", removable: configured,
      help: "Your name or firm and a contact email.", example: "IMP Screener Jane Doe jane@example.com",
      hint: configured ? "contact at @acme-research.test" : null })],
  });
}

export function providerConfigPayload(overrides: { sec?: ProviderSetup; finnhub?: ProviderSetup } = {}): ProviderConfig {
  return {
    schema_version: "operator-config/1.1",
    secrets_included: false,
    providers: [
      overrides.sec ?? secEntry(),
      overrides.finnhub ?? providerEntry("finnhub", { label: "Finnhub", state: "CONFIGURED",
        live_gates: [{ name: "IMP_FINNHUB_LIVE", enabled: true, source: "PRIVATE_FILE" }],
        fields: [field("FINNHUB_API_KEY", { configured: true, source: "PRIVATE_FILE", removable: true })] }),
      providerEntry("finra", { label: "FINRA API", group: "MARKET_DATA", state: "PARTIAL", fields: [
        field("FINRA_CLIENT_ID", { label: "Client ID", kind: "CLIENT_ID", sensitive: false, configured: true, source: "ENVIRONMENT",
          editable: false }),
        field("FINRA_CLIENT_SECRET", { label: "Client secret", kind: "CLIENT_SECRET" })] }),
      providerEntry("finviz", { label: "Finviz Elite", group: "MARKET_DATA", access: "SUBSCRIPTION", applies: "RESTART",
        applies_note: "Finviz reads its token when the API starts.", fields: [field("FINVIZ_API_KEY", { label: "Elite API token", kind: "TOKEN" })] }),
      providerEntry("openai", { label: "OpenAI", group: "AI", access: "PAID_API", fields: [field("OPENAI_API_KEY")] }),
      providerEntry("opend", { label: "moomoo OpenD", group: "LOCAL", access: "FREE", configurable: false, state: "EXTERNAL",
        external_setup: "No API key. Start OpenD from the Setup checklist and log in inside OpenD." }),
    ],
  };
}
