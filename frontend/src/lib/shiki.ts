/**
 * Lazy shiki loader.
 *
 * Shiki is ~500kb and only needed when a code block renders, so we:
 *   1. Dynamic-import the package on first call
 *   2. Keep a module-level highlighter singleton across renders
 *   3. Preload both themes (`github-light` + `github-dark`) so theme switches
 *      are instant
 */

// Shiki's createHighlighter returns a highlighter object. We keep typing loose
// here to avoid importing heavy types upfront — the callers only consume the
// returned HTML string.
type Highlighter = {
  codeToHtml: (
    code: string,
    options: { lang: string; theme: string },
  ) => string
}

export type ShikiTheme = 'github-dark' | 'github-light'

const SUPPORTED_LANGS = [
  'typescript',
  'javascript',
  'tsx',
  'jsx',
  'python',
  'bash',
  'shell',
  'sh',
  'json',
  'yaml',
  'yml',
  'markdown',
  'md',
  'css',
  'html',
  'rust',
  'go',
  'java',
  'c',
  'cpp',
  'sql',
  'dockerfile',
  'plaintext',
  'text',
] as const

let highlighterPromise: Promise<Highlighter> | null = null

function loadHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = import('shiki').then(({ createHighlighter }) =>
      createHighlighter({
        themes: ['github-dark', 'github-light'],
        langs: [...SUPPORTED_LANGS],
      }) as unknown as Promise<Highlighter>,
    )
  }
  return highlighterPromise
}

const SUPPORTED_SET = new Set<string>(SUPPORTED_LANGS)

/**
 * Highlight `code` in `lang` using `theme`. Falls back to plaintext on any
 * unknown language or shiki error.
 */
export async function highlightCode(
  code: string,
  lang: string,
  theme: ShikiTheme = 'github-dark',
): Promise<string> {
  const normalizedLang = SUPPORTED_SET.has(lang) ? lang : 'plaintext'
  const highlighter = await loadHighlighter()
  try {
    return highlighter.codeToHtml(code, { lang: normalizedLang, theme })
  } catch {
    return highlighter.codeToHtml(code, { lang: 'plaintext', theme })
  }
}
