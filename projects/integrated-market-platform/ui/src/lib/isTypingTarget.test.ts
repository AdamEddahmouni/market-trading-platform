import { describe, expect, it } from "vitest";
import { isTypingTarget } from "./isTypingTarget";

describe("isTypingTarget", () => {
  it("returns true for inputs, textareas, and selects", () => {
    expect(isTypingTarget(document.createElement("input"))).toBe(true);
    expect(isTypingTarget(document.createElement("textarea"))).toBe(true);
    expect(isTypingTarget(document.createElement("select"))).toBe(true);
  });

  it("returns true for contenteditable and combobox descendants", () => {
    const editable = document.createElement("div");
    editable.setAttribute("contenteditable", "true");
    expect(isTypingTarget(editable)).toBe(true);

    const combobox = document.createElement("div");
    combobox.setAttribute("role", "combobox");
    const child = document.createElement("span");
    combobox.appendChild(child);
    expect(isTypingTarget(child)).toBe(true);
  });

  it("returns false for plain buttons and the document body", () => {
    expect(isTypingTarget(document.createElement("button"))).toBe(false);
    expect(isTypingTarget(document.body)).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });
});
