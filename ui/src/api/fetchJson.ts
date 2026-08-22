import type { z } from "zod";

export class ApiRequestError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "ApiRequestError";
  }
}

async function parseError(response: Response, path: string): Promise<never> {
  try {
    const payload = await response.json();
    if (typeof payload === "object" && payload !== null && "code" in payload) {
      throw new ApiRequestError(String(payload.code), String(payload.message ?? path));
    }
  } catch (error) {
    if (error instanceof ApiRequestError) throw error;
  }
  throw new Error(`Request failed: ${path}`);
}

export async function fetchJson<T>(path: string, schema: z.ZodSchema<T>): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    await parseError(response, path);
  }
  return schema.parse(await response.json());
}

export async function postJson<T>(path: string, body: unknown, schema: z.ZodSchema<T>): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    await parseError(response, path);
  }
  return schema.parse(await response.json());
}

export async function fetchRawJson(path: string): Promise<Record<string, unknown>> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${path}`);
  }
  const payload = await response.json();
  if (typeof payload !== "object" || payload === null) {
    throw new Error(`Invalid JSON payload: ${path}`);
  }
  return payload as Record<string, unknown>;
}
