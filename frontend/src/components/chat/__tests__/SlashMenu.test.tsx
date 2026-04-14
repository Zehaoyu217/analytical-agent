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

describe('<ChatInput> slash menu', () => {
  beforeEach(() => {
    useChatStore.setState({
      conversations: [
        {
          id: 'conv-1',
          title: 'Test',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
      ],
      activeConversationId: 'conv-1',
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows slash suggestions when user types "/" and executes on Enter', async () => {
    const { impl, calls } = makeFetchMock({
      'GET /api/slash': {
        body: [
          { id: 'help', label: '/help', description: 'Show help' },
          { id: 'clear', label: '/clear', description: 'Clear conversation' },
        ],
      },
      'POST /api/slash/execute': {
        body: { ok: true, message: 'Executed help' },
      },
    })
    vi.stubGlobal('fetch', impl)

    render(<ChatInput conversationId="conv-1" />)

    const textarea = screen.getByLabelText('Message') as HTMLTextAreaElement

    // Type "/"
    await act(async () => {
      fireEvent.change(textarea, { target: { value: '/' } })
    })
    // Let the slash fetch resolve.
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByRole('listbox', { name: /slash commands/i })).toBeInTheDocument()
    expect(screen.getByText('/help')).toBeInTheDocument()
    expect(screen.getByText('/clear')).toBeInTheDocument()

    // Press Enter to pick the first suggestion.
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter' })
    })
    await act(async () => {
      await Promise.resolve()
    })

    // Textarea value is the label of the picked command.
    expect(textarea.value).toBe('/help')

    // Execute was called.
    const execCall = calls.find((c) => c.url === '/api/slash/execute')
    expect(execCall).toBeDefined()
    expect((execCall?.body as { command_id: string }).command_id).toBe('help')
  })

  it('closes the menu after pick so the next Enter submits instead of re-firing', async () => {
    const { impl, calls } = makeFetchMock({
      'GET /api/slash': {
        body: [{ id: 'help', label: '/help', description: 'Show help' }],
      },
      'POST /api/slash/execute': {
        body: { ok: true, message: 'Executed help' },
      },
      // Accept persistence + chat send calls so the happy path can complete.
      'POST /api/conversations/conv-1/turns': {
        body: { id: 'conv-1', turns: [] },
      },
      'POST /api/chat': {
        body: { response: 'ok', session_id: 'sess-1' },
      },
    })
    vi.stubGlobal('fetch', impl)

    render(<ChatInput conversationId="conv-1" />)
    const textarea = screen.getByLabelText('Message') as HTMLTextAreaElement

    // Type "/" → menu opens.
    await act(async () => {
      fireEvent.change(textarea, { target: { value: '/' } })
    })
    await act(async () => { await Promise.resolve() })
    await act(async () => { await Promise.resolve() })
    expect(screen.queryByRole('listbox', { name: /slash commands/i })).toBeInTheDocument()

    // First Enter picks the command — menu should close even though input
    // still starts with "/".
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter' })
    })
    await act(async () => { await Promise.resolve() })

    expect(textarea.value).toBe('/help')
    expect(screen.queryByRole('listbox', { name: /slash commands/i })).not.toBeInTheDocument()

    // Second Enter must submit, not re-fire the command.
    const execBefore = calls.filter((c) => c.url === '/api/slash/execute').length
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter' })
    })
    await act(async () => { await Promise.resolve() })

    const execAfter = calls.filter((c) => c.url === '/api/slash/execute').length
    expect(execAfter).toBe(execBefore)

    // ChatInput now uses the streaming endpoint /api/chat/stream
    const chatCall = calls.find(
      (c) => c.url === '/api/chat/stream' || c.url === '/api/chat',
    )
    expect(chatCall).toBeDefined()
    expect((chatCall?.body as { message: string }).message).toBe('/help')
  })
})
