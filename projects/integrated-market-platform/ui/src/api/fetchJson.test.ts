import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ApiRequestError } from "./errors";
import { fetchJson, fetchRawJson, postJson } from "./fetchJson";

const OkSchema = z.object({ ok: z.literal(true) });

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response;
}

describe("fetchJson error_category envelope", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("throws ApiRequestError with the API error_category", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          error: "bad field",
          reason_code: "UI_REQUEST_INVALID",
          error_category: "VALIDATION_ERROR",
        }),
      ),
    );

    await expect(fetchJson("/preview", OkSchema)).rejects.toMatchObject({
      name: "ApiRequestError",
      message: "bad field",
      code: "UI_REQUEST_INVALID",
      reasonCode: "UI_REQUEST_INVALID",
      errorCategory: "VALIDATION_ERROR",
    });
    await expect(fetchJson("/preview", OkSchema)).rejects.toBeInstanceOf(ApiRequestError);
  });

  it("fails closed when the API omits error_category", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          error: "bad field",
          reason_code: "UI_REQUEST_INVALID",
        }),
      ),
    );

    await expect(fetchJson("/preview", OkSchema)).rejects.toEqual(new Error("Request failed: /preview"));
    await expect(fetchJson("/preview", OkSchema)).rejects.not.toBeInstanceOf(ApiRequestError);
  });

  it("parses the same envelope on POST and raw GET", async () => {
    const envelope = {
      error: "Paper execution is not authorized",
      reason_code: "PAPER_EXECUTION_NOT_AUTHORIZED",
      error_category: "MODE_BLOCKED",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(403, envelope)));

    await expect(postJson("/paper/orders", {}, OkSchema)).rejects.toMatchObject({
      errorCategory: "MODE_BLOCKED",
      reasonCode: "PAPER_EXECUTION_NOT_AUTHORIZED",
    });
    await expect(fetchRawJson("/explain/x")).rejects.toMatchObject({
      errorCategory: "MODE_BLOCKED",
    });
  });
});
