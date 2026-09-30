import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";

/**
 * Screener setup contracts: the plain-language fix the server attaches beside a degraded
 * reason code, the setup checklist, and the allowlisted connect action. The reason code is
 * never replaced; a remedy only says what it means and the one step that clears it.
 */
const RemedyAction = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("CONNECT"), provider: z.string(), label: z.string() }).passthrough(),
  z.object({ kind: z.literal("COMMAND"), command: z.string() }).passthrough(),
]);
export const RemedySchema = z.object({
  reason: z.string(), title: z.string(), step: z.string(), action: RemedyAction.nullable(),
}).passthrough();
export type Remedy = z.infer<typeof RemedySchema>;

const SetupRow = z.object({
  id: z.string(), label: z.string(), kind: z.string(), state: z.string(), reason: z.string().nullable(),
  remedy: RemedySchema.nullable(), connectable: z.boolean(),
}).passthrough();
export type SetupRow = z.infer<typeof SetupRow>;
export const SetupSchema = z.object({
  schema_version: z.literal("screener-setup/1.0.0"),
  rows: z.array(SetupRow), ready_count: z.number(), total: z.number(),
}).passthrough();
export type ScreenerSetup = z.infer<typeof SetupSchema>;

export const ConnectResultSchema = z.object({
  provider: z.string(), state: z.enum(["CONNECTED", "STARTING", "FAILED"]), reason: z.string().nullable(),
  remedy: RemedySchema.nullable(),
}).passthrough();
export type ConnectResult = z.infer<typeof ConnectResultSchema>;

export const SETUP_QUERY_KEY = ["screener-setup"] as const;

export function fetchScreenerSetup(signal?: AbortSignal) {
  return fetchJson("/screener/setup", SetupSchema, signal ? { signal } : undefined);
}

/** Explicit operator click only: starts an allowlisted local provider (OpenD, FinBERT, local model). */
export function connectProvider(provider: string) {
  return postJson(`/screener/providers/${encodeURIComponent(provider)}/connect`, {}, ConnectResultSchema);
}
