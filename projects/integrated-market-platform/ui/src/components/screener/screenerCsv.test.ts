import { describe, expect, it } from "vitest";
import { csvFileName, csvText } from "./screenerCsv";

describe("screenerCsv", () => {
  it("writes headers, raw numbers and blank cells for missing values", () => {
    expect(csvText(["Symbol", "Price", "Bid"], [["SPY", 512.34, null], ["QQQ", 440, undefined]]))
      .toBe("Symbol,Price,Bid\r\nSPY,512.34,\r\nQQQ,440,\r\n");
  });

  it("quotes commas, quotes and line breaks", () => {
    expect(csvText(["Company"], [['Acme, "Inc"'], ["two\nlines"]]))
      .toBe('Company\r\n"Acme, ""Inc"""\r\n"two\nlines"\r\n');
  });

  it("neutralises text a spreadsheet would run as a formula, but keeps negative numbers", () => {
    expect(csvText(["Company", "Chg %"], [["=HYPERLINK(1)", -1.5]])).toBe("Company,Chg %\r\n'=HYPERLINK(1),-1.5\r\n");
  });

  it("names the file by universe and UTC minute", () => {
    expect(csvFileName("US_EQUITIES", new Date("2026-10-01T06:45:30Z"))).toBe("screener-us-equities-20261001-0645Z.csv");
  });
});
