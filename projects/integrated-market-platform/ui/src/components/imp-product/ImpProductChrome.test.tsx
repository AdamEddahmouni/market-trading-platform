import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImpProductChrome } from "./ImpProductChrome";

vi.mock("../../api/hooks", () => ({
  usePaperPortfolioQuery: () => ({ data: undefined }),
}));

function stubMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function renderChrome() {
  return render(
    <MemoryRouter>
      <ImpProductChrome mode="DEMO" onSwitchMode={() => undefined} topStack={<div>stack</div>}>
        <main id="imp-main-content" tabIndex={-1}>
          Workstation
        </main>
      </ImpProductChrome>
    </MemoryRouter>,
  );
}

describe("ImpProductChrome", () => {
  beforeEach(() => {
    stubMatchMedia(false);
  });

  it("exposes a skip link, Live-off posture, and the keyboard hint", () => {
    renderChrome();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#imp-main-content",
    );
    expect(screen.getByLabelText("Execution posture")).toHaveTextContent("Live off");
    expect(screen.getByRole("button", { name: "Keyboard shortcuts" })).toBeInTheDocument();
  });

  it("opens keyboard shortcuts from ? and the header control, then closes on Escape", () => {
    renderChrome();
    fireEvent.keyDown(window, { key: "?" });
    const dialog = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    expect(within(dialog).getByRole("row", { name: /Ctrl\/Cmd\+K/ })).toBeInTheDocument();
    expect(within(dialog).getByRole("row", { name: /^\/ / })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));
    expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
  });

  it("focuses command search from / and Ctrl+K, and ignores those keys while typing", () => {
    renderChrome();
    fireEvent.keyDown(window, { key: "/" });
    expect(screen.getByRole("searchbox")).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("searchbox"), { key: "/" });
    expect(screen.getByRole("searchbox")).toHaveFocus();

    screen.getByRole("searchbox").blur();
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(screen.getByRole("searchbox")).toHaveFocus();
  });

  it("offers local destinations from command search", () => {
    renderChrome();
    const search = screen.getByRole("searchbox");
    fireEvent.focus(search);
    expect(screen.getByRole("option", { name: /Radar/ })).toBeInTheDocument();
    fireEvent.keyDown(search, { key: "ArrowDown" });
    expect(screen.getByRole("option", { name: /Radar/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("option", { name: /Workspace/ })).toHaveAttribute("aria-selected", "false");
    fireEvent.keyDown(search, { key: "Escape" });
    expect(screen.queryByRole("listbox", { name: "Command destinations" })).not.toBeInTheDocument();
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: "portfolio" } });

    expect(screen.getByRole("option", { name: /Portfolio/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Workspace/ })).not.toBeInTheDocument();
  });

  it("does not open shortcuts from a select", () => {
    renderChrome();
    const select = document.createElement("select");
    document.body.appendChild(select);
    fireEvent.keyDown(select, { key: "?" });
    expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).not.toBeInTheDocument();
    select.remove();
  });
});

describe("ImpProductChrome mobile navigation", () => {
  beforeEach(() => {
    stubMatchMedia(true);
  });

  it("opens a modal menu, traps focus, and closes on Escape", () => {
    renderChrome();
    const menu = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(menu);

    const dialog = screen.getByRole("dialog", { name: "Product navigation" });
    const close = within(dialog).getByRole("button", { name: "Close menu" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    const links = within(dialog).getAllByRole("link");
    expect(links[links.length - 1]).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Product navigation" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Menu" })).toHaveFocus();
  });

  it("keeps the dimming backdrop out of the accessibility tree while the menu is open", () => {
    renderChrome();
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    expect(screen.getByRole("dialog", { name: "Product navigation" })).toBeInTheDocument();
    const unnamedButtons = screen.queryAllByRole("button").filter((button) => !button.textContent?.trim());
    expect(unnamedButtons).toHaveLength(0);
    expect(document.querySelector(".imp-sidebar-backdrop")).toHaveAttribute("aria-hidden", "true");
  });
});
