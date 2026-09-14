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
    expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Markets" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Opportunity Radar" })).toBeInTheDocument();
    expect(screen.queryByText("Frozen bridges")).not.toBeInTheDocument();
  });

  it("adds mode hints and accessible labels in Demo mode", () => {
    renderNav("DEMO");
    expect(screen.getByRole("link", { name: "Markets — Frozen bridges" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Portfolio — Read-only" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Research — Replay-bound labs" })).toHaveTextContent("GATED");
  });

  it("adds Paper simulation hints", () => {
    renderNav("PAPER");
    expect(screen.getByRole("link", { name: "Portfolio — Orders history" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workspace — Decision desk" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Research — Research & model labs" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Lab/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Opportunity Radar — Discovery desk" })).toBeInTheDocument();
  });

  it("adds Live observational hints", () => {
    renderNav("LIVE");
    expect(screen.getByRole("link", { name: "Live Canary — Safety review" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Markets — Live scanner" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Opportunity Radar — Read-only monitor" })).toBeInTheDocument();
  });
});
