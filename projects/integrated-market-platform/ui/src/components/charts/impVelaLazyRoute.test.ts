import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("ImpVela lazy route wiring", () => {
  it("lazy-loads the lab page and keeps @luxalgo/vela off App static imports", () => {
    const appPath = resolve(import.meta.dirname, "../../App.tsx");
    const researchRoutePath = resolve(import.meta.dirname, "../ModeResearchRoute.tsx");
    const labRoutePath = resolve(import.meta.dirname, "../ModeLabRoute.tsx");
    const labSurfacePath = resolve(import.meta.dirname, "../lab-shared/LabSurface.tsx");
    const appSource = readFileSync(appPath, "utf8");
    const researchRouteSource = readFileSync(researchRoutePath, "utf8");
    const labRouteSource = readFileSync(labRoutePath, "utf8");
    const labSurfaceSource = readFileSync(labSurfacePath, "utf8");
    expect(labSurfaceSource).toContain("ImpVelaChartLabPage");
    expect(labSurfaceSource).toMatch(/ImpVelaChartLabPage\s*=\s*lazy/);
    expect(labRouteSource).toContain('path="chart-lab"');
    expect(researchRouteSource).toContain('path="vela-chart-lab"');
    expect(researchRouteSource).toContain('to="/lab/chart-lab"');
    expect(appSource).toContain('path="/research/*"');
    expect(appSource).toContain('path="/lab/*"');
    expect(appSource).not.toContain("@luxalgo/vela");
    expect(researchRouteSource).not.toContain("@luxalgo/vela");
    expect(labRouteSource).not.toContain("@luxalgo/vela");
    expect(labSurfaceSource).not.toContain("@luxalgo/vela");

    const workspaceChartPath = resolve(import.meta.dirname, "./WorkspacePriceChart.tsx");
    const workspaceObsPath = resolve(
      import.meta.dirname,
      "../workspace-shared/WorkspaceObservability.tsx",
    );
    const workspaceChartSource = readFileSync(workspaceChartPath, "utf8");
    const workspaceObsSource = readFileSync(workspaceObsPath, "utf8");
    expect(workspaceChartSource).toMatch(/lazy\s*\(\s*\(\)\s*=>/);
    expect(workspaceChartSource).not.toContain("@luxalgo/vela");
    expect(workspaceObsSource).not.toContain("@luxalgo/vela");
    expect(workspaceObsSource).not.toContain("ImpVelaChartAdapter");
  });
});
