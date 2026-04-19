import { useCallback, useEffect, useState } from 'react'
import { Copy, Check, WrapText } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/components/layout/ThemeProvider'
import { highlightCode } from '@/lib/shiki'

interface CodeBlockProps {
  code: string
  language?: string
  className?: string
  showLineNumbers?: boolean
}

/**
 * Standalone syntax-highlighted code block.
 *
 * Highlighting is lazy (shiki is pulled in on first call). Theme is driven by
 * the app's light/dark selection via `useTheme`.
 */
export function CodeBlock({
  code,
  language = 'plaintext',
  className,
  showLineNumbers: initialShowLineNumbers = false,
}: CodeBlockProps) {
  const { resolvedTheme } = useTheme()
  const [html, setHtml] = useState<string>('')
  const [copied, setCopied] = useState(false)
  const [wordWrap, setWordWrap] = useState(false)
  const [showLineNumbers, setShowLineNumbers] = useState(initialShowLineNumbers)

  const lang = language || 'plaintext'
  const shikiTheme = resolvedTheme === 'light' ? 'github-light' : 'github-dark'

  useEffect(() => {
    let cancelled = false
    highlightCode(code, lang, shikiTheme)
      .then((result) => {
        if (!cancelled) setHtml(result)
      })
      .catch(() => {
        if (!cancelled) setHtml('')
      })
    return () => {
      cancelled = true
    }
  }, [code, lang, shikiTheme])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard not available
    }
  }, [code])

  return (
    <div
      className={cn(
        'shiki-container relative group my-3 rounded overflow-hidden border border-surface-700 bg-[#0d1117]',
        showLineNumbers && 'show-line-numbers',
        wordWrap && 'word-wrap-code',
        className,
      )}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-850 border-b border-surface-700">
        <span className="text-xs text-surface-500 font-mono select-none">
          {lang !== 'plaintext' ? lang : ''}
        </span>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => setShowLineNumbers((v) => !v)}
            title="Toggle line numbers"
            aria-label="Toggle line numbers"
            aria-pressed={showLineNumbers}
            className={cn(
              'p-1 rounded text-xs transition-colors',
              showLineNumbers
                ? 'text-brand-400 bg-brand-950/30'
                : 'text-surface-500 hover:text-surface-300',
            )}
          >
            <span className="font-mono text-[10px] px-1">123</span>
          </button>
          <button
            onClick={() => setWordWrap((v) => !v)}
            title="Toggle word wrap"
            aria-label="Toggle word wrap"
            aria-pressed={wordWrap}
            className={cn(
              'p-1 rounded text-xs transition-colors',
              wordWrap
                ? 'text-brand-400 bg-brand-950/30'
                : 'text-surface-500 hover:text-surface-300',
            )}
          >
            <WrapText className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleCopy}
            title={copied ? 'Copied!' : 'Copy code'}
            aria-label={copied ? 'Copied' : 'Copy code'}
            className="p-1 rounded text-surface-500 hover:text-surface-300 transition-colors"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Code content */}
      <div
        className={cn(
          'overflow-x-auto text-sm font-mono',
          wordWrap && 'whitespace-pre-wrap break-all overflow-x-hidden',
        )}
      >
        {html ? (
          <div
            // Shiki output is sanitised HTML from a trusted library.
            dangerouslySetInnerHTML={{ __html: html }}
            className="[&>pre]:!p-4 [&>pre]:!m-0 [&>pre]:!bg-transparent [&>pre]:!overflow-visible [&>pre]:!rounded-none [&>pre]:!border-none"
          />
        ) : (
          <pre className="p-4 text-surface-300 bg-[#0d1117]">
            <code>{code}</code>
          </pre>
        )}
      </div>
    </div>
  )
}
