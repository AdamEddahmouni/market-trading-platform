import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("ImpVela lazy route wiring", () => {
  it("lazy-loads the lab page and keeps @luxalgo/vela off App static imports", () => {
    const appPath = resolve(import.meta.dirname, "../../App.tsx");
    const routePath = resolve(import.meta.dirname, "../ModeResearchRoute.tsx");
    const appSource = readFileSync(appPath, "utf8");
    const routeSource = readFileSync(routePath, "utf8");
    expect(routeSource).toContain("ImpVelaChartLabPage");
    expect(routeSource).toMatch(/ImpVelaChartLabPage\s*=\s*lazy/);
    expect(routeSource).toContain('path="vela-chart-lab"');
    expect(appSource).toContain('path="/research/*"');
    expect(appSource).not.toContain("@luxalgo/vela");
    expect(routeSource).not.toContain("@luxalgo/vela");

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
