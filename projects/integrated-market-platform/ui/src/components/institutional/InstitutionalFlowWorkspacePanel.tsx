import { Link } from "react-router-dom";
import type { WorkspaceInstitutionalFlowResponse } from "../../api/schemas";
import { CatalystWorkspacePanel } from "../catalyst/CatalystWorkspacePanel";
import { DisclosureWorkspacePanel } from "../disclosure/DisclosureWorkspacePanel";
import { FundEtfWorkspacePanel } from "../fundetf/FundEtfWorkspacePanel";
import { FuturesWorkspacePanel } from "../futures/FuturesWorkspacePanel";
import { LargeTransactionsWorkspacePanel } from "../largetransactions/LargeTransactionsWorkspacePanel";
import { OptionsWorkspacePanel } from "../options/OptionsWorkspacePanel";
import { OrderBookWorkspacePanel } from "../orderbook/OrderBookWorkspacePanel";
import { OrderFlowWorkspacePanel } from "../orderflow/OrderFlowWorkspacePanel";
import {
  useWorkspaceCatalystQuery,
  useWorkspaceDisclosureQuery,
  useWorkspaceFundEtfQuery,
  useWorkspaceFuturesQuery,
  useWorkspaceLargeTransactionsQuery,
  useWorkspaceOptionsQuery,
  useWorkspaceOrderBookQuery,
  useWorkspaceOrderFlowQuery,
} from "../../api/hooks";
import { useMemo, useState } from "react";

type Props = {
  instrumentId: string;
  payload: WorkspaceInstitutionalFlowResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

function FamilyStatusRow({
  family,
  onExplain,
}: {
  family: WorkspaceInstitutionalFlowResponse["families"][number];
  onExplain?: (ref: string) => void;
}) {
  return (
    <tr>
      <td>{family.label}</td>
      <td>{family.entitled_symbol}</td>
      <td>{family.available ? "AVAILABLE" : "UNAVAILABLE"}</td>
      <td>{family.reason ?? "—"}</td>
      <td>
        <Link to={family.route_path}>Open</Link>
        {onExplain ? (
          <>
            {" · "}
            <button type="button" className="link-button" onClick={() => onExplain(family.explanation_ref)}>
              Explain
            </button>
          </>
        ) : null}
      </td>
    </tr>
  );
}

export function InstitutionalFlowWorkspacePanel({
  instrumentId,
  payload,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  const families = payload?.families ?? [];
  const [activeFamily, setActiveFamily] = useState(families[0]?.family_id ?? "");
  const selectedFamily = families.some((family) => family.family_id === activeFamily)
    ? activeFamily
    : families[0]?.family_id ?? "";
  const familySymbol = (familyId: string) =>
    families.find((family) => family.family_id === familyId)?.entitled_symbol ?? "";

  const disclosureSymbol = familySymbol("regulatory_disclosure");
  const orderFlowSymbol = familySymbol("order_flow");
  const orderBookSymbol = familySymbol("order_book");
  const optionsSymbol = familySymbol("options");
  const largeTxnSymbol = familySymbol("large_transactions");
  const futuresSymbol =
    familySymbol("futures_depth") || familySymbol("futures_positioning");
  const catalystSymbol = familySymbol("public_catalyst");
  const fundEtfSymbol = familySymbol("fund_etf_cross_asset");

  const disclosureQuery = useWorkspaceDisclosureQuery(disclosureSymbol);
  const orderFlowQuery = useWorkspaceOrderFlowQuery(orderFlowSymbol);
  const orderBookQuery = useWorkspaceOrderBookQuery(orderBookSymbol);
  const optionsQuery = useWorkspaceOptionsQuery(optionsSymbol);
  const largeTxnQuery = useWorkspaceLargeTransactionsQuery(largeTxnSymbol);
  const futuresQuery = useWorkspaceFuturesQuery(futuresSymbol);
  const catalystQuery = useWorkspaceCatalystQuery(catalystSymbol);
  const fundEtfQuery = useWorkspaceFundEtfQuery(fundEtfSymbol);

  const activeLabel = useMemo(
    () => families.find((row) => row.family_id === selectedFamily)?.label ?? selectedFamily,
    [selectedFamily, families],
  );

  if (loading) {
    return <div className="app-loading">Loading institutional flow…</div>;
  }

  if (!payload) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Institutional Flow</h2>
        <p>UNAVAILABLE — aggregator payload missing.</p>
      </aside>
    );
  }

  if (!families.length) {
    return (
      <aside className="capability-panel unavailable" data-instrument-id={instrumentId || undefined}>
        <h2>Institutional Flow</h2>
        <p>No entitled institutional-flow family is available.</p>
      </aside>
    );
  }

  return (
    <section className="institutional-flow-panel">
      <header className="panel-header">
        <h2>Institutional Flow</h2>
        <p>{payload.disclaimer}</p>
        <p className="workspace-hint">
          {payload.available_family_count} of {payload.family_count} families available at replay cutoff.
        </p>
      </header>

      <div className="research-tabs" role="tablist" aria-label="Institutional flow families">
        {families.map((family) => (
          <button
            key={family.family_id}
            type="button"
            role="tab"
            aria-selected={selectedFamily === family.family_id}
            className={selectedFamily === family.family_id ? "active" : undefined}
            onClick={() => setActiveFamily(family.family_id)}
          >
            {family.label}
            {!family.available ? " ⊘" : ""}
          </button>
        ))}
      </div>

      <table className="data-table compact-table">
        <thead>
          <tr>
            <th>Family</th>
            <th>Entitled symbol</th>
            <th>State</th>
            <th>Reason</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {families.map((family) => (
            <FamilyStatusRow key={family.family_id} family={family} onExplain={onExplain} />
          ))}
        </tbody>
      </table>

      <section className="institutional-family-detail" aria-label={`${activeLabel} detail`}>
        <h3>{activeLabel}</h3>
        {selectedFamily === "regulatory_disclosure" ? (
          <DisclosureWorkspacePanel
            instrumentId={disclosureSymbol}
            disclosure={disclosureQuery.data ?? null}
            loading={disclosureQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
        {selectedFamily === "order_flow" ? (
          <OrderFlowWorkspacePanel
            instrumentId={orderFlowSymbol}
            orderFlow={orderFlowQuery.data ?? null}
            loading={orderFlowQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
        {selectedFamily === "order_book" ? (
          <OrderBookWorkspacePanel
            instrumentId={orderBookSymbol}
            orderBook={orderBookQuery.data ?? null}
            loading={orderBookQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
        {selectedFamily === "options" ? (
          <OptionsWorkspacePanel
            instrumentId={optionsSymbol}
            options={optionsQuery.data ?? null}
            loading={optionsQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
        {selectedFamily === "large_transactions" ? (
          <LargeTransactionsWorkspacePanel
            instrumentId={largeTxnSymbol}
            largeTransactions={largeTxnQuery.data ?? null}
            loading={largeTxnQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
        {selectedFamily === "futures_positioning" ? (
          <FuturesWorkspacePanel
            instrumentId={futuresSymbol}
            futures={futuresQuery.data ?? null}
            loading={futuresQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
        {selectedFamily === "public_catalyst" ? (
          <CatalystWorkspacePanel
            instrumentId={catalystSymbol}
            catalyst={catalystQuery.data ?? null}
            loading={catalystQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
        {selectedFamily === "fund_etf_cross_asset" ? (
          <FundEtfWorkspacePanel
            instrumentId={fundEtfSymbol}
            fundEtf={fundEtfQuery.data ?? null}
            loading={fundEtfQuery.isLoading}
            onExplain={onExplain}
            onInspect={onInspect}
          />
        ) : null}
      </section>
    </section>
  );
}
