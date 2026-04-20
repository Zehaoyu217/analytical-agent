import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { SECTION_SHORTCUTS, ShortcutWiring } from "../App";
import { CommandRegistryProvider } from "@/hooks/useCommandRegistry";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { useChatStore } from "@/lib/store";
import { useUiStore } from "@/lib/ui-store";

function mount() {
  return render(
    <ThemeProvider>
      <CommandRegistryProvider>
        <ShortcutWiring />
      </CommandRegistryProvider>
    </ThemeProvider>,
  );
}

function fireBoth(key: string, modifiers: { shift?: boolean } = {}) {
  // The command matcher treats `mod` as metaKey OR ctrlKey. Fire both so
  // the test is host-agnostic; the mismatched one is a no-op.
  act(() => {
    document.dispatchEvent(
      new KeyboardEvent("keydown", {
        key,
        metaKey: true,
        shiftKey: !!modifiers.shift,
        bubbles: true,
      }),
    );
    document.dispatchEvent(
      new KeyboardEvent("keydown", {
        key,
        ctrlKey: true,
        shiftKey: !!modifiers.shift,
        bubbles: true,
      }),
    );
  });
}

beforeEach(() => {
  useChatStore.setState({ activeSection: "chat" });
  useUiStore.setState({ dockOpen: true, dockOverridden: false });
});

describe("ShortcutWiring", () => {
  it("registers one OPEN_SECTION_* command per rail section", () => {
    expect(SECTION_SHORTCUTS).toHaveLength(7);
    const keys = SECTION_SHORTCUTS.map((s) => s.key);
    expect(new Set(keys).size).toBe(7); // all unique
    expect(keys).toEqual([
      "mod+shift+1",
      "mod+shift+2",
      "mod+shift+3",
      "mod+shift+4",
      "mod+shift+5",
      "mod+shift+6",
      "mod+shift+7",
    ]);
  });

  it("mod+shift+2 switches activeSection to 'knowledge'", async () => {
    mount();
    await act(async () => {
      await Promise.resolve();
    });

    fireBoth("2", { shift: true });

    expect(useChatStore.getState().activeSection).toBe("knowledge");
  });

  it("mod+shift+7 switches activeSection to 'integrity'", async () => {
    mount();
    await act(async () => {
      await Promise.resolve();
    });

    fireBoth("7", { shift: true });

    expect(useChatStore.getState().activeSection).toBe("integrity");
  });

  it("mod+j toggles the dock open state and marks it overridden", async () => {
    mount();
    await act(async () => {
      await Promise.resolve();
    });

    expect(useUiStore.getState().dockOpen).toBe(true);
    fireBoth("j");
    expect(useUiStore.getState().dockOpen).toBe(false);
    expect(useUiStore.getState().dockOverridden).toBe(true);

    fireBoth("j");
    expect(useUiStore.getState().dockOpen).toBe(true);
  });
});
