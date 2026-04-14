import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { backend } from '../api-backend'

interface FetchCall {
  url: string
  method: string
  body: unknown
}

function mockFetch(responses: Array<{ status?: number; body: unknown; contentType?: string }>) {
  const calls: FetchCall[] = []
  let callIndex = 0
  const impl = (
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = init?.method ?? 'GET'
    const bodyRaw = init?.body as string | undefined
    calls.push({
      url,
      method,
      body: bodyRaw !== undefined ? JSON.parse(bodyRaw) : undefined,
    })
    const resp = responses[callIndex] ?? responses[responses.length - 1]
    callIndex += 1
    const status = resp.status ?? 200
    const ok = status >= 200 && status < 300
    const contentType = resp.contentType ?? 'application/json'
    return Promise.resolve({
      ok,
      status,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === 'content-type' ? contentType : null,
      },
      json: () => Promise.resolve(resp.body),
      text: () =>
        Promise.resolve(
          typeof resp.body === 'string' ? resp.body : JSON.stringify(resp.body),
        ),
    } as unknown as Response)
  }
  return { impl, calls }
}

describe('api-backend client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('conversations.list GETs /api/conversations', async () => {
    const { impl, calls } = mockFetch([
      { body: [{ id: 'a', title: 't', created_at: 1, updated_at: 2, turn_count: 0 }] },
    ])
    vi.stubGlobal('fetch', impl)
    const out = await backend.conversations.list()
    expect(calls[0]).toEqual({
      url: '/api/conversations',
      method: 'GET',
      body: undefined,
    })
    expect(out[0].id).toBe('a')
  })

  it('conversations.create POSTs with title payload', async () => {
    const conv = {
      id: 'abcdef01',
      title: 'hi',
      created_at: 1,
      updated_at: 1,
      turns: [],
    }
    const { impl, calls } = mockFetch([{ body: conv }])
    vi.stubGlobal('fetch', impl)
    const out = await backend.conversations.create('hi')
    expect(calls[0].url).toBe('/api/conversations')
    expect(calls[0].method).toBe('POST')
    expect(calls[0].body).toEqual({ title: 'hi' })
    expect(out.id).toBe('abcdef01')
  })

  it('conversations.appendTurn POSTs to /{id}/turns', async () => {
    const conv = {
      id: 'abc',
      title: 't',
      created_at: 1,
      updated_at: 2,
      turns: [{ role: 'user', content: 'hi', timestamp: 1 }],
    }
    const { impl, calls } = mockFetch([{ body: conv }])
    vi.stubGlobal('fetch', impl)
    await backend.conversations.appendTurn('abc', 'user', 'hi')
    expect(calls[0].url).toBe('/api/conversations/abc/turns')
    expect(calls[0].method).toBe('POST')
    expect(calls[0].body).toEqual({ role: 'user', content: 'hi' })
  })

  it('conversations.delete DELETEs and returns void', async () => {
    const { impl, calls } = mockFetch([{ status: 204, body: '' }])
    vi.stubGlobal('fetch', impl)
    await backend.conversations.delete('abc')
    expect(calls[0].url).toBe('/api/conversations/abc')
    expect(calls[0].method).toBe('DELETE')
  })

  it('settings.get GETs /api/settings', async () => {
    const { impl, calls } = mockFetch([
      { body: { theme: 'system', model: 'claude-sonnet-4-6', send_on_enter: true } },
    ])
    vi.stubGlobal('fetch', impl)
    const out = await backend.settings.get()
    expect(calls[0].url).toBe('/api/settings')
    expect(calls[0].method).toBe('GET')
    expect(out.theme).toBe('system')
  })

  it('settings.put PUTs payload', async () => {
    const payload = {
      theme: 'dark' as const,
      model: 'claude-opus-4-6',
      send_on_enter: false,
    }
    const { impl, calls } = mockFetch([{ body: payload }])
    vi.stubGlobal('fetch', impl)
    await backend.settings.put(payload)
    expect(calls[0].method).toBe('PUT')
    expect(calls[0].body).toEqual(payload)
  })

  it('files.tree GETs /api/files/tree with path query', async () => {
    const { impl, calls } = mockFetch([{ body: { root: '', entries: [], truncated: false } }])
    vi.stubGlobal('fetch', impl)
    await backend.files.tree('docs')
    expect(calls[0].url).toBe('/api/files/tree?path=docs')
  })

  it('files.tree without path GETs /api/files/tree without query', async () => {
    const { impl, calls } = mockFetch([{ body: { root: '', entries: [], truncated: false } }])
    vi.stubGlobal('fetch', impl)
    await backend.files.tree()
    expect(calls[0].url).toBe('/api/files/tree')
  })

  it('files.read GETs /api/files/read', async () => {
    const { impl, calls } = mockFetch([
      { body: { path: 'a.txt', size: 2, content: 'hi', encoding: 'utf-8' } },
    ])
    vi.stubGlobal('fetch', impl)
    const out = await backend.files.read('a.txt')
    expect(calls[0].url).toBe('/api/files/read?path=a.txt')
    expect(out.content).toBe('hi')
  })

  it('slash.list GETs /api/slash', async () => {
    const { impl, calls } = mockFetch([{ body: [] }])
    vi.stubGlobal('fetch', impl)
    await backend.slash.list()
    expect(calls[0].url).toBe('/api/slash')
    expect(calls[0].method).toBe('GET')
  })

  it('slash.execute POSTs command_id + args + conversation_id', async () => {
    const { impl, calls } = mockFetch([{ body: { ok: true, message: 'ok' } }])
    vi.stubGlobal('fetch', impl)
    await backend.slash.execute('help', { x: 1 }, 'conv-1')
    expect(calls[0].url).toBe('/api/slash/execute')
    expect(calls[0].method).toBe('POST')
    expect(calls[0].body).toEqual({
      command_id: 'help',
      args: { x: 1 },
      conversation_id: 'conv-1',
    })
  })

  it('throws an Error on non-2xx with response body in message', async () => {
    const { impl } = mockFetch([
      { status: 404, body: 'conversation not found', contentType: 'text/plain' },
    ])
    vi.stubGlobal('fetch', impl)
    await expect(backend.conversations.get('missing')).rejects.toThrow(
      /GET \/api\/conversations\/missing failed \(404\)/,
    )
  })
})
