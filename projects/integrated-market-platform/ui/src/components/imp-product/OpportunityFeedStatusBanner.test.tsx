import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { OpportunityFeedStatusBanner } from "./OpportunityFeedStatusBanner";

describe("OpportunityFeedStatusBanner", () => {
  it("announces loading without fabricating rows", () => {
    render(
      <MemoryRouter>
        <OpportunityFeedStatusBanner state="loading" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/loading ranked opportunities/i);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("alerts when ranking is unavailable", () => {
    render(
      <MemoryRouter>
        <OpportunityFeedStatusBanner state="error" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/opportunity ranking unavailable/i);
  });

  it("points UNREADY radar at Control Center", () => {
    render(
      <MemoryRouter>
        <OpportunityFeedStatusBanner
          state="ready"
          feedStatus="UNREADY"
          unreadyReason="QUALITY_SUMMARY_NOT_HEALTHY"
          nextAction="/control"
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/radar unready/i);
    expect(screen.getByRole("status")).toHaveTextContent("QUALITY_SUMMARY_NOT_HEALTHY");
    expect(screen.getByRole("link", { name: "Open Control Center" })).toHaveAttribute(
      "href",
      "/control",
    );
  });

  it("renders nothing when the feed is ready", () => {
    const { container } = render(
      <MemoryRouter>
        <OpportunityFeedStatusBanner state="ready" feedStatus="READY" />
      </MemoryRouter>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
