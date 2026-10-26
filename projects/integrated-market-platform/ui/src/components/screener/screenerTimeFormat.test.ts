import { describe, expect, it } from "vitest";

// Every Screener source file that renders (tests excluded): times go through screenerText's ET format.
const sources = import.meta.glob(["./**/*.ts", "./**/*.tsx", "!./**/*.test.ts", "!./**/*.test.tsx"],
  { query: "?raw", import: "default", eager: true }) as Record<string, string>;
// The formatter itself, and the CSV file name (a machine timestamp, never shown in the page).
const ALLOWED = new Set(["./screenerText.tsx", "./screenerCsv.ts"]);
const RAW = [
  /toLocaleTimeString\(/,
  /toLocaleDateString\(/,
  /new Date\([^;]*?\)\s*\.\s*toLocaleString\(/,
  /new Date\([^;]*?\)\s*\.\s*toISOString\(/,
];

describe("Screener time format", () => {
  it("reads the Screener sources", () => {
    expect(Object.keys(sources)).toEqual(expect.arrayContaining(["./ScreenerPage.tsx", "./screenerText.tsx", "./panels/shared.tsx"]));
  });

  it("formats no time outside the shared ET formatter", () => {
    const raw: string[] = [];
    for (const [file, text] of Object.entries(sources)) {
      if (ALLOWED.has(file)) continue;
      text.split("\n").forEach((line, index) => {
        if (RAW.some((pattern) => pattern.test(line))) raw.push(`${file}:${index + 1}: ${line.trim().slice(0, 120)}`);
      });
    }
    expect(raw).toEqual([]);
  });
});
