import { ResearchObservability } from "../research-shared/ResearchObservability";

export function PaperResearchPage() {
  return (
    <section className="page research-page paper-research-page">
      <header className="paper-research-header">
        <div>
          <span className="paper-eyebrow">Paper · Research to simulation</span>
          <h1>Research</h1>
          <p>
            Replay-bound analytics, model manifests, and deterministic simulation output. Use findings to
            inform paper order previews — research itself does not place orders.
          </p>
        </div>
      </header>

      <ResearchObservability defaultTab="simulation" />
    </section>
  );
}
