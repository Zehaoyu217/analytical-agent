import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { HistoryTab } from '../HistoryTab'
import { useChatStore } from '@/lib/store'

function makeFetchMock(
  handlers: Record<string, { status?: number; body: unknown; contentType?: string }>,
) {
  const calls: Array<{ url: string; method: string }> = []
  return (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = init?.method ?? 'GET'
    calls.push({ url, method })
    const key = `${method} ${url.split('?')[0]}`
    const handler = handlers[key]
    if (!handler) {
      return Promise.resolve({
        ok: false,
        status: 404,
        headers: { get: () => 'text/plain' },
        text: () => Promise.resolve('no handler'),
        json: () => Promise.resolve({}),
      } as unknown as Response)
    }
    const status = handler.status ?? 200
    const ok = status >= 200 && status < 300
    return Promise.resolve({
      ok,
      status,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === 'content-type'
            ? handler.contentType ?? 'application/json'
            : null,
      },
      json: () => Promise.resolve(handler.body),
      text: () =>
        Promise.resolve(
          typeof handler.body === 'string'
            ? handler.body
            : JSON.stringify(handler.body),
        ),
    } as unknown as Response)
  }
}

describe('<HistoryTab>', () => {
  beforeEach(() => {
    useChatStore.setState({
      conversations: [],
      activeConversationId: null,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders backend conversations as a list', async () => {
    const mock = makeFetchMock({
      'GET /api/conversations': {
        body: [
          {
            id: 'abc123',
            title: 'First conversation',
            created_at: 1_700_000_000,
            updated_at: 1_700_000_100,
            turn_count: 3,
          },
          {
            id: 'def456',
            title: 'Second conversation',
            created_at: 1_700_000_200,
            updated_at: 1_700_000_300,
            turn_count: 5,
          },
        ],
      },
    })
    vi.stubGlobal('fetch', mock)

    render(<HistoryTab />)

    // Let the useEffect fire and resolve.
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByText('First conversation')).toBeInTheDocument()
    expect(screen.getByText('Second conversation')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('click loads conversation into the store', async () => {
    const mock = makeFetchMock({
      'GET /api/conversations': {
        body: [
          {
            id: 'abc123',
            title: 'Click me',
            created_at: 1_700_000_000,
            updated_at: 1_700_000_100,
            turn_count: 2,
          },
        ],
      },
      'GET /api/conversations/abc123': {
        body: {
          id: 'abc123',
          title: 'Click me',
          created_at: 1_700_000_000,
          updated_at: 1_700_000_100,
          turns: [
            { role: 'user', content: 'hi', timestamp: 1_700_000_050 },
            { role: 'assistant', content: 'hello', timestamp: 1_700_000_060 },
          ],
        },
      },
    })
    vi.stubGlobal('fetch', mock)

    render(<HistoryTab />)

    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    const button = screen.getByTitle('Click me')
    await act(async () => {
      button.click()
    })
    await act(async () => {
      await Promise.resolve()
    })

    const state = useChatStore.getState()
    expect(state.activeConversationId).toBe('abc123')
    expect(state.conversations[0]?.id).toBe('abc123')
    expect(state.conversations[0]?.messages).toHaveLength(2)
    expect(state.conversations[0]?.messages[0]?.content).toBe('hi')
  })
})
