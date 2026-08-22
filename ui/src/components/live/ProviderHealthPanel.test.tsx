import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { ProviderHealthPanel } from "./ProviderHealthPanel";

vi.mock("../../api/hooks", () => ({
  useProviderHealthQuery: () => ({
    data: {
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
    },
    isLoading: false,
    isError: false,
  }),
}));

function renderPanel() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <ProviderHealthPanel />
    </QueryClientProvider>,
  );
}

describe("ProviderHealthPanel", () => {
  it("shows live provider diagnostics", () => {
    renderPanel();
    expect(screen.getByText(/MOOMOO · CONNECTED/)).toBeInTheDocument();
    expect(screen.getByText(/DISPLAY_ONLY/)).toBeInTheDocument();
    expect(screen.getByText(/Generation/)).toBeInTheDocument();
  });
});
