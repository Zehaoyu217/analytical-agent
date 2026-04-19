import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { IconRail } from "../IconRail";
import { ThemeProvider } from "../ThemeProvider";
import { useChatStore } from "@/lib/store";

function renderRail() {
  return render(
    <ThemeProvider>
      <IconRail />
    </ThemeProvider>,
  );
}

function clearThemeStorage(): void {
  window.localStorage.removeItem("ds:theme");
  window.localStorage.removeItem("theme");
  delete document.documentElement.dataset.theme;
  document.documentElement.classList.remove("light");
}

beforeEach(() => {
  useChatStore.setState({ activeSection: "chat" });
  clearThemeStorage();
});

describe("IconRail", () => {
  it("renders 9 section buttons + theme toggle + settings = 11 buttons", () => {
    renderRail();
    const nav = screen.getByRole("navigation", { name: /main navigation/i });
    const buttons = within(nav).getAllByRole("button");
    expect(buttons.length).toBe(11);
  });

  it("applies aria-current='page' to the active section", () => {
    useChatStore.setState({ activeSection: "skills" });
    renderRail();
    const skillsBtn = screen.getByRole("button", { name: "Skills" });
    expect(skillsBtn).toHaveAttribute("aria-current", "page");
  });

  it("clicking a section button updates activeSection in the store", () => {
    renderRail();
    fireEvent.click(screen.getByRole("button", { name: "Graph" }));
    expect(useChatStore.getState().activeSection).toBe("graph");
    fireEvent.click(screen.getByRole("button", { name: "Digest" }));
    expect(useChatStore.getState().activeSection).toBe("digest");
    fireEvent.click(screen.getByRole("button", { name: "Ingest" }));
    expect(useChatStore.getState().activeSection).toBe("ingest");
  });

  it("settings button routes to the settings section", () => {
    renderRail();
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(useChatStore.getState().activeSection).toBe("settings");
  });

  it("theme toggle flips between light and dark", () => {
    // Pin theme to light via storage so the assertion is deterministic
    // regardless of the provider's default resolution.
    window.localStorage.setItem("theme", "light");
    window.localStorage.setItem("ds:theme", "light");
    renderRail();
    const toggle = screen.getByRole("button", { name: /dark mode/i });
    fireEvent.click(toggle);
    expect(
      screen.getByRole("button", { name: /light mode/i }),
    ).toBeInTheDocument();
  });

  it("renders the rail at 52px wide per handoff spec", () => {
    renderRail();
    const nav = screen.getByRole("navigation", { name: /main navigation/i });
    expect(nav.className).toMatch(/w-\[52px\]/);
  });
});
