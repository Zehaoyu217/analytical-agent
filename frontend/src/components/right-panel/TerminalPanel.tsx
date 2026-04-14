import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2 } from 'lucide-react'
import { useChatStore, type ToolCallEntry, type ToolCallStatus } from '@/lib/store'
import { cn } from '@/lib/utils'

// ── Rotating standby messages ─────────────────────────────────────────────────

const STANDBY_MESSAGES = [
  'awaiting query...',
  'standing by...',
  'ready to analyze...',
  'idle. ask me something...',
  'systems nominal...',
  'all tools loaded...',
  'connected to DuckDB...',
  'LLM is warm and waiting...',
]

// ── Per-tool verb rotations ───────────────────────────────────────────────────

const TOOL_VERBS: Record<string, string[]> = {
  execute_python: [
    'Unleashing the snake...',
    'Running Pythonic magic...',
    'Crunching in Python...',
    'Computing away...',
    'import awesome_results...',
    'def get_answers()...',
    'Snake go brrrr...',
    'Numpy doing numpy things...',
    'Pandas are eating data...',
  ],
  query_duckdb: [
    'Quacking through SQL...',
    'Asking the ducks politely...',
    'Querying the data pond...',
    'SELECT-ing the good stuff...',
    'JOINing the party...',
    'GROUP BY... everything...',
  ],
  write_working: [
    'Updating the scratchpad...',
    'Writing thoughts down...',
    'Recording findings...',
    'Logging to working memory...',
    'Noting it down...',
  ],
  delegate_subagent: [
    'Spawning sub-agent...',
    'Delegating to the team...',
    'Launching specialist...',
    'Coordinating work...',
  ],
}

const DEFAULT_VERBS = [
  'Working on it...',
  'Processing...',
  'Thinking...',
  'Computing...',
  'Running tool...',
  'Almost there...',
  'Just a moment...',
]

const DONE_QUIPS = [
  'Nailed it!',
  'Done and dusted!',
  'Boom!',
  'Easy peasy!',
  'Mission complete!',
  'Another one bites the dust!',
  'Ta-da!',
  'Crushed it.',
  'Analysis complete.',
  'SQL delivered.',
  'The data has spoken.',
]

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useRotatingText(texts: string[], intervalMs = 2500): string {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % texts.length)
    }, intervalMs)
    return () => clearInterval(timer)
  }, [texts, intervalMs])
  return texts[index]
}

// ── Components ────────────────────────────────────────────────────────────────

function LiveTimer({ startedAt, className }: { startedAt: number; className?: string }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const tick = () => setElapsed((Date.now() - startedAt) / 1000)
    tick()
    const timer = setInterval(tick, 73)
    return () => clearInterval(timer)
  }, [startedAt])

  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60

  return (
    <span
      className={cn(
        'text-[10px] font-mono tabular-nums shrink-0',
        className ?? 'text-amber-400/80',
      )}
    >
      {mins > 0
        ? `${mins}:${secs.toFixed(1).padStart(4, '0')}`
        : `${secs.toFixed(1)}s`}
    </span>
  )
}

function ElapsedBadge({
  startedAt,
  finishedAt,
}: {
  startedAt: number
  finishedAt: number
}) {
  const s = (finishedAt - startedAt) / 1000
  const display =
    s < 1
      ? `${Math.round(s * 1000)}ms`
      : s < 60
        ? `${s.toFixed(1)}s`
        : `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`

  return (
    <motion.span
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className="text-[10px] text-emerald-400/70 font-mono tabular-nums shrink-0 bg-emerald-500/8 px-1.5 py-0.5 rounded-sm"
    >
      {display}
    </motion.span>
  )
}

function RotatingVerb({ toolName }: { toolName: string }) {
  const verbs = TOOL_VERBS[toolName] ?? DEFAULT_VERBS
  const text = useRotatingText(verbs, 1600)
  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={text}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.15 }}
        className="text-[10px] text-amber-400/55 italic truncate max-w-[150px]"
      >
        {text}
      </motion.span>
    </AnimatePresence>
  )
}

function PythonCodeBlock({
  code,
  isRunning,
}: {
  code: string
  isRunning: boolean
}) {
  const lines = code.split('\n')
  const PREVIEW_LINES = 5
  const isLong = lines.length > PREVIEW_LINES
  const [expanded, setExpanded] = useState(isRunning)

  useEffect(() => {
    if (!isRunning && isLong) setExpanded(false)
  }, [isRunning, isLong])

  const displayCode = expanded
    ? code
    : lines.slice(0, PREVIEW_LINES).join('\n') + (isLong ? '\n…' : '')

  return (
    <div className="mt-1.5 rounded-sm bg-[#0b0e18] border border-violet-500/20 overflow-hidden">
      <div className="flex items-center justify-between px-2 py-1 border-b border-violet-500/15 bg-violet-500/5">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-400/60" />
          <span className="text-[9px] font-mono text-violet-400/70 tracking-wider">
            PYTHON
          </span>
          {isRunning && (
            <span className="text-[9px] font-mono text-amber-400/60 animate-pulse">
              executing…
            </span>
          )}
        </div>
        {isLong && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-[9px] font-mono text-violet-400/50 hover:text-violet-400/80 transition-colors"
          >
            {expanded ? 'collapse' : 'expand'}
          </button>
        )}
      </div>
      <pre className="text-[10px] font-mono text-violet-300/80 px-2.5 py-2 overflow-x-auto leading-relaxed whitespace-pre-wrap break-all">
        {displayCode}
      </pre>
    </div>
  )
}

function StdoutBlock({ stdout }: { stdout: string }) {
  const lines = stdout.split('\n')
  const MAX_LINES = 30
  const [showAll, setShowAll] = useState(false)
  const displayLines = showAll ? lines : lines.slice(0, MAX_LINES)
  const trimmed = lines.length > MAX_LINES && !showAll

  return (
    <div className="mt-1.5 rounded-sm bg-surface-950/80 border border-green-500/15 overflow-hidden">
      <div className="flex items-center gap-1.5 px-2 py-1 border-b border-green-500/10 bg-green-500/4">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400/40" />
        <span className="text-[9px] font-mono text-green-400/50 tracking-wider">STDOUT</span>
      </div>
      <pre className="text-[10px] font-mono text-green-300/65 px-2.5 py-2 overflow-x-auto leading-relaxed whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
        {displayLines.join('\n')}
        {trimmed && (
          <span
            className="block mt-1 text-green-400/40 cursor-pointer hover:text-green-400/60"
            onClick={() => setShowAll(true)}
          >
            … {lines.length - MAX_LINES} more lines (click to show)
          </span>
        )}
      </pre>
    </div>
  )
}

function StatusDot({ status }: { status: ToolCallStatus }) {
  if (status === 'pending') {
    return (
      <span className="text-[11px] text-amber-400 animate-pulse shrink-0 leading-none">
        ◌
      </span>
    )
  }
  if (status === 'ok') {
    return (
      <span className="text-[11px] text-emerald-400/80 shrink-0 leading-none">✓</span>
    )
  }
  if (status === 'error') {
    return <span className="text-[11px] text-red-400 shrink-0 leading-none">✗</span>
  }
  // blocked
  return <span className="text-[11px] text-amber-500/70 shrink-0 leading-none">⊘</span>
}

// Stable done quip per entry — pick from DONE_QUIPS based on id hash
function doneQuipFor(id: string): string {
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0
  }
  return DONE_QUIPS[Math.abs(hash) % DONE_QUIPS.length]
}

function TerminalEntry({ entry }: { entry: ToolCallEntry }) {
  const isPending = entry.status === 'pending'
  const isError = entry.status === 'error'
  const isBlocked = entry.status === 'blocked'

  // Determine code to show (only for execute_python)
  let codePreview: string | null = null
  if (entry.name === 'execute_python' && entry.inputPreview) {
    // inputPreview is JSON-encoded args: {"code": "..."} — try to parse
    try {
      const parsed = JSON.parse(entry.inputPreview) as Record<string, unknown>
      if (typeof parsed.code === 'string') {
        codePreview = parsed.code
      }
    } catch {
      // not JSON, use raw preview
      codePreview = entry.inputPreview
    }
  }

  const hasStdout =
    entry.name === 'execute_python' &&
    !isPending &&
    entry.stdout &&
    entry.stdout.trim() !== '' &&
    entry.stdout !== '(no output)'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className={cn(
        'rounded border px-2.5 py-2 space-y-1',
        isError
          ? 'border-red-900/40 bg-red-950/15'
          : isBlocked
            ? 'border-amber-900/40 bg-amber-950/15'
            : isPending
              ? 'border-amber-800/30 bg-amber-950/8'
              : 'border-surface-800/70 bg-surface-900/40',
      )}
    >
      {/* Header row */}
      <div className="flex items-center gap-1.5 min-w-0">
        <StatusDot status={entry.status} />
        <span
          className={cn(
            'text-[11px] font-mono font-semibold truncate',
            isError
              ? 'text-red-400'
              : isBlocked
                ? 'text-amber-500/80'
                : isPending
                  ? 'text-amber-300/90'
                  : 'text-surface-300/80',
          )}
        >
          {entry.name}
        </span>

        {/* Running verb or done quip */}
        <div className="flex-1 min-w-0 overflow-hidden">
          {isPending ? (
            <RotatingVerb toolName={entry.name} />
          ) : (
            <span className="text-[10px] font-mono text-surface-600 italic truncate block">
              {isError ? 'failed.' : isBlocked ? 'blocked.' : doneQuipFor(entry.id)}
            </span>
          )}
        </div>

        {/* Timer / elapsed */}
        <div className="ml-auto shrink-0 flex items-center gap-1">
          <span className="text-[10px] font-mono text-surface-700">s{entry.step}</span>
          {isPending && entry.startedAt ? (
            <LiveTimer startedAt={entry.startedAt} />
          ) : entry.startedAt && entry.finishedAt ? (
            <ElapsedBadge startedAt={entry.startedAt} finishedAt={entry.finishedAt} />
          ) : null}
        </div>
      </div>

      {/* Python code block */}
      {codePreview && (
        <PythonCodeBlock code={codePreview} isRunning={isPending} />
      )}

      {/* Python stdout */}
      {hasStdout && <StdoutBlock stdout={entry.stdout!} />}

      {/* Generic preview for non-python or error */}
      {!codePreview && entry.inputPreview && (
        <p className="text-[10px] font-mono text-surface-600 truncate leading-relaxed pl-4">
          {entry.inputPreview}
        </p>
      )}
      {entry.preview && !isPending && entry.name !== 'execute_python' && (
        <p
          className={cn(
            'text-[10px] font-mono leading-relaxed pl-4 line-clamp-2',
            isError ? 'text-red-400/70' : 'text-surface-500',
          )}
        >
          {entry.preview}
        </p>
      )}
    </motion.div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function TerminalPanel(): React.ReactElement {
  const toolCallLog = useChatStore((s) => s.toolCallLog)
  const clearToolCallLog = useChatStore((s) => s.clearToolCallLog)
  const standbyText = useRotatingText(STANDBY_MESSAGES, 3000)
  const scrollRef = useRef<HTMLDivElement>(null)

  const hasRunning = toolCallLog.some((e) => e.status === 'pending')

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [toolCallLog.length])

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-[#09090b]">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 border-b border-surface-800/60 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono font-bold tracking-[0.18em] text-surface-500 uppercase">
            Terminal
          </span>
          {hasRunning && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-1"
            >
              <span className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-[9px] font-mono text-amber-400/70">running</span>
            </motion.span>
          )}
        </div>
        {toolCallLog.length > 0 && (
          <button
            onClick={clearToolCallLog}
            title="Clear log"
            className="p-1 rounded text-surface-600 hover:text-surface-400 hover:bg-surface-800/60 transition-colors"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* Content */}
      {toolCallLog.length === 0 ? (
        <div className="flex flex-col flex-1 items-center justify-center px-4 gap-2">
          <span className="text-[10px] font-mono text-surface-600">
            <AnimatePresence mode="wait">
              <motion.span
                key={standbyText}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="block"
              >
                {standbyText}
              </motion.span>
            </AnimatePresence>
          </span>
          <span className="text-[9px] font-mono text-surface-700">
            tool calls will appear here
          </span>
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="flex flex-col gap-2 p-3 overflow-y-auto flex-1 min-h-0"
        >
          <AnimatePresence initial={false}>
            {toolCallLog.map((entry) => (
              <TerminalEntry key={entry.id} entry={entry} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
