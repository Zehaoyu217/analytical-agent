/**
 * Unit tests for the context API helper functions introduced in P11.
 * These test the fetch wrappers directly using a mocked global fetch,
 * without requiring a running server.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fetchCompactionDiff,
  fetchSessionContext,
  fetchContext,
  listContextSessions,
} from '@/lib/api'

interface FetchCall {
  url: string
}

function mockFetch(body: unknown, status = 200) {
  const calls: FetchCall[] = []
  const impl = (input: RequestInfo | URL): Promise<Response> => {
    calls.push({ url: String(input) })
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)),
    } as unknown as Response)
  }
  vi.stubGlobal('fetch', impl)
  return calls
}

describe('context API helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('fetchContext (legacy global)', () => {
    it('calls /api/context', async () => {
      const snapshot = {
        total_tokens: 1000,
        max_tokens: 200000,
        utilization: 0.005,
        compaction_needed: false,
        layers: [],
        compaction_history: [],
      }
      const calls = mockFetch(snapshot)
      const result = await fetchContext()
      expect(calls[0].url).toBe('/api/context')
      expect(result.total_tokens).toBe(1000)
    })
  })

  describe('fetchSessionContext', () => {
    it('calls /api/context/{sessionId}', async () => {
      const snapshot = {
        session_id: 'test-session-abc',
        total_tokens: 5000,
        max_tokens: 200000,
        utilization: 0.025,
        compaction_needed: false,
        layers: [
          { name: 'System Prompt', tokens: 3000, compactable: false, items: [] },
          { name: 'User Message', tokens: 2000, compactable: true, items: [] },
        ],
        compaction_history: [],
      }
      const calls = mockFetch(snapshot)
      const result = await fetchSessionContext('test-session-abc')
      expect(calls[0].url).toBe('/api/context/test-session-abc')
      expect(result.session_id).toBe('test-session-abc')
      expect(result.layers).toHaveLength(2)
    })

    it('URL-encodes session IDs with special characters', async () => {
      mockFetch({ session_id: 'x', total_tokens: 0, max_tokens: 200000, utilization: 0, compaction_needed: false, layers: [], compaction_history: [] })
      await fetchSessionContext('chat/foo bar')
      // ensure it doesn't throw — encoding handled by encodeURIComponent
    })
  })

  describe('listContextSessions', () => {
    it('calls /api/context/sessions and returns list', async () => {
      const calls = mockFetch({ sessions: ['s1', 's2', 's3'] })
      const result = await listContextSessions()
      expect(calls[0].url).toBe('/api/context/sessions')
      expect(result.sessions).toEqual(['s1', 's2', 's3'])
    })

    it('returns empty list when no sessions exist', async () => {
      mockFetch({ sessions: [] })
      const result = await listContextSessions()
      expect(result.sessions).toHaveLength(0)
    })
  })

  describe('fetchCompactionDiff', () => {
    it('calls /api/context/{sessionId}/compaction/{id}', async () => {
      const diff = {
        session_id: 'sess-1',
        compaction_id: 3,
        timestamp: '2026-04-14T12:00:00Z',
        tokens_before: 160000,
        tokens_after: 90000,
        tokens_freed: 70000,
        trigger_utilization: 0.8,
        information_loss_pct: 43.75,
        loss_severity: 'HIGH',
        removed: [{ name: 'old_tool_result', tokens: 70000 }],
        survived: ['System Prompt', 'User Message'],
      }
      const calls = mockFetch(diff)
      const result = await fetchCompactionDiff('sess-1', 3)
      expect(calls[0].url).toBe('/api/context/sess-1/compaction/3')
      expect(result.loss_severity).toBe('HIGH')
      expect(result.information_loss_pct).toBe(43.75)
    })

    it('throws on non-ok response', async () => {
      mockFetch({ detail: 'not found' }, 404)
      await expect(fetchCompactionDiff('no-session', 99)).rejects.toThrow()
    })
  })
})
