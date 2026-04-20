import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePipelineStore, formatAgo } from "../pipeline-store";

type FetchMock = ReturnType<typeof vi.fn>;

function resetStore(): void {
  usePipelineStore.setState({
    ingest: {
      status: "idle",
      lastRunAt: null,
      lastResult: null,
      errorMessage: null,
    },
    digest: {
      status: "idle",
      lastRunAt: null,
      lastResult: null,
      errorMessage: null,
    },
    maintain: {
      status: "idle",
      lastRunAt: null,
      lastResult: null,
      errorMessage: null,
    },
    gardener: {
      status: "idle",
      lastRunAt: null,
      lastResult: null,
      errorMessage: null,
    },
    digestPending: null,
  });
}

function mockFetchSequence(
  responses: Array<{ ok: boolean; status?: number; body: unknown; text?: string }>,
): FetchMock {
  const fn = vi.fn();
  for (const r of responses) {
    fn.mockResolvedValueOnce({
      ok: r.ok,
      status: r.status ?? (r.ok ? 200 : 500),
      json: async () => r.body,
      text: async () => r.text ?? "",
    });
  }
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("pipeline-store", () => {
  beforeEach(() => {
    resetStore();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("refreshStatus hydrates all three phase slots", async () => {
    mockFetchSequence([
      {
        ok: true,
        body: {
          ok: true,
          ingest: {
            last_run_at: "2026-04-19T10:00:00Z",
            result: { sources_added: 1 },
          },
          digest: {
            last_run_at: "2026-04-19T10:01:00Z",
            result: { entries: 3, emitted: true, pending: 2 },
          },
          maintain: { last_run_at: null, result: null },
        },
      },
      { ok: true, body: { ok: true, count: 2, proposals: [] } },
    ]);

    await usePipelineStore.getState().refreshStatus();
    const s = usePipelineStore.getState();
    expect(s.ingest.lastRunAt).toBe("2026-04-19T10:00:00Z");
    expect(s.digest.lastResult?.entries).toBe(3);
    expect(s.maintain.lastRunAt).toBeNull();
  });

  it("refreshStatus swallows network errors and leaves slots untouched", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error("network"));
    vi.stubGlobal("fetch", fn);
    await expect(
      usePipelineStore.getState().refreshStatus(),
    ).resolves.toBeUndefined();
    expect(usePipelineStore.getState().digest.lastRunAt).toBeNull();
  });

  it("runDigest transitions idle → running → done and auto-reverts", async () => {
    mockFetchSequence([
      { ok: true, body: { ok: true, entries: 2, emitted: true } },
      {
        ok: true,
        body: {
          ok: true,
          ingest: { last_run_at: null, result: null },
          digest: {
            last_run_at: "2026-04-19T10:00:00Z",
            result: { entries: 2, emitted: true, pending: 0 },
          },
          maintain: { last_run_at: null, result: null },
        },
      },
      { ok: true, body: { ok: true, count: 0, proposals: [] } },
    ]);

    const promise = usePipelineStore.getState().runDigest();
    expect(usePipelineStore.getState().digest.status).toBe("running");
    const result = await promise;
    expect(result?.entries).toBe(2);
    expect(usePipelineStore.getState().digest.status).toBe("done");

    vi.advanceTimersByTime(2100);
    expect(usePipelineStore.getState().digest.status).toBe("idle");
  });

  it("runDigest records errorMessage on non-ok response", async () => {
    mockFetchSequence([
      { ok: false, status: 500, body: {}, text: "digest_build_failed: boom" },
    ]);
    const result = await usePipelineStore.getState().runDigest();
    expect(result).toBeNull();
    const s = usePipelineStore.getState().digest;
    expect(s.status).toBe("error");
    expect(s.errorMessage).toContain("digest_build_failed");
  });

  it("runMaintain writes summary and auto-reverts", async () => {
    const summary = {
      lint_errors: 0,
      lint_warnings: 2,
      lint_info: 1,
      open_contradictions: 0,
      stale_count: 0,
      stale_abstracts: [],
      analytics_rebuilt: true,
      habit_proposals: 1,
      fts_bytes_before: 100,
      fts_bytes_after: 120,
      duck_bytes_before: 200,
      duck_bytes_after: 220,
    };
    mockFetchSequence([
      { ok: true, body: { ok: true, result: summary } },
      {
        ok: true,
        body: {
          ok: true,
          ingest: { last_run_at: null, result: null },
          digest: { last_run_at: null, result: null },
          maintain: { last_run_at: "2026-04-19T10:05:00Z", result: summary },
        },
      },
      { ok: true, body: { ok: true, count: 0, proposals: [] } },
    ]);
    const result = await usePipelineStore.getState().runMaintain();
    expect(result?.lint_warnings).toBe(2);
    expect(usePipelineStore.getState().maintain.status).toBe("done");
    vi.advanceTimersByTime(2100);
    expect(usePipelineStore.getState().maintain.status).toBe("idle");
  });

  it("runMaintain catches thrown errors and surfaces errorMessage", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error("boom"));
    vi.stubGlobal("fetch", fn);
    const result = await usePipelineStore.getState().runMaintain();
    expect(result).toBeNull();
    const s = usePipelineStore.getState().maintain;
    expect(s.status).toBe("error");
    expect(s.errorMessage).toBe("boom");
  });

  it("runGardener posts body and hydrates slot on success", async () => {
    const summary = {
      passes_run: ["extract"],
      proposals_added: 4,
      total_tokens: 900,
      total_cost_usd: 0.012,
      duration_ms: 50,
      errors: [],
    };
    mockFetchSequence([
      { ok: true, body: { ok: true, result: summary } },
      {
        ok: true,
        body: {
          ok: true,
          ingest: { last_run_at: null, result: null },
          digest: { last_run_at: null, result: null },
          maintain: { last_run_at: null, result: null },
          gardener: { last_run_at: "2026-04-19T10:00:00Z", result: summary },
        },
      },
      { ok: true, body: { ok: true, count: 0, proposals: [] } },
    ]);
    const result = await usePipelineStore
      .getState()
      .runGardener({ dry_run: false, passes: ["extract"] });
    expect(result?.proposals_added).toBe(4);
    expect(usePipelineStore.getState().gardener.status).toBe("done");
    vi.advanceTimersByTime(2100);
    expect(usePipelineStore.getState().gardener.status).toBe("idle");
  });

  it("runGardener records errorMessage on non-ok response", async () => {
    mockFetchSequence([
      { ok: false, status: 500, body: {}, text: "gardener_run_failed: boom" },
    ]);
    const result = await usePipelineStore.getState().runGardener();
    expect(result).toBeNull();
    const s = usePipelineStore.getState().gardener;
    expect(s.status).toBe("error");
    expect(s.errorMessage).toContain("gardener_run_failed");
  });
});

describe("formatAgo", () => {
  const NOW = Date.parse("2026-04-19T12:00:00Z");

  it("returns 'never' for null or unparseable input", () => {
    expect(formatAgo(null, NOW)).toBe("never");
    expect(formatAgo("not-a-date", NOW)).toBe("never");
  });

  it("formats seconds, minutes, hours, days", () => {
    expect(formatAgo("2026-04-19T11:59:30Z", NOW)).toBe("30s ago");
    expect(formatAgo("2026-04-19T11:55:00Z", NOW)).toBe("5m ago");
    expect(formatAgo("2026-04-19T09:00:00Z", NOW)).toBe("3h ago");
    expect(formatAgo("2026-04-17T12:00:00Z", NOW)).toBe("2d ago");
  });
});
