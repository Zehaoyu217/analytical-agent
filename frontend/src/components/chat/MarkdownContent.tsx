import { memo, useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, Copy, ExternalLink, WrapText } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/components/layout/ThemeProvider'
import { highlightCode } from '@/lib/shiki'
import { Skeleton } from '@/components/ui/Skeleton'

interface MarkdownContentProps {
  content: string
  className?: string
}

// ─── Inline code block used by react-markdown ───────────────────────────────
// This is a markdown-scoped fork of the standalone CodeBlock in `./CodeBlock`.
// It exists here (rather than reusing that component) because the react-markdown
// renderer gives us a `className` like `language-ts`, not a `{ code, language }`
// prop split — inlining lets us parse the class and normalise children in one
// place.

interface MdCodeBlockProps {
  className?: string
  children?: React.ReactNode
}

const MdCodeBlock = memo(function MdCodeBlock({
  className,
  children,
}: MdCodeBlockProps) {
  const { resolvedTheme } = useTheme()
  const shikiTheme = resolvedTheme === 'light' ? 'github-light' : 'github-dark'

  const lang = /language-(\w+)/.exec(className ?? '')?.[1] ?? 'plaintext'
  const code = String(children ?? '').replace(/\n$/, '')

  const [highlightedHtml, setHighlightedHtml] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [wordWrap, setWordWrap] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    highlightCode(code, lang, shikiTheme)
      .then((html) => {
        if (cancelled) return
        setHighlightedHtml(html)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setLoading(false)
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
      // clipboard unavailable
    }
  }, [code])

  return (
    <div className="shiki-container relative group my-3 rounded overflow-hidden border border-surface-700 bg-[#0d1117]">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-850 border-b border-surface-700">
        <span className="text-xs text-surface-500 font-mono select-none">
          {lang !== 'plaintext' ? lang : ''}
        </span>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => setWordWrap((v) => !v)}
            title="Toggle word wrap"
            aria-label="Toggle word wrap"
            aria-pressed={wordWrap}
            className={cn(
              'p-1 rounded transition-colors',
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
        {loading && !highlightedHtml ? (
          <div className="p-4 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        ) : highlightedHtml ? (
          <div
            className="[&>pre]:!p-4 [&>pre]:!m-0 [&>pre]:!bg-transparent [&>pre]:!overflow-visible [&>pre]:!rounded-none [&>pre]:!border-none"
            // Shiki output is sanitised HTML from a trusted library.
            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
          />
        ) : (
          <pre className="p-4 text-surface-300 bg-[#0d1117]">
            <code>{code}</code>
          </pre>
        )}
      </div>
    </div>
  )
})

// ─── Custom renderers ─────────────────────────────────────────────────────────

const mdComponents: Components = {
  code({ className: cls, children }) {
    const isBlock = /language-/.test(cls ?? '')
    if (isBlock) {
      return <MdCodeBlock className={cls}>{children}</MdCodeBlock>
    }
    return (
      <code className="text-brand-300 bg-surface-900 px-1 py-0.5 rounded text-xs font-mono border border-surface-700/50">
        {children}
      </code>
    )
  },
  // Suppress the default <pre> wrapper — MdCodeBlock renders its own container
  pre({ children }) {
    return <>{children}</>
  },
  a({ href, children }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-brand-400 hover:text-brand-300 no-underline hover:underline inline-flex items-center gap-0.5"
      >
        {children}
        <ExternalLink className="w-2.5 h-2.5 flex-shrink-0 inline" aria-label="(external link)" />
      </a>
    )
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto my-3">
        <table className="w-full border-collapse text-sm">{children}</table>
      </div>
    )
  },
  th({ children }) {
    return (
      <th className="px-3 py-1.5 text-left font-medium text-surface-200 border border-surface-700 bg-surface-850">
        {children}
      </th>
    )
  },
  td({ children }) {
    return (
      <td className="px-3 py-1.5 border border-surface-700 text-surface-300">
        {children}
      </td>
    )
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-brand-500 pl-4 my-2 text-surface-300 not-italic">
        {children}
      </blockquote>
    )
  },
}

// ─── Main component ───────────────────────────────────────────────────────────

export const MarkdownContent = memo(function MarkdownContent({
  content,
  className,
}: MarkdownContentProps) {
  return (
    <div
      className={cn(
        'prose prose-sm prose-invert max-w-none',
        'prose-p:leading-relaxed prose-p:my-1',
        'prose-pre:bg-transparent prose-pre:p-0 prose-pre:border-0',
        'prose-code:text-brand-300 prose-code:bg-surface-900 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs',
        'prose-pre:code:bg-transparent prose-pre:code:p-0',
        'prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5',
        'prose-headings:text-surface-100 prose-headings:font-semibold',
        'prose-a:text-brand-400 prose-a:no-underline hover:prose-a:underline',
        'prose-blockquote:border-brand-500 prose-blockquote:text-surface-300',
        'prose-hr:border-surface-700',
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={mdComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
})
