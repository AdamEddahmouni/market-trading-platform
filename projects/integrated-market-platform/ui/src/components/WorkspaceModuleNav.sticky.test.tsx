import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { WorkspaceModuleNav } from "./WorkspaceModuleNav";

describe("WorkspaceModuleNav", () => {
  it("marks the active lane with aria-current and sticky wrapper", () => {
    const { container } = render(
      <MemoryRouter>
        <WorkspaceModuleNav instrumentId="BIYA" active="squeeze" />
      </MemoryRouter>,
    );
    expect(container.querySelector(".workspace-module-nav-sticky")).toBeTruthy();
    const active = screen.getByRole("link", { name: "Short Squeeze" });
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active.className).toContain("active");
  });
});
