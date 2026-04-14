import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FilesTab } from '../FilesTab'

type Handler = { status?: number; body: unknown; contentType?: string }

function makeFetchMock(handlers: Record<string, Handler>) {
  const calls: Array<{ url: string; method: string }> = []
  return {
    impl: (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'
      calls.push({ url, method })
      // Match by prefix of url (ignoring query variants) — we try exact first.
      const exact = handlers[`${method} ${url}`]
      const handler = exact
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

describe('<FilesTab>', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders root tree and navigates into a subfolder then opens a file', async () => {
    const { impl } = makeFetchMock({
      'GET /api/files/tree': {
        body: {
          root: '',
          truncated: false,
          entries: [
            {
              path: 'docs',
              name: 'docs',
              kind: 'dir',
              size: null,
              modified: 1,
            },
            {
              path: 'README.md',
              name: 'README.md',
              kind: 'file',
              size: 1024,
              modified: 1,
            },
          ],
        },
      },
      'GET /api/files/tree?path=docs': {
        body: {
          root: '',
          truncated: false,
          entries: [
            {
              path: 'docs/intro.md',
              name: 'intro.md',
              kind: 'file',
              size: 77,
              modified: 2,
            },
          ],
        },
      },
      'GET /api/files/read?path=docs%2Fintro.md': {
        body: {
          path: 'docs/intro.md',
          size: 77,
          content: 'Hello from docs',
          encoding: 'utf-8',
        },
      },
    })
    vi.stubGlobal('fetch', impl)

    render(<FilesTab />)

    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    // Root listing shows folder + file.
    expect(screen.getByText('docs')).toBeInTheDocument()
    expect(screen.getByText('README.md')).toBeInTheDocument()

    // Navigate into docs.
    await act(async () => {
      screen.getByText('docs').click()
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByText('intro.md')).toBeInTheDocument()

    // Open the file.
    await act(async () => {
      screen.getByText('intro.md').click()
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Hello from docs')).toBeInTheDocument()
  })
})
