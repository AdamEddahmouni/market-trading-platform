import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function readUi(relativePath: string): string {
  return readFileSync(resolve(import.meta.dirname, relativePath), "utf8");
}

describe("Lab accessibility polish contract", () => {
  const labCss = readUi("../../styles/lab.css");
  const chartLabCss = readUi("../../styles/imp-vela-chart-lab.css");
  const linkTabsCss = readUi("../imp-ui/imp-ui.css");
  const chartLabPage = readUi("../charts/ImpVelaChartLabPage.tsx");
  const labSurface = readUi("./LabSurface.tsx");
  const researchRoute = readUi("../ModeResearchRoute.tsx");

  it("keeps Chart Lab tick/backfill controls at the 44px touch floor", () => {
    expect(chartLabCss).toContain(".imp-vela-chart-lab-controls button");
    expect(chartLabCss).toMatch(
      /\.imp-vela-chart-lab-controls button \{[\s\S]*?min-height: 44px;/,
    );
  });

  it("raises Lab muted/meta copy to --imp-text-md without changing the global sm token", () => {
    const tokens = readUi("../../styles/tokens.css");
    expect(tokens).toContain("--imp-text-sm: 0.8125rem;");
    expect(tokens).toContain("--imp-text-md: 0.875rem;");
    expect(labCss).toMatch(/\.lab-muted \{[\s\S]*?font-size: var\(--imp-text-md\);/);
    expect(chartLabCss).toMatch(
      /\.imp-vela-chart-lab-meta \{[\s\S]*?font-size: var\(--imp-text-md/,
    );
  });

  it("keeps LinkTabs at the 44px floor, including the BP_SM mobile rule", () => {
    expect(linkTabsCss).toMatch(/\.imp-ui-link-tab \{[\s\S]*?min-height: 44px;/);
    expect(linkTabsCss).toContain("@media (max-width: 720px)");
    expect(labSurface).toContain("LinkTabs");
  });

  it("demotes the inner Chart Lab heading so the playground h2 is unique", () => {
    expect(labSurface).toContain('<h2 id="lab-chart-heading">Chart adapter playground</h2>');
    expect(chartLabPage).toContain("<h3 id=\"imp-vela-lab-title\">Vela chart adapter (Lane F)</h3>");
    expect(chartLabPage).not.toMatch(/<h2[^>]*>Vela chart adapter/);
    expect(chartLabCss).toContain(".imp-vela-chart-lab-header h3");
    expect(chartLabCss).not.toContain(".imp-vela-chart-lab-header h1");
  });

  it("keeps the historical Research Chart Lab path as a redirect to /lab/chart-lab", () => {
    expect(researchRoute).toContain('path="vela-chart-lab"');
    expect(researchRoute).toContain('to="/lab/chart-lab"');
    expect(researchRoute).toContain("Navigate");
  });
});
