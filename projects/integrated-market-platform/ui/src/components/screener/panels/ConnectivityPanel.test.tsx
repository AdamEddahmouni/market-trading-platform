import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ConnectivityPanel, { ConnectivityView } from "./ConnectivityPanel";
import { SpecialistContext, type SpecialistSelection } from "./shared";
import type { IDockviewPanelProps } from "dockview-react";
import type { ScreenerRow } from "../../../api/screener";
const request = vi.hoisted(() => vi.fn());
vi.mock("../../../api/screenerConnectivity", async original => ({
  ...(await original<typeof import("../../../api/screenerConnectivity")>()), fetchConnectivity: request,
}));
import type { ConnectivityPayload } from "../../../api/screenerConnectivity";

const node = (id: string, label: string) => ({ node_id: id, canonical_instrument_id: id, label,
  domain: "STOCK_ETF", asset_class: "EQUITY", instrument_kind: "TRADABLE_SECURITY",
  state: "CURRENT", source: "controlled", as_of: "2026-10-02T15:00:00Z", received_at: null,
  facts: {}, executable: false, role: "CONTEXT" });
const selected = node("XA01:selected", "NVDA");
const payload: ConnectivityPayload = { schema_version: "screener-connectivity/1.0.0", instrument_id: "NVDA",
  universe: "US_EQUITIES", selected_instrument: selected, nodes: [selected, node("XA01:future", "NQ")],
  edges: [{ edge_id: "relation", from_node: selected.node_id, to_node: "XA01:future",
    relationship_type: "REFERENCE_RELEVANT_TO", relationship_class: "CONTEXTUAL_MAPPING",
    basis: "FUTURES_CONTEXT_MAP_V1", definition_version: "V1", evidence_state: "CONFLICTING",
    explanation: "Observed opposite direction, not a forecast", provenance: {} }],
  completeness: { requested_domains: ["STOCK_ETF", "OPTIONS"], domains: {
    STOCK_ETF: { state: "AVAILABLE", reason: null }, OPTIONS: { state: "UNAVAILABLE", reason: "NOT_ENTITLED" } } },
  generated_at: "2026-10-02T15:01:00Z", causal_note: "Research only" };

describe("Connectivity inspection", () => {
  it("renders an accessible graph, equivalent list, source clocks, and missing domains", () => {
    render(<ConnectivityView data={payload} />);
    expect(screen.getByRole("region", { name: "Cross-asset connectivity graph" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Cross-asset relationships" })).toBeInTheDocument();
    expect(screen.getAllByText("CONFLICTING").length).toBeGreaterThan(0);
    expect(screen.getByText(/NOT_ENTITLED/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Inspect NQ/ }));
    expect(screen.getByText("Why connected")).toBeInTheDocument();
    expect(screen.getAllByText(/Observed opposite direction/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/controlled/).length).toBeGreaterThan(0);
  });
  it.each(["CONFIRMING", "CONTEXT_ONLY", "UNKNOWN", "UNAVAILABLE"] as const)("shows %s as text without relying on color", state => {
    render(<ConnectivityView data={{ ...payload, edges: [{ ...payload.edges[0], evidence_state: state }] }} />);
    expect(screen.getAllByText(state).length).toBeGreaterThan(0);
  });
  it("clears the inspector when the selected graph is replaced", () => {
    const { rerender } = render(<ConnectivityView key="NVDA" data={payload} />);
    fireEvent.click(screen.getByRole("button", { name: /Inspect NQ/ }));
    rerender(<ConnectivityView key="AAPL" data={{ ...payload, instrument_id: "AAPL", nodes: [node("AAPL", "AAPL")],
      selected_instrument: node("AAPL", "AAPL"), edges: [] }} />);
    expect(screen.queryByText("Why connected")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Inspect NQ/ })).not.toBeInTheDocument();
  });
  it("does not render a late response from a prior instrument and stops requests without selection", async () => {
    let resolveOld!: (data: ConnectivityPayload) => void;
    request.mockImplementation((id: string) => id === "NVDA" ? new Promise(resolve => { resolveOld = resolve; }) :
      Promise.resolve({ ...payload, instrument_id: "AAPL", nodes: [node("AAPL", "AAPL")], selected_instrument: node("AAPL", "AAPL"), edges: [] }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const api = { isVisible: true, onDidVisibilityChange: () => ({ dispose() {} }) } as unknown as IDockviewPanelProps["api"];
    const selection = (id: string | null): SpecialistSelection => ({ row: id ? {
      instrument: { instrument_id: id, venue_id: "US_EQUITY", asset_class: "EQUITY" }, symbol: id,
    } as ScreenerRow : null, settledId: id, universe: "US_EQUITIES", supportedPanels: new Set(["connectivity"]),
      quote: undefined, filters: [], demand: null, actions: { close() {}, move() {}, resize() {} } });
    const content = (id: string | null) => <QueryClientProvider client={client}><SpecialistContext.Provider value={selection(id)}>
      <ConnectivityPanel api={api} {...({} as IDockviewPanelProps)} />
    </SpecialistContext.Provider></QueryClientProvider>;
    const { rerender } = render(content("NVDA"));
    await waitFor(() => expect(request).toHaveBeenCalledWith("NVDA", "US_EQUITIES", expect.anything()));
    rerender(content("AAPL"));
    await screen.findByRole("button", { name: /Inspect AAPL/ });
    await act(async () => resolveOld(payload));
    expect(screen.queryByRole("button", { name: /Inspect NVDA/ })).not.toBeInTheDocument();
    rerender(content(null));
    expect(screen.queryByRole("region", { name: "Cross-asset connectivity graph" })).not.toBeInTheDocument();
    client.clear();
  });
});
