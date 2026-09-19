import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProviderHealthPanel } from "./ProviderHealthPanel";

const healthMock = vi.hoisted(() => ({
  isLoading: false,
  isError: false,
  data: undefined as Record<string, unknown> | undefined,
  refetch: vi.fn(),
}));

vi.mock("../../api/hooks", () => ({
  useProviderHealthQuery: () => healthMock,
}));

const connectedHealth = {
  available: true,
  lifecycle: {
    connection_state: "CONNECTED",
    provider_role: "MARKET_DATA",
    entitlement_state: "PROBE_VERIFIED",
    reconnect_count: 1,
    execution_use: "DISPLAY_ONLY",
    sdk_version: "10.10.7008",
    provider_generation_id: 2,
  },
  quota: { active_count: 2, max_quota: 100 },
  metrics: { events_admitted: 42 },
  provider_summary: {
    provider: "MOOMOO",
    quote_entitlement: true,
    event_lag_ms_p50: 12,
    event_lag_ms_p95: 45,
    dropped: 0,
  },
};

function renderPanel() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ProviderHealthPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ProviderHealthPanel", () => {
  beforeEach(() => {
    healthMock.isLoading = false;
    healthMock.isError = false;
    healthMock.data = connectedHealth;
    healthMock.refetch.mockReset();
  });

  it("shows live provider diagnostics", () => {
    renderPanel();
    expect(screen.getByText(/MOOMOO · CONNECTED/)).toBeInTheDocument();
    expect(screen.getByText(/DISPLAY_ONLY/)).toBeInTheDocument();
    expect(screen.getByText(/Generation/)).toBeInTheDocument();
  });

  it("shows a loading status instead of treating an in-flight request as Live disabled", () => {
    healthMock.isLoading = true;
    healthMock.data = undefined;
    renderPanel();
    expect(screen.getByRole("status")).toHaveTextContent(/loading provider diagnostics/i);
    expect(screen.queryByText(/live observational mode disabled/i)).not.toBeInTheDocument();
  });

  it("shows a retryable error when the health request fails", () => {
    healthMock.isError = true;
    healthMock.data = undefined;
    renderPanel();
    expect(screen.getByRole("alert")).toHaveTextContent(/could not be loaded/i);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("states Live observational disabled only after a successful unavailable payload", () => {
    healthMock.data = { available: false, reason: "IMP_LIVE_OBSERVATIONAL not enabled" };
    renderPanel();
    expect(screen.getByRole("heading", { name: "Provider diagnostics" })).toBeInTheDocument();
    expect(screen.getByText("IMP_LIVE_OBSERVATIONAL not enabled")).toBeInTheDocument();
  });
});
