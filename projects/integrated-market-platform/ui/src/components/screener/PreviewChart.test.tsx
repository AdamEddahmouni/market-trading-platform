import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ createChart: vi.fn() }));
vi.mock("lightweight-charts", () => ({
  LineStyle: { Dashed: 2 },
  createChart: mocks.createChart.mockImplementation(() => ({
    addCandlestickSeries: () => ({ setData: vi.fn(), createPriceLine: vi.fn(), removePriceLine: vi.fn() }),
    timeScale: () => ({ setVisibleLogicalRange: vi.fn() }), applyOptions: vi.fn(), remove: vi.fn(),
  })),
}));

import PreviewChart from "./PreviewChart";

describe("Quick Preview chart", () => {
  it("keeps the candles clear of the logo and the price labels whole, and still credits TradingView", () => {
    render(<PreviewChart bars={[]} forming={null} support={null} resistance={null} label="AAPL 5m candles" />);
    const options = mocks.createChart.mock.calls[0][1];
    expect(options.layout.attributionLogo).toBe(false);
    expect(options.layout.fontSize).toBeGreaterThanOrEqual(11);
    expect(options.rightPriceScale.minimumWidth).toBeGreaterThanOrEqual(56);
    expect(screen.getByRole("link", { name: "Charts by TradingView" })).toHaveAttribute("href", "https://www.tradingview.com/");
  });
});
