import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PipelineBar } from "../PipelineBar";
import { usePipelineStore } from "@/lib/pipeline-store";

function resetStore(): void {
  usePipelineStore.setState({
    ingest: { status: "idle", lastRunAt: null, lastResult: null, errorMessage: null },
    digest: { status: "idle", lastRunAt: null, lastResult: null, errorMessage: null },
    maintain: {
      status: "idle",
      lastRunAt: null,
      lastResult: null,
      errorMessage: null,
    },
    digestPending: null,
  });
}

function mockFetch(responses: Array<{ ok: boolean; body: unknown }>): void {
  const fn = vi.fn();
  for (const r of responses) {
    fn.mockResolvedValueOnce({
      ok: r.ok,
      status: r.ok ? 200 : 500,
      json: async () => r.body,
      text: async () => "",
    });
  }
  vi.stubGlobal("fetch", fn);
}

describe("PipelineBar", () => {
  beforeEach(() => {
    resetStore();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders three phase buttons under Pipeline landmark", () => {
    mockFetch([
      {
        ok: true,
        body: {
          ok: true,
          ingest: { last_run_at: null, result: null },
          digest: { last_run_at: null, result: null },
          maintain: { last_run_at: null, result: null },
        },
      },
      { ok: true, body: { ok: true, count: 0, proposals: [] } },
    ]);
    render(<PipelineBar />);
    const nav = screen.getByRole("navigation", { name: "Pipeline" });
    const buttons = nav.querySelectorAll("button");
    expect(buttons.length).toBe(3);
  });

  it("invokes onOpenIngest on Ingest click", () => {
    mockFetch([
      {
        ok: true,
        body: {
          ok: true,
          ingest: { last_run_at: null, result: null },
          digest: { last_run_at: null, result: null },
          maintain: { last_run_at: null, result: null },
        },
      },
      { ok: true, body: { ok: true, count: 0, proposals: [] } },
    ]);
    const onOpenIngest = vi.fn();
    render(<PipelineBar onOpenIngest={onOpenIngest} />);
    fireEvent.click(screen.getByRole("button", { name: /Ingest/ }));
    expect(onOpenIngest).toHaveBeenCalled();
  });

  it("invokes onDigestComplete when runDigest returns entries", async () => {
    mockFetch([
      {
        ok: true,
        body: {
          ok: true,
          ingest: { last_run_at: null, result: null },
          digest: { last_run_at: null, result: null },
          maintain: { last_run_at: null, result: null },
        },
      },
      { ok: true, body: { ok: true, count: 0, proposals: [] } },
      { ok: true, body: { ok: true, entries: 4, emitted: true } },
      {
        ok: true,
        body: {
          ok: true,
          ingest: { last_run_at: null, result: null },
          digest: {
            last_run_at: "2026-04-19T10:00:00Z",
            result: { entries: 4, emitted: true, pending: 0 },
          },
          maintain: { last_run_at: null, result: null },
        },
      },
      { ok: true, body: { ok: true, count: 0, proposals: [] } },
    ]);
    const onDigestComplete = vi.fn();
    render(<PipelineBar onDigestComplete={onDigestComplete} />);
    fireEvent.click(screen.getByRole("button", { name: /Digest/ }));
    await waitFor(() => expect(onDigestComplete).toHaveBeenCalledWith(4));
  });
});
