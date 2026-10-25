import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SetupAi } from "../../../api/setupAi";
import { AiEngineCard } from "./AiEngineCard";
import { providerConfigPayload } from "./providerConfig.fixture";

type Call = { url: string; method: string; body: Record<string, unknown> | null };
let calls: Call[];
let status: SetupAi;
let respond: (call: Call) => { status: number; body: unknown } | null;

const engine = (id: string, label: string, runtime: "LOCAL_MODEL" | "PAID_API", models: string[], ready: boolean, reason: string | null = null) =>
  ({ id, label, runtime, models, default_model: models[0] ?? null, state: ready ? "AVAILABLE" : "NOT_CONFIGURED", reason });

function payload(overrides: Partial<SetupAi> = {}): SetupAi {
  return {
    schema_version: "setup-ai/1.0.0", engine: "auto", resolved_engine: "local", model: null, source: "AUTOMATIC",
    engines: [engine("local", "Local model", "LOCAL_MODEL", ["Qwen/Qwen3-4B-GGUF:Q4_K_M"], true),
      engine("anthropic", "Anthropic Claude", "PAID_API", ["claude-sonnet-5-5", "claude-haiku-5-5"], false, "PAID_AI_CAP_NOT_SET"),
      engine("openai", "OpenAI", "PAID_API", ["gpt-6-luna"], false, "OPENAI_API_KEY_NOT_SET")],
    caps: { daily_usd: 0, monthly_usd: 0, set: false, settings: {
      IMP_PAID_AI_DAILY_USD: { source: "NONE", editable: true }, IMP_PAID_AI_MONTHLY_USD: { source: "NONE", editable: true } } },
    spend: { state: "CAP_NOT_SET", reason: "PAID_AI_CAP_NOT_SET", spent_today_usd: 0, spent_month_usd: 0, daily_cap_usd: 0, monthly_cap_usd: 0 },
    prices: [{ engine: "anthropic", model: "claude-haiku-5-5", priced: true, input_per_mtok: 0.1, output_per_mtok: 0.5 },
      { engine: "anthropic", model: "claude-sonnet-5-5", priced: true, input_per_mtok: 2, output_per_mtok: 10 }],
    benchmark: { generated_at: "2026-10-24T23:00:00Z", local_winner: "Qwen/Qwen3-4B-GGUF:Q4_K_M", paid_pick: "claude-haiku-5-5",
      runs: [{ engine: "local", model: "Qwen/Qwen3-4B-GGUF:Q4_K_M", skipped: false, cases: 60, accepted_pct: 70, p50_latency_ms: 5400 },
        { engine: "anthropic", model: "claude-haiku-5-5", skipped: false, cases: 60, accepted_pct: 90, p50_latency_ms: 5000, dollars_per_case: 0.0016 }] },
    engine_lock: { locked: false, reason: null }, secrets_included: false, ...overrides,
  } as SetupAi;
}

function json(code: number, body: unknown) {
  return Promise.resolve({ ok: code < 400, status: code, json: () => Promise.resolve(body) } as Response);
}

beforeEach(() => {
  calls = [];
  status = payload();
  respond = () => null;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const call = { url: String(input), method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null };
    calls.push(call);
    const custom = respond(call);
    if (custom) return json(custom.status, custom.body);
    if (call.url === "/screener/setup/ai") return json(200, status);
    return json(404, { error: "not found" });
  }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AiEngineCard enabled /></QueryClientProvider>);
}

describe("Which AI decides", () => {
  it("shows the free local model as the automatic choice and keeps paid off without caps", async () => {
    mount();
    const card = await screen.findByRole("region", { name: "Which AI decides" });
    expect(card).toHaveTextContent("Now: Free · Qwen/Qwen3-4B-GGUF:Q4_K_M (automatic always means the free local model)");
    expect(card).toHaveTextContent("Tested on 60 past decisions: 70% accepted, typically 5.4 s.");
    expect(card).toHaveTextContent("Set both dollar caps below to choose paid AI.");
    expect(card).toHaveTextContent("Paid AI stays off until both are above $0.");
    expect(within(card).queryByRole("button", { name: /Use paid/ })).toBeNull();
    // The benchmark's paid pick is preselected, with its list price and measured cost.
    expect(within(card).getByRole("combobox")).toHaveValue("claude-haiku-5-5");
    expect(card).toHaveTextContent("List price $0.10 in / $0.50 out per million tokens. Measured about 0.16¢ per decision, 90% accepted.");
  });

  it("saves the caps through the paid_ai provider setting", async () => {
    respond = (call) => call.url === "/operator/config/provider"
      ? { status: 200, body: { ...providerConfigPayload(), result: { provider: "paid_ai", saved: ["IMP_PAID_AI_DAILY_USD", "IMP_PAID_AI_MONTHLY_USD"],
        cleared: [], gates_enabled: [], gates_removed: [], applies: "NEXT_REQUEST", verification: "ON_FIRST_USE" } } } : null;
    mount();
    const form = await screen.findByRole("form", { name: "Paid AI dollar caps" });
    fireEvent.change(within(form).getByLabelText("Daily cap"), { target: { value: "1.50" } });
    fireEvent.change(within(form).getByLabelText("Monthly cap"), { target: { value: "20" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save caps" }));
    await waitFor(() => expect(form).toHaveTextContent("Saved. The caps apply to the next paid call."));
    expect(calls.find((call) => call.method === "POST")?.body).toEqual(
      { provider: "paid_ai", values: { IMP_PAID_AI_DAILY_USD: "1.50", IMP_PAID_AI_MONTHLY_USD: "20" }, clear: [] });
  });

  it("asks before switching to paid and sends the chosen model", async () => {
    status = payload({ caps: { ...payload().caps, daily_usd: 1.5, monthly_usd: 20, set: true },
      engines: payload().engines.map((item) => item.id === "anthropic" ? { ...item, state: "AVAILABLE", reason: null } : item) });
    respond = (call) => call.url === "/screener/news/synthesis/engine"
      ? { status: 200, body: { state: "AVAILABLE", reason: null, provider_id: "anthropic.messages", model_id: "claude-haiku-5-5" } } : null;
    mount();
    const card = await screen.findByRole("region", { name: "Which AI decides" });
    fireEvent.click(await within(card).findByRole("button", { name: "Use paid claude-haiku-5-5" }));
    const dialog = within(card).getByRole("alertdialog");
    expect(dialog).toHaveTextContent("refused if that would cross your daily or monthly dollar cap");
    expect(calls.some((call) => call.method === "POST")).toBe(false);          // nothing sent before confirming
    fireEvent.click(within(dialog).getByRole("button", { name: "Switch engine" }));
    await waitFor(() => expect(calls.find((call) => call.method === "POST")?.body).toEqual({ engine: "anthropic", model: "claude-haiku-5-5" }));
  });

  it("is locked while automatic passes run", async () => {
    status = payload({ resolved_engine: "anthropic", engine: "anthropic", model: "claude-haiku-5-5", source: "OPERATOR",
      engine_lock: { locked: true, reason: "REEVALUATION_LOOP_RUNNING" } });
    mount();
    const card = await screen.findByRole("region", { name: "Which AI decides" });
    expect(card).toHaveTextContent("Now: Paid · claude-haiku-5-5");
    expect(card).toHaveTextContent("Locked while Paper's automatic passes are running. Pause them to switch.");
    expect(within(card).getByRole("button", { name: "Use free local" })).toBeDisabled();
  });
});
