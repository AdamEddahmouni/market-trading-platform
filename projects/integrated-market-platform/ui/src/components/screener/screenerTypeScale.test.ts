import { describe, expect, it } from "vitest";

// Every stylesheet the Screener, its preview and its panels load.
const sheets = import.meta.glob("./**/*.css", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const MIN_PX = 11;

describe("Screener type scale", () => {
  it("reads every Screener stylesheet", () => {
    expect(Object.keys(sheets)).toEqual(expect.arrayContaining(["./screener.css", "./panels/dock.css", "./news/news.css", "./bonds/bonds.css"]));
  });

  it("sets no text smaller than 11px", () => {
    const small: string[] = [];
    for (const [file, css] of Object.entries(sheets)) {
      for (const match of css.matchAll(/font(?:-size)?:\s*(?:\d{3}\s+)?(\d+(?:\.\d+)?)px/g)) {
        if (Number(match[1]) < MIN_PX) small.push(`${file}: ${match[0]}`);
      }
    }
    expect(small).toEqual([]);
  });
});
