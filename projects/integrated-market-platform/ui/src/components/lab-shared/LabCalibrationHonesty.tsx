import { Link } from "react-router-dom";
import { useOperatorDiagnosticsQuery } from "../../api/hooks";
import { StatePill } from "../imp-ui/StatePill";
import { LabFactGrid, LabWarningList } from "./LabFactGrid";
import { labAuthorityHonestyFacts, labAuthorityHonestyWarnings } from "./labPresentation";

/**
 * Item 9 / Live / Full30 honesty for Lab. Diagnostics are read-only.
 * This panel never offers calibrate, collect, or Full30 actions.
 */
export function LabCalibrationHonesty() {
  const diagnosticsQuery = useOperatorDiagnosticsQuery();
  const diagnostics = diagnosticsQuery.data;
  const diagnosticsError = diagnosticsQuery.isError && !diagnosticsQuery.data;
  const facts = labAuthorityHonestyFacts({
    diagnostics,
    diagnosticsError,
  });
  const dateGate = facts.find((row) => row.label === "Item 9 date-gate truth class")?.value;
  const calibration = facts.find((row) => row.label === "Item 9 calibration")?.value;
  const live = facts.find((row) => row.label === "Live real-money execution")?.value;

  return (
    <section className="lab-panel" aria-labelledby="lab-calibration-honesty-heading">
      <div className="lab-panel-heading">
        <div>
          <div className="lab-panel-kicker">Calibration gates</div>
          <h2 id="lab-calibration-honesty-heading">Item 9, Live, and what Lab is not</h2>
        </div>
      </div>
      {diagnosticsQuery.isLoading ? (
        <p className="lab-muted" role="status">
          Loading operator diagnostics… a load wait is not an Item 9 calendar wait.
        </p>
      ) : null}
      <div className="lab-trust-row">
        {dateGate ? <StatePill tone="neutral" label={dateGate} raw={dateGate} /> : null}
        {calibration ? (
          <StatePill tone="caution" label={calibration} raw={calibration} />
        ) : null}
        {live ? <StatePill tone="neutral" label={live} raw={live} /> : null}
        <StatePill tone="neutral" label="Lab inspect-only" raw="inspectable" />
      </div>
      <LabWarningList warnings={labAuthorityHonestyWarnings({ diagnostics, diagnosticsError })} />
      <LabFactGrid facts={facts} />
      <p className="lab-muted">
        Canonical operator truth lives on <Link to="/control">Control</Link>. Lab does not
        start collection, fit calibration, enable Live, or run Full30.
      </p>
    </section>
  );
}
