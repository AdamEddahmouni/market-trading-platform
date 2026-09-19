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
  it("renders the operator IA without mode hints when mode is omitted", () => {
    renderNav();
    expect(screen.getByRole("link", { name: "Command" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Radar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Portfolio" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lab" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Control" })).toBeInTheDocument();
    expect(screen.queryByText("Frozen bridges")).not.toBeInTheDocument();
  });

  it("adds mode hints and accessible labels in Demo mode", () => {
    renderNav("DEMO");
    expect(screen.getByRole("link", { name: "Radar — Replay discovery" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Portfolio — Read-only" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Research — Replay-bound evidence" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lab — Experimental workbench" })).toBeInTheDocument();
  });

  it("adds Paper simulation hints", () => {
    renderNav("PAPER");
    expect(screen.getByRole("link", { name: "Portfolio — Paper positions" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workspace — Decision desk" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lab — Experimental workbench" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Research — Evidence & validation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Radar — Candidate discovery" })).toBeInTheDocument();
  });

  it("adds Live observational hints", () => {
    renderNav("LIVE");
    expect(screen.getByRole("link", { name: "Live Canary — Safety review" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Radar — Live monitor" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Control — Platform operations" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lab — Read-only workbench" })).toBeInTheDocument();
  });

  it("does not render the removed GATED badge", () => {
    renderNav("PAPER");
    expect(screen.queryByText("GATED")).not.toBeInTheDocument();
  });
});
