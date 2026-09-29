import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CongressViewSchema, type CongressTransaction } from "../../../api/screenerParticipants";
import { CongressTable, stateText } from "./participantFormat";
import { Congressional, Holdings13F } from "./sections";

/** S14: 13F index freshness, chamber source coverage, and canonical member identity on the existing S12 surfaces. */
const amount = { min_amount: 1001, max_amount: 15000, display: "$1,001 – $15,000", exact_value_disclosed: false as const };
const row = (id: string, member: Record<string, unknown>, chamber = "HOUSE"): CongressTransaction => ({
  id, chamber, member: { name: "Josh Gottheimer", state_district: "NJ05", member_id: "HOUSE:GOTTHEIMER:JOSH:NJ05", ...member },
  owner: "SELF", asset_description: "Apple Inc. (AAPL) [ST]", asset_type_code: "ST", disclosed_ticker: "AAPL", transaction_type: "PURCHASE",
  transaction_date: "2026-09-01", notification_date: null, filing_date: "2026-09-14", available_at: "2026-09-15T03:59:59Z",
  available_basis: "house_index.filing_date_end_of_et_day", retrieved_at: "2026-09-28T14:00:00Z", amount, disclosure_lag_days: 13,
  source_url: "https://disclosures-clerk.house.gov/x.pdf", quality_flags: [],
});
const index = { managed: true, refresh_state: "REFRESH_AVAILABLE", refresh_reason: "NEWER_SEC_DATASET_PUBLISHED",
  indexed_through: "2026-08-31", generated_at: "2026-09-02T10:00:00Z", source_dataset_count: 2 };

describe("S14 13F index status", () => {
  it("states what the index holds and whether a newer data set exists, never liveness", () => {
    render(<Holdings13F compact={false} section={{ state: "CURRENT_AS_FILED", reason: null, period: "2026-06-30", holder_count: 3,
      change_counts: {}, holders: [], index }} />);
    const status = screen.getByLabelText("13F index status");
    expect(status).toHaveTextContent("13F index: data sets indexed through 2026-08-31 (2 data sets) · generated 2026-09-02 10:00 UTC · refresh: update available.");
    expect(status).toHaveAttribute("title", "A newer SEC data set is published");
    expect(status.textContent).not.toMatch(/\blive\b/i);
    expect(document.body.textContent).toContain("is not a live position");   // the S12 boundary text stays
  });

  it("keeps the compact preview to one line", () => {
    render(<Holdings13F compact section={{ state: "CURRENT_AS_FILED", reason: null, index: { ...index, refresh_state: "CURRENT_AS_FILED" } }} />);
    expect(screen.getByText("13F data sets indexed through 2026-08-31 · current for published SEC data sets.")).toBeInTheDocument();
    expect(screen.queryByLabelText("13F index status")).toBeNull();
  });

  it("explains a refreshing or invalid index as a source state", () => {
    render(<Holdings13F compact={false} section={{ state: "INDEX_INVALID", reason: "INDEX_SIZE_MISMATCH", index: { refresh_state: "INDEX_INVALID" } }} />);
    const section = screen.getByRole("region", { name: "13F holdings (quarter-end)" });
    expect(section).toHaveTextContent("Index invalid");
    expect(section).toHaveTextContent("this is a source state, not an absence of disclosures");
    expect(stateText("REFRESHING")).toBe("Refreshing");
  });
});

describe("S14 congressional coverage and identity", () => {
  const sources = [{ id: "house_ptr", chamber: "HOUSE", state: "PUBLICATION_CURRENT", reason: null },
    { id: "senate_efd", chamber: "SENATE", state: "TERMS_ACCEPTANCE_REQUIRED", reason: "SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE" }];

  it("shows each chamber's own state and only actual counts", () => {
    render(<Congressional compact={false} section={{ state: "NO_DISCLOSURES", reason: "NO_DISCLOSED_TRANSACTIONS", window_days: 90,
      transactions: [], chambers: ["HOUSE"], sources, coverage: { house: { parsed: 116, scanned_unparsed: 20, partially_parsed: 0, failed: 0, loading: 0 } } }} />);
    const list = screen.getByRole("list", { name: "Congressional source coverage" });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual(["House · Current publication · 116 parsed · 20 scanned/unparsed",
      "Senate · Terms acceptance required"]);
    expect(items[1]).toHaveAttribute("title", "Senate eFD needs the operator to accept its terms and import reports");
    expect(screen.getByText("No House transactions disclosing this ticker were filed in the last 90 days.")).toBeInTheDocument();
  });

  it("notes an unavailable chamber in the compact preview", () => {
    render(<Congressional compact section={{ state: "PUBLICATION_CURRENT", reason: null, window_days: 90, sources,
      transactions: [row("h1", { source_name: "Josh Mr Gottheimer", resolution: "SEAT_AND_NAME" })] }} />);
    expect(screen.getByText("House: current publication · Senate: terms acceptance required")).toBeInTheDocument();
    expect(screen.getByText(/Josh Gottheimer · purchase/)).toHaveAttribute("title", expect.stringContaining("Filed as: Josh Mr Gottheimer"));
  });

  it("shows the canonical name and keeps the filed spelling in provenance", () => {
    render(<CongressTable caption="rows" rows={[
      row("h1", { source_name: "Josh Mr Gottheimer", canonical_member_id: "HOUSE-SEAT:NJ05:GOTTHEIMER:JOSH", resolution: "SEAT_AND_NAME",
        basis: "SAME_HOUSE_SEAT_SAME_GIVEN_SURNAME_SUFFIX" }),
      row("h2", { source_name: "Josh Gottheimer", resolution: "SEAT_AND_NAME" }),
      row("s1", { name: "Jane Q Example", source_name: "Jane Q Example", state_district: "", resolution: "UNRESOLVED" }, "SENATE"),
    ]} />);
    const [, first, second, senate] = screen.getAllByRole("row");
    const cell = within(first).getByText("Josh Gottheimer").closest("td");
    expect(cell).toHaveTextContent("Josh Gottheimer (NJ05)");
    expect(cell).toHaveAttribute("title", "Filed as: Josh Mr Gottheimer · Identity: seat and name (same house seat same given surname suffix)");
    expect(within(second).getByText("Josh Gottheimer").closest("td")?.getAttribute("title")).not.toContain("Filed as");
    expect(senate).toHaveTextContent("Jane Q Example (Senate)");
  });

  it("parses an S14 congress view with canonical identity and per-chamber coverage", () => {
    const view = {
      schema_version: "screener-participants/1.0.0", generated_at: "2026-09-28T14:00:00Z", universe: "US_EQUITIES", view: "congress",
      window: { id: "60d", days: 60, since: "2026-07-30", basis: "FILING_DATE" }, state: "PUBLICATION_CURRENT", reason: null,
      providers: [], sorts: [], sort: "filed",
      filters: { transaction_types: [], amount_floors: [], applied: { transaction_type: null, min_amount: null, member: null },
        members: [{ id: "HOUSE-SEAT:NJ05:GOTTHEIMER:JOSH", name: "Josh Gottheimer", state_district: "NJ05", chamber: "HOUSE",
          filed_as: ["Josh Gottheimer", "Josh Mr Gottheimer"], resolution: "SEAT_AND_NAME" }] },
      rows: [row("h1", { source_name: "Josh Mr Gottheimer", canonical_member_id: "HOUSE-SEAT:NJ05:GOTTHEIMER:JOSH", aliases: ["a", "b"] })],
      result_count: 1, offset: 0, limit: 100, has_more: false, coverage: { chambers: ["HOUSE", "SENATE"] },
      boundaries: [], time_note: "", neutrality_note: "",
    };
    const parsed = CongressViewSchema.parse(view);
    expect(parsed.filters.members[0].filed_as).toEqual(["Josh Gottheimer", "Josh Mr Gottheimer"]);
    expect(parsed.rows[0].member.source_name).toBe("Josh Mr Gottheimer");
  });
});
