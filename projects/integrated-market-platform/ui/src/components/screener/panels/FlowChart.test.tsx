import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import CvdChart from "./CvdChart";

const m = vi.hoisted(() => ({ fit: vi.fn(), live: vi.fn(), set: vi.fn(), restore: vi.fn(),
  options: vi.fn(), subscribe: vi.fn(), unsubscribe: vi.fn(), remove: vi.fn(),
  range: { from: 100, to: 110 }, logical: { from: 0, to: 10 }, setLogical: vi.fn() }));
vi.mock("lightweight-charts", () => ({ createChart: (element: unknown, options: unknown) => {
  m.options(options);
  const scale = { fitContent: m.fit, scrollToRealTime: m.live, getVisibleRange: () => m.range,
    setVisibleRange: m.restore, getVisibleLogicalRange: () => m.logical, setVisibleLogicalRange: m.setLogical,
    subscribeVisibleTimeRangeChange: m.subscribe, unsubscribeVisibleTimeRangeChange: m.unsubscribe };
  return { timeScale: () => scale, addBaselineSeries: () => ({ setData: m.set }),
    addHistogramSeries: () => ({ setData: m.set }), removeSeries: vi.fn(), remove: m.remove };
} }));
const points = [{ time_ms: 100000, cvd: 10, delta: 10, segment: 0 }, { time_ms: 110000, cvd: 15, delta: 5, segment: 0 }];
beforeEach(() => {
  vi.clearAllMocks();
  m.range = { from: 100, to: 110 };
  m.restore.mockImplementation(range => { m.range = range; });
});

it("enables navigation and fits only on initial load and explicit Fit", () => {
  const view = render(<CvdChart points={points} label="Flow" />);
  expect(m.options.mock.calls[0][0]).toMatchObject({ handleScroll: true, handleScale: true });
  expect(m.fit).toHaveBeenCalledTimes(1);
  view.rerender(<CvdChart points={[...points, { time_ms: 111000, cvd: 20, delta: 5, segment: 0 }]} label="Flow" />);
  expect(m.fit).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Fit" }));
  expect(m.fit).toHaveBeenCalledTimes(2);
});

it("preserves historical viewport through refresh and resumes on Go Live", () => {
  const view = render(<CvdChart points={points} label="Flow" />);
  act(() => { m.range = { from: 100, to: 105 }; m.subscribe.mock.calls[0][0](m.range); });
  expect(screen.getByText("Historical view")).toBeInTheDocument();
  view.rerender(<CvdChart points={[...points, { time_ms: 111000, cvd: 20, delta: 5, segment: 0 }]} label="Flow" />);
  expect(m.restore).toHaveBeenCalledWith({ from: 100, to: 105 });
  fireEvent.click(screen.getByRole("button", { name: "Go Live" }));
  expect(m.live).toHaveBeenCalled();
  expect(screen.getByText("LIVE")).toBeInTheDocument();
  view.rerender(<CvdChart points={[...points, { time_ms: 112000, cvd: 25, delta: 10, segment: 0 }]} label="Flow" />);
  expect(m.restore).toHaveBeenLastCalledWith({ from: 107, to: 112 });
});

it("provides keyboard-accessible zoom and resets on instrument change", () => {
  const view = render(<CvdChart points={points} label="Flow" resetKey="NVDA" />);
  fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
  expect(m.setLogical).toHaveBeenCalledWith({ from: 2.5, to: 7.5 });
  view.rerender(<CvdChart points={points} label="Flow" resetKey="AAPL" />);
  expect(m.fit).toHaveBeenCalledTimes(2);
});

it("uses separate CVD series across coverage gaps", () => {
  render(<CvdChart points={[points[0], { ...points[1], segment: 1 }]} label="Gapped capture" />);
  expect(m.set.mock.calls.filter(([rows]) => rows.length === 1)).toHaveLength(2);
});

it("keeps the full captured range after Fit while new points arrive", () => {
  const view = render(<CvdChart points={points} label="Flow" />);
  act(() => m.subscribe.mock.calls[0][0]({ from: 103, to: 108 }));
  fireEvent.click(screen.getByRole("button", { name: "Fit" }));
  view.rerender(<CvdChart points={[...points, { time_ms: 111000, cvd: 20, delta: 5, segment: 0 }]} label="Flow" />);
  expect(m.restore).toHaveBeenLastCalledWith({ from: 100, to: 111 });
  expect(m.fit).toHaveBeenCalledTimes(2);
});
