import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../AppShell";
import { useChatStore, type SectionId } from "@/lib/store";
import { useUiStore } from "@/lib/ui-store";

// Keep the shell test tightly scoped — stub the three heavy children so we
// can assert purely on which of them mount under each state.
vi.mock("@/components/layout/IconRail", () => ({
  IconRail: () => <nav data-testid="icon-rail">IconRail</nav>,
}));
vi.mock("../ThreadList", () => ({
  ThreadList: () => <aside data-testid="thread-list">ThreadList</aside>,
}));
vi.mock("@/components/dock/Dock", () => ({
  Dock: () => <aside data-testid="dock">Dock</aside>,
}));

function setupState(section: SectionId, threadsOpen = true, dockOpen = true) {
  useChatStore.setState({ activeSection: section });
  useUiStore.setState({
    v: 1,
    threadW: 240,
    dockW: 320,
    threadsOpen,
    dockOpen,
    dockTab: "progress",
    density: "default",
    // Mark as overridden so useAutoCollapse doesn't re-open panes
    // that the test explicitly closed.
    threadsOverridden: !threadsOpen,
    dockOverridden: !dockOpen,
  });
}

beforeEach(() => {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: 1600,
  });
});

describe("AppShell", () => {
  it("mounts IconRail, ThreadList, and Dock on the chat section", () => {
    setupState("chat");
    render(
      <AppShell>
        <div data-testid="main">main</div>
      </AppShell>,
    );
    expect(screen.getByTestId("icon-rail")).toBeInTheDocument();
    expect(screen.getByTestId("thread-list")).toBeInTheDocument();
    expect(screen.getByTestId("dock")).toBeInTheDocument();
    expect(screen.getByTestId("main")).toBeInTheDocument();
  });

  it("hides ThreadList and Dock when the section is not chat", () => {
    setupState("settings");
    render(
      <AppShell>
        <div data-testid="main">main</div>
      </AppShell>,
    );
    expect(screen.getByTestId("icon-rail")).toBeInTheDocument();
    expect(screen.queryByTestId("thread-list")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dock")).not.toBeInTheDocument();
  });

  it("respects ui-store threadsOpen / dockOpen flags within chat", () => {
    setupState("chat", false, false);
    render(
      <AppShell>
        <div data-testid="main">main</div>
      </AppShell>,
    );
    expect(screen.queryByTestId("thread-list")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dock")).not.toBeInTheDocument();
  });

  it("hides Dock when dockPosition === 'off'", () => {
    setupState("chat");
    useUiStore.setState({ dockPosition: "off" });
    render(
      <AppShell>
        <div data-testid="main">main</div>
      </AppShell>,
    );
    expect(screen.queryByTestId("dock")).not.toBeInTheDocument();
    const shell = document.querySelector("[data-app-shell]");
    expect(shell?.getAttribute("data-dock-position")).toBe("off");
  });

  it("renders Dock below main when dockPosition === 'bottom'", () => {
    setupState("chat");
    useUiStore.setState({ dockPosition: "bottom" });
    render(
      <AppShell>
        <div data-testid="main">main</div>
      </AppShell>,
    );
    const shell = document.querySelector("[data-app-shell]");
    expect(shell?.getAttribute("data-dock-position")).toBe("bottom");
    expect(screen.getByTestId("dock")).toBeInTheDocument();
  });
});
