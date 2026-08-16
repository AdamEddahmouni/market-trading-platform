import type { z } from "zod";

export async function fetchJson<T>(path: string, schema: z.ZodSchema<T>): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${path}`);
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
