import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { WorkspaceModuleModeShell } from "./WorkspaceModuleModeShell";

function renderShell(mode: "DEMO" | "PAPER" | "LIVE") {
  return render(
    <MemoryRouter initialEntries={["/workspace/BIYA/squeeze"]}>
      <Routes>
        <Route
          path="/workspace/:symbol/squeeze"
          element={
            <WorkspaceModuleModeShell
              mode={mode}
              instrumentId="BIYA"
              active="squeeze"
              pageClassName="squeeze-workspace-page"
              moduleTitle="Short Squeeze Workspace"
              description="Frozen research cohort evidence."
            >
              <p>Module panel</p>
            </WorkspaceModuleModeShell>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("WorkspaceModuleModeShell", () => {
  it("renders Demo restriction note and observational badge", () => {
    renderShell("DEMO");
    expect(screen.getByRole("heading", { name: /BIYA — Short Squeeze Workspace/i })).toBeInTheDocument();
    expect(screen.getByText(/Demo is exploration only/i)).toBeInTheDocument();
    expect(screen.getByText(/Observational module/i)).toBeInTheDocument();
    expect(screen.getByText("Module panel")).toBeInTheDocument();
  });

  it("renders Paper links to overview and portfolio", () => {
    renderShell("PAPER");
    expect(screen.getByRole("link", { name: "Open workspace overview" })).toHaveAttribute(
      "href",
      "/workspace/BIYA",
    );
    expect(screen.getByRole("link", { name: "Open paper portfolio" })).toHaveAttribute(
      "href",
      "/portfolio",
    );
    expect(screen.getByText(/Paper simulation context/i)).toBeInTheDocument();
  });

  it("renders Live canary link and restriction note", () => {
    renderShell("LIVE");
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
      "href",
      "/live-canary",
    );
    expect(screen.getByText(/Live is read-only here/i)).toBeInTheDocument();
  });
});
