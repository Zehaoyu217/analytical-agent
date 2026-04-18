import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useDigestStore } from '../digest-store'

interface FetchCall {
  url: string
  method: string
  body: unknown
}

function installFetchMock(
  responder?: (url: string) => { status: number; body: unknown },
): FetchCall[] {
  const calls: FetchCall[] = []
  const defaultBody = {
    ok: true,
    date: '2026-04-18',
    entry_count: 1,
    unread: 1,
    entries: [
      {
        id: 'r01',
        section: 'Reconciliation',
        line: 'x',
        action: 'keep',
        applied: false,
      },
    ],
  }
  global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const bodyRaw = init?.body as string | undefined
    calls.push({
      url,
      method: init?.method ?? 'GET',
      body: bodyRaw !== undefined ? JSON.parse(bodyRaw) : undefined,
    })
    const resolved = responder?.(url) ?? { status: 200, body: defaultBody }
    return new Response(JSON.stringify(resolved.body), { status: resolved.status })
  }) as typeof fetch
  return calls
}

describe('digest-store', () => {
  beforeEach(() => {
    useDigestStore.setState({
      date: '',
      entries: [],
      unread: 0,
      loading: false,
      error: null,
    })
  })

  it('refresh() populates date, entries, unread', async () => {
    installFetchMock()
    await useDigestStore.getState().refresh()
    const state = useDigestStore.getState()
    expect(state.date).toBe('2026-04-18')
    expect(state.entries).toHaveLength(1)
    expect(state.unread).toBe(1)
    expect(state.loading).toBe(false)
  })

  it('refresh() treats 404 as empty state', async () => {
    installFetchMock(() => ({ status: 404, body: { detail: 'second_brain_disabled' } }))
    await useDigestStore.getState().refresh()
    const state = useDigestStore.getState()
    expect(state.entries).toEqual([])
    expect(state.unread).toBe(0)
    expect(state.date).toBe('')
  })

  it('apply() posts ids to /apply and then refreshes', async () => {
    const calls = installFetchMock()
    await useDigestStore.getState().apply(['r01'])
    const urls = calls.map((c) => c.url)
    expect(urls).toContain('/api/sb/digest/apply')
    expect(urls).toContain('/api/sb/digest/today')
    const applyCall = calls.find((c) => c.url === '/api/sb/digest/apply')
    expect(applyCall?.method).toBe('POST')
    expect(applyCall?.body).toEqual({ ids: ['r01'] })
  })

  it('skip() posts id + ttl_days and then refreshes', async () => {
    const calls = installFetchMock()
    await useDigestStore.getState().skip('r01', 14)
    const skipCall = calls.find((c) => c.url === '/api/sb/digest/skip')
    expect(skipCall?.body).toEqual({ id: 'r01', ttl_days: 14 })
    expect(calls.map((c) => c.url)).toContain('/api/sb/digest/today')
  })

  it('skip() defaults ttl_days to 30', async () => {
    const calls = installFetchMock()
    await useDigestStore.getState().skip('r01')
    const skipCall = calls.find((c) => c.url === '/api/sb/digest/skip')
    expect(skipCall?.body).toEqual({ id: 'r01', ttl_days: 30 })
  })

  it('markRead() is a no-op when date is empty', async () => {
    const calls = installFetchMock()
    await useDigestStore.getState().markRead()
    expect(calls).toHaveLength(0)
  })

  it('markRead() posts current date when set', async () => {
    const calls = installFetchMock()
    useDigestStore.setState({ date: '2026-04-18' })
    await useDigestStore.getState().markRead()
    const readCall = calls.find((c) => c.url === '/api/sb/digest/read')
    expect(readCall?.body).toEqual({ date: '2026-04-18' })
  })
})
