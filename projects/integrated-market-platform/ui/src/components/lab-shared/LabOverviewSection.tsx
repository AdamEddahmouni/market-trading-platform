import { Link } from "react-router-dom";
import { useResearchModelsQuery, useResearchSimulationQuery } from "../../api/hooks";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { LoadingState } from "../shared/LoadingState";
import { LabCalibrationHonesty } from "./LabCalibrationHonesty";
import { LabFactGrid } from "./LabFactGrid";
import {
  buildLabWorkflowCards,
  experimentStatusFacts,
  labEvidenceClassRows,
  labHasRunnableBackendWorkflow,
  type LabWorkflowCard,
} from "./labPresentation";

function WorkflowCard({ card }: { card: LabWorkflowCard }) {
  return (
    <article
      className="lab-workflow-card"
      data-availability={card.availability}
      aria-labelledby={`lab-workflow-${card.id}-title`}
    >
      <div className="lab-workflow-meta">
        <h3 id={`lab-workflow-${card.id}-title`}>{card.title}</h3>
        <StatePill tone={card.statusTone} label={card.availabilityLabel} raw={card.availability} />
        <StatePill tone={card.statusTone} label={card.statusLabel} raw={card.statusLabel} />
      </div>
      <p className="lab-claim">{card.purpose}</p>
      <dl className="lab-dl-compact">
        <div>
          <dt>What it tests</dt>
          <dd>{card.tests}</dd>
        </div>
        <div>
          <dt>Current status</dt>
          <dd>{card.statusDetail}</dd>
        </div>
        <div>
          <dt>Inputs / configuration</dt>
          <dd>{card.inputs}</dd>
        </div>
        <div>
          <dt>Can it be run from Lab?</dt>
          <dd>{card.runnable ? "Yes" : `No. ${card.runnableDetail}`}</dd>
        </div>
        <div>
          <dt>Evidence / result</dt>
          <dd>{card.evidence}</dd>
        </div>
        <div>
          <dt>Major limitation</dt>
          <dd>{card.limitation}</dd>
        </div>
      </dl>
      <div className="lab-actions">
        {card.labHref ? <Link to={card.labHref}>Open workbench</Link> : null}
        {card.researchHref ? (
          <Link to={card.researchHref}>View interpretation in Research</Link>
        ) : null}
      </div>
    </article>
  );
}

/**
 * Lab Overview — what can actually be done, what is read-only, and where
 * results are interpreted. Never presents a fake Run control.
 */
export function LabOverviewSection() {
  const modelsQuery = useResearchModelsQuery();
  const simulationQuery = useResearchSimulationQuery();

  if (modelsQuery.isLoading && simulationQuery.isLoading) {
    return <LoadingState label="Loading lab workbench…" />;
  }

  const modelsFailed = modelsQuery.isError && !modelsQuery.data;
  const simulationFailed = simulationQuery.isError && !simulationQuery.data;
  if (modelsFailed && simulationFailed) {
    return (
      <ErrorState
        title="Lab cannot load the current experimental snapshots."
        affects="Validation and simulation workflow status are unavailable until the research projections respond."
        rawDetail={
          modelsQuery.error instanceof Error
            ? modelsQuery.error.message
            : simulationQuery.error instanceof Error
              ? simulationQuery.error.message
              : undefined
        }
        onRetry={() => {
          void modelsQuery.refetch();
          void simulationQuery.refetch();
        }}
      />
    );
  }

  const cards = buildLabWorkflowCards({
    models: modelsQuery.data,
    modelsError: modelsQuery.isError && !modelsQuery.data,
    simulation: simulationQuery.data,
    simulationError: simulationQuery.isError && !simulationQuery.data,
  });

  return (
    <>
      <section className="lab-panel" aria-labelledby="lab-overview-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Workbench</div>
            <h2 id="lab-overview-heading">What Lab can do right now</h2>
          </div>
        </div>
        <p className="lab-claim">
          Lab inspects governed research and testing workflows. It does not grant execution
          authority, Paper submit rights, or production readiness.
        </p>
        <p className="lab-muted">
          {labHasRunnableBackendWorkflow()
            ? "A backend mutation can start a Lab workflow from this interface."
            : "No Lab backend mutation exists. Validation and simulation are inspectable snapshots. Chart Lab is local adapter tooling and is not evidence."}
        </p>
      </section>

      <section className="lab-panel" aria-labelledby="lab-experiment-status-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Experiment status</div>
            <h2 id="lab-experiment-status-heading">What is loaded versus what is UNKNOWN</h2>
          </div>
        </div>
        <LabFactGrid
          facts={experimentStatusFacts({
            models: modelsQuery.data,
            modelsError: modelsQuery.isError && !modelsQuery.data,
            simulation: simulationQuery.data,
            simulationError: simulationQuery.isError && !simulationQuery.data,
          })}
        />
      </section>

      <LabCalibrationHonesty />

      <section className="lab-panel" aria-labelledby="lab-evidence-class-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Evidence classes</div>
            <h2 id="lab-evidence-class-heading">Test versus forward-test</h2>
          </div>
        </div>
        <p className="lab-muted">
          Retrospective walk-forward and deterministic simulation stay in their own classes. Lab
          does not upgrade them to FTEP, Paper, or Live.
        </p>
        <div className="lab-table-wrap">
          <table className="data-table lab-compare-table">
            <caption className="chart-data-caption">
              Evidence-class map for Lab workflows. UNKNOWN means the contract does not carry it.
            </caption>
            <thead>
              <tr>
                <th scope="col">Workflow</th>
                <th scope="col">Evidence class</th>
                <th scope="col">Must not be read as</th>
              </tr>
            </thead>
            <tbody>
              {labEvidenceClassRows().map((row) => (
                <tr key={row.workflow}>
                  <td>{row.workflow}</td>
                  <td>{row.evidenceClass}</td>
                  <td>{row.notThis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="lab-panel" aria-labelledby="lab-workflows-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Workflows</div>
            <h2 id="lab-workflows-heading">Supported and unsupported workflows</h2>
          </div>
        </div>
        <div className="lab-workflow-grid">
          {cards.map((card) => (
            <WorkflowCard key={card.id} card={card} />
          ))}
        </div>
      </section>

      <section className="lab-panel" aria-labelledby="lab-handoff-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Research</div>
            <h2 id="lab-handoff-heading">Where completed results are interpreted</h2>
          </div>
        </div>
        <p className="lab-muted">
          Lab is the process surface. Research remains the interpretation surface for the same
          contracts.
        </p>
        <ul className="lab-gap-list">
          <li>
            Validation outcomes → <Link to="/research/validation">Research Validation</Link>
          </li>
          <li>
            Simulation ledger meaning → <Link to="/research/simulation">Research Simulation</Link>
          </li>
          <li>
            Broader findings → <Link to="/research">Research Overview</Link>
          </li>
        </ul>
      </section>
    </>
  );
}
