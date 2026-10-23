import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Code, codeWords, distinctJoin, exchangeText, fieldDigits, filterText, filtersText, fixedText, priceText, sessionHint,
  sessionText, Stamp, stampText, stampTitle, universeText } from "./screenerText";

describe("codeWords", () => {
  it.each([
    ["FUTURE_CONTRACT", "Future contract"],
    ["XA01.UNDERLYING", "Underlying"],
    ["FUTURES_CONTEXT_MAP_V1", "Futures context map v1"],
    ["SEC_FILING", "SEC filing"],
    ["US_ETFS", "US ETFs"],
    ["movement 3", "Movement 3"],
  ])("%s reads as %s", (code, words) => expect(codeWords(code)).toBe(words));

  it("is empty for no code", () => {
    expect(codeWords(null)).toBe("");
    expect(codeWords("")).toBe("");
  });

  it("keeps the raw code on hover", () => {
    render(<Code code="TRADABLE_SECURITY" />);
    expect(screen.getByText("Tradable security")).toHaveAttribute("title", "TRADABLE_SECURITY");
  });
});

describe("stampText", () => {
  const now = Date.parse("2026-10-22T18:30:00Z"); // 14:30 ET (EDT)

  it("shows today's times as ET with seconds", () => {
    expect(stampText("2026-10-22T18:03:38Z", now)).toBe("14:03:38 ET");
    expect(stampText("2026-10-22T18:03:38.123456Z", now)).toBe("14:03:38 ET");
  });

  it("names the day for another day, and the year for another year", () => {
    expect(stampText("2026-10-21T18:03:38Z", now)).toBe("Oct 21 14:03 ET");
    expect(stampText("2025-12-31T15:00:00Z", now)).toBe("Dec 31, 2025 10:00 ET");
  });

  it("follows daylight saving: a winter time is EST", () => {
    expect(stampText("2026-12-01T15:00:00Z", Date.parse("2026-12-01T16:00:00Z"))).toBe("10:00:00 ET");
  });

  it("reads a calendar date as a date, never midnight UTC moved into ET", () => {
    expect(stampText("2026-10-01", now)).toBe("Oct 1, 2026");
    expect(stampTitle("2026-10-01")).toBe("Calendar date 2026-10-01");
  });

  it("uses midnight, not 24:00", () => {
    expect(stampText("2026-10-22T04:00:05Z", now)).toBe("00:00:05 ET");
  });

  it("shows an unparseable value as given and a missing one as a dash", () => {
    expect(stampText("not a time", now)).toBe("not a time");
    expect(stampText(null, now)).toBe("—");
  });

  it("puts UTC in the tooltip", () => {
    expect(stampTitle("2026-10-22T18:03:38Z")).toMatch(/^2026-10-22 18:03:38 UTC/);
  });

  it("renders a machine-readable <time>", () => {
    render(<Stamp iso="2026-10-22T18:03:38Z" now={now} />);
    const time = screen.getByText("14:03:38 ET");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("dateTime", "2026-10-22T18:03:38Z");
    expect(time.getAttribute("title")).toMatch(/UTC/);
  });
});

describe("sessions", () => {
  it.each([
    ["REGULAR", "Regular session"], ["PREMARKET", "Pre-market"], ["AFTER_HOURS", "After hours"], ["OVERNIGHT", "Overnight"],
    ["CLOSED", "Market closed"], ["24_7", "24/7"], ["TRADING", "Trading"], ["MIXED", "Mixed sessions"],
    ["PUBLICATION_BASED", "Published data"], ["PROVIDER_SPECIFIC", "Per contract"], ["UNAVAILABLE", "Unknown"],
  ])("%s reads as %s", (code, text) => expect(sessionText(code)).toBe(text));

  it("reads a missing session as Unknown, so \"Session …\" never says the word twice", () => {
    expect(sessionText(null)).toBe("Unknown");
    expect(`Session ${sessionText(undefined)}`).toBe("Session Unknown");
  });

  it("explains the states that are not one session", () => {
    expect(sessionHint("MIXED")).toMatch(/different trading sessions/);
    expect(sessionHint("PUBLICATION_BASED")).toMatch(/not a live trading session/);
    expect(sessionHint("REGULAR")).toBe("Market session");
  });
});

describe("numbers", () => {
  it("keeps fixed decimals so a column lines up", () => {
    expect(fixedText(21.4, 1)).toBe("21.4");
    expect(fixedText(35.38, 1)).toBe("35.4");
    expect(fixedText(2.3, 2)).toBe("2.30");
    expect(fixedText(72.17, 2)).toBe("72.17");
  });

  it("never rounds a small nonzero value to zero", () => {
    expect(fixedText(0.004, 2)).toBe("<0.01");
    expect(fixedText(-0.004, 2)).toBe("−<0.01");
    expect(fixedText(0, 2)).toBe("0.00");
  });

  it("gives RSI one decimal and ratios two", () => {
    expect(fieldDigits("rsi_14")).toBe(1);
    expect(fieldDigits("rel_volume")).toBe(2);
    expect(fieldDigits("short_ratio")).toBe(2);
    expect(fieldDigits("volume")).toBeUndefined();
  });

  it("keeps four decimals below $1, as Quick Preview does", () => {
    expect(priceText(0.01)).toBe("0.0100");
    expect(priceText(12.3)).toBe("12.30");
    expect(priceText(0)).toBe("0.00");
  });
});

describe("words", () => {
  it("drops the market prefix from exchange codes", () => {
    expect(exchangeText("US_CBOT")).toBe("CBOT");
    expect(exchangeText("US_NASDAQ")).toBe("NASDAQ");
    expect(exchangeText(null)).toBe("");
  });

  it("names universes by their tab", () => {
    expect(universeText("US_EQUITIES")).toBe("US Equities");
    expect(universeText("US_ETFS")).toBe("ETFs");
  });

  it("reads filters as their chips do", () => {
    expect(filterText({ field: "price", operator: "gte", value: 5 }, { label: "Price", unit: "USD" })).toBe("Price ≥ $5");
    expect(filterText({ field: "short_float_pct", operator: "gt", value: 20 }, { label: "Short Float", unit: "percent" })).toBe("Short Float > 20%");
    expect(filterText({ field: "rel_volume", operator: "between", value: [1, 3] })).toBe("Rel volume 1–3");
    expect(filtersText([])).toBe("no filters");
  });

  it("joins parts without repeating one", () => {
    expect(distinctJoin(["Finviz", "snapshot", "Snapshot", null, "", "observed 14:03:38 ET"])).toBe("Finviz · snapshot · observed 14:03:38 ET");
  });
});
