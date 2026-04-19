import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FlyoutTooltip } from "../FlyoutTooltip";

describe("FlyoutTooltip", () => {
  it("renders the label and hint in a role=tooltip element", () => {
    render(
      <FlyoutTooltip label="Chat" hint="⌘1">
        <button>chat</button>
      </FlyoutTooltip>,
    );
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveTextContent("Chat");
    expect(tip).toHaveTextContent("⌘1");
  });

  it("starts hidden (opacity-0) and becomes visible on pointer enter", () => {
    render(
      <FlyoutTooltip label="Chat" hint="⌘1">
        <button>chat</button>
      </FlyoutTooltip>,
    );
    const tip = screen.getByRole("tooltip");
    expect(tip.className).toMatch(/opacity-0/);

    const wrapper = tip.parentElement!;
    fireEvent.pointerEnter(wrapper);
    expect(tip.className).toMatch(/opacity-100/);

    fireEvent.pointerLeave(wrapper);
    expect(tip.className).toMatch(/opacity-0/);
  });

  it("becomes visible on keyboard focus", () => {
    render(
      <FlyoutTooltip label="Skills" hint="⌘3">
        <button>skills</button>
      </FlyoutTooltip>,
    );
    const tip = screen.getByRole("tooltip");
    expect(tip.className).toMatch(/opacity-0/);

    // Focus capture fires on the wrapper before reaching the button.
    fireEvent.focus(screen.getByRole("button"));
    expect(tip.className).toMatch(/opacity-100/);
  });

  it("omits the hint span when no hint is provided", () => {
    render(
      <FlyoutTooltip label="Settings">
        <button>settings</button>
      </FlyoutTooltip>,
    );
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveTextContent("Settings");
    // Only one child span (the label) when hint is absent.
    expect(tip.querySelectorAll("span").length).toBe(1);
  });

  it("flips tooltip to the left when side='left'", () => {
    render(
      <FlyoutTooltip label="Archive" side="left">
        <button>archive</button>
      </FlyoutTooltip>,
    );
    const tip = screen.getByRole("tooltip");
    expect(tip.className).toMatch(/right-full/);
    expect(tip.className).not.toMatch(/left-full/);
  });
});
