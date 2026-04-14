import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SettingsTab } from '../SettingsTab'
import { ThemeProvider } from '@/components/layout/ThemeProvider'

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
    },
    calls,
  }
}

describe('<SettingsTab>', () => {
  beforeEach(() => {
    window.localStorage.clear()
    // jsdom doesn't implement matchMedia; ThemeProvider calls it on mount.
    if (!window.matchMedia) {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: (query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
          dispatchEvent: () => false,
        }),
      })
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads defaults from backend and saves changes', async () => {
    const { impl, calls } = makeFetchMock({
      'GET /api/settings': {
        body: { theme: 'dark', model: 'claude-sonnet-4-6', send_on_enter: true },
      },
      'PUT /api/settings': {
        body: { theme: 'light', model: 'claude-sonnet-4-6', send_on_enter: true },
      },
    })
    vi.stubGlobal('fetch', impl)

    render(
      <ThemeProvider>
        <SettingsTab />
      </ThemeProvider>,
    )

    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    // Form shows loaded values.
    const modelInput = screen.getByLabelText('Model') as HTMLInputElement
    expect(modelInput.value).toBe('claude-sonnet-4-6')

    // Theme radios reflect current.
    const darkRadio = screen.getByLabelText('Dark') as HTMLInputElement
    expect(darkRadio.checked).toBe(true)

    // Change theme to light.
    const lightRadio = screen.getByLabelText('Light') as HTMLInputElement
    await act(async () => {
      fireEvent.click(lightRadio)
    })
    expect(lightRadio.checked).toBe(true)

    // Click Save.
    const saveBtn = screen.getByRole('button', { name: /^save$/i })
    await act(async () => {
      saveBtn.click()
    })
    await act(async () => {
      await Promise.resolve()
    })

    // Verify PUT was called with updated theme.
    const putCall = calls.find((c) => c.method === 'PUT')
    expect(putCall).toBeDefined()
    expect((putCall?.body as { theme: string }).theme).toBe('light')

    // Saved toast should render.
    expect(screen.getByRole('status').textContent).toMatch(/Saved/)
  })
})
