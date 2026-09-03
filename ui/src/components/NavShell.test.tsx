import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { NavShell } from "./NavShell";

function renderNav(mode?: "DEMO" | "PAPER" | "LIVE") {
  return render(
    <MemoryRouter>
      <NavShell mode={mode} />
    </MemoryRouter>,
  );
}

describe("NavShell", () => {
  it("renders primary navigation links without mode hints when mode is omitted", () => {
    renderNav();
    expect(screen.getByRole("link", { name: "NOW" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "EXPLORE" })).toBeInTheDocument();
    expect(screen.queryByText("Frozen bridges")).not.toBeInTheDocument();
  });

  it("adds mode hints and accessible labels in Demo mode", () => {
    renderNav("DEMO");
    expect(screen.getByRole("link", { name: "EXPLORE — Frozen bridges" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "PORTFOLIO — Read-only" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "RESEARCH — Replay-bound" })).toHaveTextContent("GATED");
  });

  it("adds Paper simulation hints", () => {
    renderNav("PAPER");
    expect(screen.getByRole("link", { name: "PORTFOLIO — Simulation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "WORKSPACE — Simulation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "DISCOVER — Discovery desk" })).toBeInTheDocument();
  });

  it("adds Live observational hints", () => {
    renderNav("LIVE");
    expect(screen.getByRole("link", { name: "LIVE CANARY — Safety review" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "EXPLORE — Live scanner" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "DISCOVER — Read-only monitor" })).toBeInTheDocument();
  });
});
