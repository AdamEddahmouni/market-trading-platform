import type { z } from "zod";
import { authHeaders } from "../auth/session";

/** The server answered, but not in the shape this client build expects (a UI/API version skew). */
export class SchemaMismatchError extends Error {
  readonly path: string;
  readonly issues: z.ZodIssue[];
  constructor(path: string, issues: z.ZodIssue[]) {
    super(`Response did not match the expected schema: ${path}`);
    this.name = "SchemaMismatchError";
    this.path = path;
    this.issues = issues;
  }
}

function parseBody<T>(schema: z.ZodSchema<T>, payload: unknown, path: string): T {
  const result = schema.safeParse(payload);
  if (!result.success) throw new SchemaMismatchError(path, result.error.issues);
  return result.data;
}

async function parseError(response: Response, path: string): Promise<never> {
  try {
    const payload = await response.json();
    const { ApiRequestError, parseApiErrorEnvelope } = await import("./errors");
    const envelope = parseApiErrorEnvelope(payload);
    if (envelope) {
      throw new ApiRequestError(envelope);
    }
  } catch (error) {
    if (error instanceof Error && error.name === "ApiRequestError") throw error;
  }
  throw new Error(`Request failed: ${path}`);
}

export async function fetchJson<T>(path: string, schema: z.ZodSchema<T>, init?: { signal?: AbortSignal }): Promise<T> {
  const response = await fetch(path, init?.signal ? { headers: authHeaders(), signal: init.signal } : { headers: authHeaders() });
  if (!response.ok) {
    await parseError(response, path);
  }
  return parseBody(schema, await response.json(), path);
}

export async function postJson<T>(path: string, body: unknown, schema: z.ZodSchema<T>, init?: { signal?: AbortSignal }): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
    ...(init?.signal ? { signal: init.signal } : {}),
  });
  if (!response.ok) {
    await parseError(response, path);
  }
  return parseBody(schema, await response.json(), path);
}

export async function fetchRawJson(path: string): Promise<Record<string, unknown>> {
  const response = await fetch(path, { headers: authHeaders() });
  if (!response.ok) {
    await parseError(response, path);
  }
  const payload = await response.json();
  if (typeof payload !== "object" || payload === null) {
    throw new Error(`Invalid JSON payload: ${path}`);
  }
  return payload as Record<string, unknown>;
}
