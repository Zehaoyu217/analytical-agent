import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatInput } from '../ChatInput'
import { useChatStore } from '@/lib/store'

type Handler = { status?: number; body: unknown; contentType?: string }

function makeFetchMock(handlers: Record<string, Handler>) {
  const calls: Array<{ url: string; method: string; body: unknown }> = []
  return {
    impl: (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'
      const bodyRaw = init?.body as string | undefined
      calls.push({
        url,
        method,
        body: bodyRaw !== undefined ? JSON.parse(bodyRaw) : undefined,
      })
      const key = `${method} ${url}`
      const handler = handlers[key]
      if (!handler) {
        return Promise.resolve({
          ok: false,
          status: 404,
          headers: { get: () => 'text/plain' },
          text: () => Promise.resolve('no handler for ' + url),
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
    },
    calls,
  }
}

const SLASH_LIST = [
  { id: 'help', label: '/help', description: 'Show help' },
  { id: 'clear', label: '/clear', description: 'Clear conversation' },
  { id: 'new', label: '/new', description: 'New conversation' },
  { id: 'settings', label: '/settings', description: 'Open settings' },
]

describe('<ChatInput> slash menu', () => {
  beforeEach(() => {
    useChatStore.setState({
      conversations: [
        {
          id: 'conv-1',
          title: 'Test',
          messages: [
            {
              id: 'm1',
              role: 'user',
              content: 'hello',
              timestamp: 1,
              status: 'complete',
            },
          ],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
      ],
      activeConversationId: 'conv-1',
      activeSection: 'chat',
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  async function openMenu(): Promise<HTMLTextAreaElement> {
    const { impl } = makeFetchMock({
      'GET /api/slash': { body: SLASH_LIST },
    })
    vi.stubGlobal('fetch', impl)

    render(<ChatInput conversationId="conv-1" />)
    const textarea = screen.getByLabelText('Message') as HTMLTextAreaElement

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '/' } })
    })
    await act(async () => { await Promise.resolve() })
    await act(async () => { await Promise.resolve() })
    return textarea
  }

  it('shows slash suggestions when user types "/"', async () => {
    await openMenu()
    expect(
      screen.getByRole('listbox', { name: /slash commands/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('/help')).toBeInTheDocument()
    expect(screen.getByText('/clear')).toBeInTheDocument()
  })

  it('picking /clear empties active conversation messages and clears input', async () => {
    const textarea = await openMenu()

    // Filter to /clear and press Enter to pick.
    await act(async () => {
      fireEvent.change(textarea, { target: { value: '/clear' } })
    })
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter' })
    })
    await act(async () => { await Promise.resolve() })

    expect(useChatStore.getState().conversations[0].messages).toHaveLength(0)
    expect(textarea.value).toBe('')
    expect(
      screen.queryByRole('listbox', { name: /slash commands/i }),
    ).not.toBeInTheDocument()
  })

  it('picking /new creates an additional conversation', async () => {
    const textarea = await openMenu()
    const before = useChatStore.getState().conversations.length

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '/new' } })
    })
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter' })
    })

    expect(useChatStore.getState().conversations.length).toBe(before + 1)
    expect(textarea.value).toBe('')
  })

  it('picking /settings switches activeSection', async () => {
    const textarea = await openMenu()

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '/settings' } })
    })
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter' })
    })

    expect(useChatStore.getState().activeSection).toBe('settings')
    expect(textarea.value).toBe('')
  })

  it('does not POST to /api/slash/execute (legacy endpoint)', async () => {
    const { impl, calls } = makeFetchMock({
      'GET /api/slash': { body: SLASH_LIST },
    })
    vi.stubGlobal('fetch', impl)

    render(<ChatInput conversationId="conv-1" />)
    const textarea = screen.getByLabelText('Message') as HTMLTextAreaElement

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '/help' } })
    })
    await act(async () => { await Promise.resolve() })
    await act(async () => { await Promise.resolve() })
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter' })
    })

    expect(calls.find((c) => c.url === '/api/slash/execute')).toBeUndefined()
  })
})
