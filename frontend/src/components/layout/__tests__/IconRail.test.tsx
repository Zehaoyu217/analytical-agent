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
  it("renders 7 section buttons + theme + tweaks + settings = 10 buttons", () => {
    renderRail();
    const nav = screen.getByRole("navigation", { name: /main navigation/i });
    const buttons = within(nav).getAllByRole("button");
    expect(buttons.length).toBe(10);
  });

  it("Tweaks button opens the Tweaks panel via ui-store", async () => {
    const { useUiStore } = await import("@/lib/ui-store");
    useUiStore.setState({ tweaksOpen: false });
    renderRail();
    const tweaks = screen.getByRole("button", { name: "Tweaks" });
    tweaks.click();
    expect(useUiStore.getState().tweaksOpen).toBe(true);
  });

  it("applies aria-current='page' to the active section", () => {
    useChatStore.setState({ activeSection: "skills" });
    renderRail();
    const skillsBtn = screen.getByRole("button", { name: "Skills" });
    expect(skillsBtn).toHaveAttribute("aria-current", "page");
  });

  it("clicking a section button updates activeSection in the store", () => {
    renderRail();
    fireEvent.click(screen.getByRole("button", { name: "Knowledge" }));
    expect(useChatStore.getState().activeSection).toBe("knowledge");
    fireEvent.click(screen.getByRole("button", { name: "Memory" }));
    expect(useChatStore.getState().activeSection).toBe("memory");
    fireEvent.click(screen.getByRole("button", { name: "Agents" }));
    expect(useChatStore.getState().activeSection).toBe("agents");
  });

  it("settings button opens the settings overlay", async () => {
    const { useSurfacesStore } = await import("@/lib/surfaces-store");
    useSurfacesStore.setState({ settingsOverlayOpen: false });
    renderRail();
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(useSurfacesStore.getState().settingsOverlayOpen).toBe(true);
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
