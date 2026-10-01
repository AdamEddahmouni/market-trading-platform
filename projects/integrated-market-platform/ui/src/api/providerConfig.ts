import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";

/**
 * Provider setup: the value-blind status of every registered provider setting and the one write
 * route that stores them. Responses never carry a secret; a secret travels only in the body of an
 * explicit save and is never kept in a query cache, storage, or the URL.
 */
const FieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  kind: z.string(),
  sensitive: z.boolean(),
  required: z.boolean(),
  configured: z.boolean(),
  source: z.enum(["ENVIRONMENT", "PRIVATE_FILE", "ENV_FILE", "NONE"]),
  editable: z.boolean(),
  removable: z.boolean(),
  help: z.string().nullable(),
  example: z.string().nullable(),
  hint: z.string().nullable(),
}).passthrough();
export type ProviderField = z.infer<typeof FieldSchema>;

const ProviderSchema = z.object({
  provider: z.string(),
  label: z.string(),
  group: z.string(),
  access: z.string(),
  about: z.string(),
  unlocks: z.array(z.string()),
  configurable: z.boolean(),
  external_setup: z.string().nullable(),
  state: z.enum(["CONFIGURED", "PARTIAL", "NEEDS_SETUP", "OPTIONAL", "EXTERNAL"]),
  live_gates: z.array(z.object({ name: z.string(), enabled: z.boolean(), source: z.string() }).passthrough()),
  applies: z.enum(["NEXT_REQUEST", "RESTART"]),
  applies_note: z.string().nullable(),
  verification: z.string(),
  fields: z.array(FieldSchema),
}).passthrough();
export type ProviderSetup = z.infer<typeof ProviderSchema>;

const ResultSchema = z.object({
  provider: z.string(),
  saved: z.array(z.string()),
  cleared: z.array(z.string()),
  gates_enabled: z.array(z.string()),
  gates_removed: z.array(z.string()),
  applies: z.enum(["NEXT_REQUEST", "RESTART"]),
  verification: z.string(),
  refresh_failed: z.boolean().optional(),
}).passthrough();
export type SaveResult = z.infer<typeof ResultSchema>;

export const ProviderConfigSchema = z.object({
  schema_version: z.literal("operator-config/1.1"),
  providers: z.array(ProviderSchema),
  secrets_included: z.literal(false),
}).passthrough();
export type ProviderConfig = z.infer<typeof ProviderConfigSchema>;

const SaveResponseSchema = ProviderConfigSchema.extend({ result: ResultSchema });

export const PROVIDER_CONFIG_QUERY_KEY = ["screener-setup-providers"] as const;

export function fetchProviderConfig(signal?: AbortSignal) {
  return fetchJson("/operator/config", ProviderConfigSchema, signal ? { signal } : undefined);
}

/** Explicit operator save: blank values keep what is stored; `clear` removes named settings. */
export function saveProviderSettings(provider: string, values: Record<string, string>, clear: string[] = []) {
  return postJson("/operator/config/provider", { provider, values, clear }, SaveResponseSchema);
}

const ERRORS: Record<string, string> = {
  VALUE_REQUIRED: "Enter a value.",
  NO_CHANGES: "Nothing to save: every field is blank.",
  VALUE_HAS_WHITESPACE: "Keys and tokens can't contain spaces. Paste the value exactly as the provider shows it.",
  VALUE_HAS_CONTROL_CHARACTERS: "The value contains a tab or line break. Paste it again as one line.",
  VALUE_TOO_LONG: "That is longer than any key this provider issues.",
  VALUE_QUOTED: "Leave out the quotation marks.",
  VALUE_IS_PLACEHOLDER: "That looks like a placeholder, not a real value.",
  VALUE_NOT_ALLOWED: "Pick one of the listed values.",
  INVALID_MODEL_ID: "Enter a model name such as the provider lists it.",
  SEC_USER_AGENT_REQUIRED: "Enter your name and a contact email.",
  SEC_USER_AGENT_MUST_IDENTIFY_CONTACT: "Include a name and a full contact email, e.g. IMP Screener Jane Doe jane@example.com.",
  SEC_USER_AGENT_NEEDS_NAME: "Add your name or firm before the email.",
  SEC_USER_AGENT_GENERIC_FORBIDDEN: "The SEC blocks generic tool names. Use your own name or firm.",
  SEC_USER_AGENT_NOT_ASCII: "Use plain letters (no accents): the SEC receives it as a web request header.",
  SETTING_OVERRIDDEN_BY_ENVIRONMENT: "The API's environment sets this. Change it there; a value saved here would never be used.",
  PROVIDER_FIELD_NOT_ALLOWED: "IMP doesn't accept that setting.",
  PROVIDER_NOT_SUPPORTED: "This provider isn't set up from IMP.",
  OPERATOR_CONFIG_ORIGIN_REJECTED: "Settings can only be changed from IMP on this computer.",
};

/** Plain-language text for a rejected save. The server's message is `CODE` or `CODE:SETTING`, never a value. */
export function describeSaveError(error: unknown): string {
  const reason = (error as { reasonCode?: unknown } | null)?.reasonCode;
  const text = `${error instanceof Error ? error.message : String(error ?? "")} ${typeof reason === "string" ? reason : ""}`;
  const code = Object.keys(ERRORS).find((candidate) => text.includes(candidate));
  if (code) return ERRORS[code]!;
  if (/fetch|network/i.test(text)) return "Could not reach the API. Is it running?";
  return "Not saved. Check the value and try again.";
}
