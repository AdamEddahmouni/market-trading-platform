import { useState } from "react";
import {
  useResearchAnalyticsQuery,
  useResearchModelsQuery,
  useResearchSimulationQuery,
} from "../api/hooks";
import { ModelLabPanel } from "./research/ModelLabPanel";
import { ResearchAnalyticsPanel } from "./research/ResearchAnalyticsPanel";
import { SimulationLabPanel } from "./research/SimulationLabPanel";

type ResearchTab = "analytics" | "models" | "simulation";

export function ResearchPage() {
  const [tab, setTab] = useState<ResearchTab>("analytics");
  const analyticsQuery = useResearchAnalyticsQuery();
  const modelsQuery = useResearchModelsQuery();
  const simulationQuery = useResearchSimulationQuery();

  const loading =
    (tab === "analytics" && analyticsQuery.isLoading) ||
    (tab === "models" && modelsQuery.isLoading) ||
    (tab === "simulation" && simulationQuery.isLoading);

  if (loading) {
    return <div className="app-loading">Loading research surface…</div>;
  }

  return (
    <section className="page research-page">
      <header className="page-header">
        <h1>RESEARCH</h1>
        <p>Replay-bound research projections. No trade authority.</p>
      </header>

      <div className="research-tabs" role="tablist" aria-label="Research sections">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "analytics"}
          className={tab === "analytics" ? "active" : undefined}
          onClick={() => setTab("analytics")}
        >
          Analytics
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "models"}
          className={tab === "models" ? "active" : undefined}
          onClick={() => setTab("models")}
        >
          Model Lab
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "simulation"}
          className={tab === "simulation" ? "active" : undefined}
          onClick={() => setTab("simulation")}
        >
          Simulation
        </button>
      </div>

      {tab === "analytics" ? (
        analyticsQuery.data ? (
          <>
            <p className="research-meta">
              Epistemic class: {analyticsQuery.data.epistemic_class} · Boundary:{" "}
              {analyticsQuery.data.authority_boundary}
            </p>
            <p>{analyticsQuery.data.disclaimer}</p>
            <ResearchAnalyticsPanel payload={analyticsQuery.data} />
          </>
        ) : (
          <p>Research analytics unavailable.</p>
        )
      ) : null}

      {tab === "models" ? (
        modelsQuery.data ? <ModelLabPanel payload={modelsQuery.data} /> : <p>Model Lab unavailable.</p>
      ) : null}

      {tab === "simulation" ? (
        simulationQuery.data ? (
          <SimulationLabPanel payload={simulationQuery.data} />
        ) : (
          <p>Simulation Lab unavailable.</p>
        )
      ) : null}
    </section>
  );
}
