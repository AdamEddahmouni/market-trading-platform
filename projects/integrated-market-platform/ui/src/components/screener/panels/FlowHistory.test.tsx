import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import FlowHistory from "./FlowHistory";

const m = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("../../../api/screenerPanels", () => ({ fetchFlowSeries: m.fetch }));
vi.mock("./CvdChart", () => ({ default: ({ onViewport }: { onViewport: (range: unknown) => void }) =>
  <button onClick={() => onViewport({ from: 100000, to: 110000, live: false })}>Inspect history</button> }));
afterEach(() => vi.useRealTimers());

it("keeps current captured context refreshing during historical inspection", async () => {
  vi.useFakeTimers();
  let current = 10;
  m.fetch.mockImplementation(async (instrument: string, _universe: string, range: string) => ({
    instrument_id: instrument, range, resolution_seconds: 1, state: "CURRENT", reason: null,
    coverage: { requested_start_ms: 100000, requested_end_ms: 120000, actual_start_ms: 100000,
      actual_end_ms: 111000, anchor_at: "1970-01-01T00:01:40Z", complete: false, truncated: false,
      dropped_late_trades: 0, gaps: [], persistence: "RUNTIME_LOCAL" },
    points: [{ time_ms: 100000, end_ms: 101000, cvd: 10, delta: 10, trade_count: 1,
      classified_volume: 10, unknown_volume: 0, providers: ["MOOMOO"], segment: 0 }],
    latest: { cvd: current, recent_delta: current, trades_per_minute: 1, event_at: "1970-01-01T00:02:00Z" },
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><FlowHistory instrument="NVDA" universe="US_EQUITIES" visible mode="cvd" /></QueryClientProvider>);
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  expect(screen.getByText(/Captured CVD now \+10/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Inspect history" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(400); });
  current = 20;
  await act(async () => { await vi.advanceTimersByTimeAsync(5100); });
  expect(screen.getByText(/Captured CVD now \+20/)).toBeInTheDocument();
  client.clear();
});
it("discloses a historical detail gap even when the current capture is continuous", async () => {
  vi.useFakeTimers();
  m.fetch.mockImplementation(async (instrument: string, _universe: string, range: string, _resolution: string, window?: unknown) => ({
    instrument_id: instrument, range, resolution_seconds: 1, state: "CURRENT", reason: null,
    coverage: { requested_start_ms: window ? 100000 : 110000, requested_end_ms: 120000,
      actual_start_ms: window ? 100000 : 110000, actual_end_ms: 120000,
      anchor_at: "1970-01-01T00:01:40Z", complete: !window, truncated: false,
      dropped_late_trades: 0, persistence: "RUNTIME_LOCAL",
      gaps: window ? [{ start_ms: 103000, end_ms: 105000, reason: "SUBSCRIPTION_INTERRUPTION" }] : [] },
    points: [{ time_ms: window ? 100000 : 110000, end_ms: window ? 101000 : 111000,
      cvd: 10, delta: 10, trade_count: 1, classified_volume: 10, unknown_volume: 0, providers: ["MOOMOO"], segment: 0 }],
    latest: { cvd: 10, recent_delta: 10, trades_per_minute: 1, event_at: "1970-01-01T00:02:00Z" },
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><FlowHistory instrument="NVDA" universe="US_EQUITIES" visible mode="cvd" /></QueryClientProvider>);
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  expect(screen.getByText(/Continuous subscribed capture/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Inspect history" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(500); });
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  expect(m.fetch).toHaveBeenCalledWith("NVDA", "US_EQUITIES", "5m", "auto", expect.objectContaining({ start: expect.any(Number) }), expect.anything());
  expect(screen.getByText(/subscription interrupted/)).toBeInTheDocument();
  expect(screen.getByText(/Partial capture; missing history/)).toBeInTheDocument();
  client.clear();
});
it("hides cached historical detail when the current authority gate blocks history", async () => {
  vi.useFakeTimers();
  let blocked = false;
  m.fetch.mockImplementation(async (instrument: string, _universe: string, range: string, _resolution: string, window?: unknown) => ({
    instrument_id: instrument, range, resolution_seconds: 1, state: blocked && !window ? "DISCONNECTED" : "CURRENT", reason: "DISCONNECTED",
    coverage: blocked && !window ? null : { requested_start_ms: 100000, requested_end_ms: 120000, actual_start_ms: 100000,
      actual_end_ms: 111000, anchor_at: "1970-01-01T00:01:40Z", complete: false, truncated: false,
      dropped_late_trades: 0, gaps: [], persistence: "RUNTIME_LOCAL" },
    points: blocked && !window ? [] : [{ time_ms: 100000, end_ms: 101000, cvd: 10, delta: 10, trade_count: 1,
      classified_volume: 10, unknown_volume: 0, providers: ["MOOMOO"], segment: 0 }], latest: null,
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><FlowHistory instrument="NVDA" universe="US_EQUITIES" visible mode="cvd" /></QueryClientProvider>);
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  fireEvent.click(screen.getByRole("button", { name: "Inspect history" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(400); });
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  blocked = true;
  await act(async () => { await vi.advanceTimersByTimeAsync(5100); });
  expect(screen.queryByRole("button", { name: "Inspect history" })).toBeNull();
  expect(screen.getByText(/disconnect/i)).toBeInTheDocument();
  client.clear();
});
