import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ProviderConfig } from "../../../api/providerConfig";
import { ProviderSetupList } from "./ProviderConfig";
import { RemedyHint } from "./Remedy";
import { providerConfigPayload, secEntry } from "./providerConfig.fixture";

const IDENTITY = "Acme Research Ops Desk ops-desk@acme-research.test";
const SECRET = "fh-live-7f3a9c2e51d4";

type Call = { url: string; method: string; body: Record<string, unknown> | null };

let config: ProviderConfig;
let calls: Call[];
let respond: (call: Call) => { status: number; body: unknown } | null;

function json(status: number, body: unknown) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) } as Response);
}

beforeEach(() => {
  config = providerConfigPayload();
  calls = [];
  respond = () => null;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const call = { url: String(input), method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null };
    calls.push(call);
    const custom = respond(call);
    if (custom) return json(custom.status, custom.body);
    if (call.url === "/operator/config") return json(200, config);
    return json(404, { error: "not found" });
  }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function mount(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

function saved(provider: string, result: Partial<Record<string, unknown>>, next: ProviderConfig) {
  config = next;  // the server's GET reflects the save from now on
  return { status: 200, body: { ...next, result: { provider, saved: [], cleared: [], gates_enabled: [], gates_removed: [],
    applies: "NEXT_REQUEST", verification: "ON_FIRST_USE", ...result } } };
}

function errorBody(message: string, reason = "OPERATOR_CONFIG_FAILED") {
  return { error: message, reason_code: reason, error_category: "VALIDATION_ERROR" };
}

async function openProvider(name: string) {
  const list = await screen.findByRole("region", { name: "Provider settings" });
  fireEvent.click(within(list).getByRole("button", { name }));
  return screen.findByRole("dialog");
}

describe("Provider settings in Setup", () => {
  it("groups providers, says what each unlocks, and keeps OpenD a local process", async () => {
    mount(<ProviderSetupList enabled />);
    const list = await screen.findByRole("region", { name: "Provider settings" });
    expect(within(list).getByText("Regulatory and government")).toBeInTheDocument();
    const sec = within(list).getByText("SEC EDGAR").closest("li")!;
    expect(sec).toHaveTextContent("needs setup");
    expect(sec).toHaveTextContent("13F institutional ownership");
    expect(within(sec).getByRole("button", { name: "Configure SEC EDGAR" })).toBeInTheDocument();
    const finnhub = within(list).getByText("Finnhub").closest("li")!;
    expect(finnhub).toHaveTextContent("configured");
    expect(within(finnhub).getByRole("button", { name: "Manage Finnhub" })).toBeInTheDocument();
    const openD = within(list).getByText("moomoo OpenD").closest("li")!;
    expect(openD).toHaveTextContent("No API key. Start OpenD");
    expect(within(openD).queryByRole("button")).toBeNull();
    // A paid API or subscription is "not set", never a "needs setup" nudge, and does not count as pending.
    const openai = within(list).getByText("OpenAI").closest("li")!;
    expect(openai).toHaveTextContent("Paid API · billed by the provider");
    expect(openai).toHaveTextContent("not set");
    expect(openai).not.toHaveTextContent("needs setup");
    expect(within(list).getByText("AI synthesis").closest("details")).not.toHaveAttribute("open");
    expect(within(list).getByText("Finviz Elite").closest("li")).toHaveTextContent("not set");
  });

  it("configures the SEC identity: explains it, rejects a bad value, saves, and shows it switched on", async () => {
    mount(<ProviderSetupList enabled />);
    const dialog = await openProvider("Configure SEC EDGAR");
    expect(within(dialog).getByRole("heading", { name: "SEC EDGAR" })).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Fair Access policy requires");
    for (const unlock of ["SEC filings in News", "SEC press releases", "13F institutional ownership", "Fail-to-deliver data (Short Squeeze)"]) {
      expect(within(dialog).getByText(unlock)).toBeInTheDocument();
    }
    const input = within(dialog).getByLabelText("Contact identity");
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveAttribute("placeholder", "IMP Screener Jane Doe jane@example.com");
    expect(within(dialog).getByRole("button", { name: "Save & enable" })).toBeInTheDocument();

    respond = (call) => call.method === "POST"
      ? { status: 400, body: errorBody("SEC_USER_AGENT_MUST_IDENTIFY_CONTACT:SEC_USER_AGENT") } : null;
    fireEvent.change(input, { target: { value: "Acme Research" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save & enable" }));
    expect(await within(dialog).findByText(/Include a name and a full contact email/)).toBeInTheDocument();
    expect(input).toHaveValue("Acme Research");

    const next = providerConfigPayload({ sec: secEntry(true) });
    respond = (call) => call.method === "POST"
      ? saved("sec", { saved: ["SEC_USER_AGENT"], gates_enabled: ["IMP_EDGAR_LIVE", "IMP_SEC_FTD_LIVE"] }, next) : null;
    fireEvent.change(input, { target: { value: IDENTITY } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save & enable" }));
    const status = await within(dialog).findByText(/SEC EDGAR is switched on/);
    expect(status).toHaveTextContent("applies to the next request; no restart needed");
    expect(status).toHaveTextContent("Nothing was called to test it");
    const post = calls.filter((call) => call.method === "POST").at(-1)!;
    expect(post).toEqual({ url: "/operator/config/provider", method: "POST",
      body: { provider: "sec", values: { SEC_USER_AGENT: IDENTITY }, clear: [] } });
    await waitFor(() => expect(within(dialog).getByLabelText("Contact identity")).toHaveValue(""));
    expect(await within(dialog).findByText(/Current: contact at @acme-research.test/)).toBeInTheDocument();
    expect(within(dialog).getByText("configured")).toBeInTheDocument();
  });

  it("keeps a stored secret hidden, replaces it, and never writes it to storage or the URL", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    mount(<ProviderSetupList enabled />);
    const dialog = await openProvider("Manage Finnhub");
    const input = within(dialog).getByLabelText("API key");
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveAttribute("autocomplete", "off");
    expect(input).toHaveValue("");
    expect(input.getAttribute("placeholder")).toMatch(/stored/);
    expect(within(dialog).getByRole("button", { name: "Save" })).toBeInTheDocument();  // already switched on

    respond = (call) => call.method === "POST" ? saved("finnhub", { saved: ["FINNHUB_API_KEY"] }, config) : null;
    fireEvent.change(input, { target: { value: SECRET } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByText(/^Saved\./)).toBeInTheDocument();
    expect(input).toHaveValue("");
    const post = calls.find((call) => call.method === "POST")!;
    expect(post.body).toEqual({ provider: "finnhub", values: { FINNHUB_API_KEY: SECRET }, clear: [] });
    for (const call of calls) expect(call.url).not.toContain(SECRET);
    for (const [, value] of setItem.mock.calls) expect(String(value)).not.toContain(SECRET);
    expect(document.body.innerHTML).not.toContain(SECRET);
  });

  it("removes a stored key only after confirmation", async () => {
    mount(<ProviderSetupList enabled />);
    const dialog = await openProvider("Manage Finnhub");
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove key" }));
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep" }));
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    respond = (call) => call.method === "POST" ? saved("finnhub", { cleared: ["FINNHUB_API_KEY"], gates_removed: ["IMP_FINNHUB_LIVE"] }, config) : null;
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove key" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(await within(dialog).findByText(/^Removed\./)).toBeInTheDocument();
    expect(calls.find((call) => call.method === "POST")!.body).toEqual({ provider: "finnhub", values: {}, clear: ["FINNHUB_API_KEY"] });
  });

  it("shows an environment-set field read-only and says a blank form has nothing to save", async () => {
    mount(<ProviderSetupList enabled />);
    const dialog = await openProvider("Configure FINRA API");
    expect(within(dialog).queryByRole("textbox", { name: "Client ID" })).toBeNull();
    expect(dialog).toHaveTextContent("Set by the API's environment. Change it there");
    expect(within(dialog).getByLabelText("Client secret")).toHaveAttribute("type", "password");
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByText("Nothing to save: every field is blank.")).toBeInTheDocument();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });

  it("says when a provider needs an API restart", async () => {
    mount(<ProviderSetupList enabled />);
    const dialog = await openProvider("Configure Finviz Elite");
    expect(dialog).toHaveTextContent("Needs an API restart after saving. Finviz reads its token when the API starts.");
    expect(dialog).toHaveTextContent("Your existing subscription");
  });

  it("closes on Escape", async () => {
    mount(<ProviderSetupList enabled />);
    await openProvider("Configure SEC EDGAR");
    act(() => { fireEvent.keyDown(document, { key: "Escape" }); });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("Configure action in a remedy", () => {
  it("opens the provider's Setup form from wherever the degraded state is shown", async () => {
    mount(<RemedyHint remedy={{ reason: "OPENAI_API_KEY_NOT_SET", title: "OpenAI has no key", step: "Save an OpenAI key in Setup.",
      action: { kind: "CONFIGURE", provider: "openai", label: "Enter key" } }} />);
    fireEvent.click(screen.getByRole("button", { name: "Enter key" }));
    const dialog = await screen.findByRole("dialog", { name: "OpenAI" });
    expect(dialog).toHaveTextContent("Paid API · billed by the provider");
    expect(within(dialog).getByLabelText("API key")).toHaveAttribute("type", "password");
  });
});
