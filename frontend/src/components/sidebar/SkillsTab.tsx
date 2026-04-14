import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { listSkills, type SkillEntry } from '@/lib/api-skills'
import { cn } from '@/lib/utils'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

const LEVEL_LABELS: Record<number, string> = {
  1: 'PRIMITIVES',
  2: 'ANALYTICAL',
  3: 'COMPOSITION',
}

function getLevelLabel(level: number): string {
  return LEVEL_LABELS[level] ?? `LEVEL ${level}`
}

export function SkillsTab(): React.ReactElement {
  const [state, setState] = useState<LoadState>('idle')
  const [skills, setSkills] = useState<SkillEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const refresh = useCallback(async () => {
    setState('loading')
    setError(null)
    try {
      const data = await listSkills()
      setSkills(data)
      setState('ready')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load skills'
      setError(message)
      setState('error')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const toggleExpanded = useCallback((name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }, [])

  const q = search.trim().toLowerCase()
  const filteredSkills = q
    ? skills.filter((s) => s.name.toLowerCase().includes(q))
    : skills

  const levelGroups = new Map<number, SkillEntry[]>()
  for (const skill of filteredSkills) {
    const existing = levelGroups.get(skill.level)
    if (existing) {
      existing.push(skill)
    } else {
      levelGroups.set(skill.level, [skill])
    }
  }
  const sortedLevels = [...levelGroups.keys()].sort((a, b) => a - b)

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-surface-800 flex-shrink-0 gap-2">
        <h2 className="text-xs font-semibold text-surface-300 uppercase tracking-wide flex-shrink-0">
          Skills
        </h2>
        <input
          type="search"
          placeholder="search…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={cn(
            'flex-1 min-w-0 bg-surface-800 border border-surface-700 rounded px-2 py-0.5',
            'text-xs font-mono text-surface-200 placeholder:text-surface-600',
            'focus:outline-none focus:border-brand-500 focus:ring-0',
          )}
          aria-label="Search skills"
        />
      </div>

      {error && (
        <div
          role="alert"
          className="mx-3 my-2 rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300"
        >
          {error}
        </div>
      )}

      <div
        className="flex-1 min-h-0 overflow-y-auto pb-2"
        role="list"
        aria-label="Skills by level"
      >
        {state === 'loading' && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            Loading skills…
          </p>
        )}

        {state === 'ready' && filteredSkills.length === 0 && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            No skills found.
          </p>
        )}

        {sortedLevels.map((level) => {
          const levelSkills = levelGroups.get(level) ?? []
          const isAlwaysLoaded = level === 1
          const label = getLevelLabel(level)

          return (
            <div key={level} role="listitem" className="mb-1">
              <div className="px-3 py-1.5 flex items-center gap-2 border-b border-surface-800/60">
                <span className="text-[10px] font-mono font-semibold text-surface-500 uppercase tracking-widest">
                  Level {level} — {label}
                </span>
              </div>

              <div className="px-2 py-0.5 space-y-px">
                {levelSkills.map((skill) => {
                  const isExpanded = expanded.has(skill.name)
                  const hasDeps = skill.requires.length > 0 || skill.used_by.length > 0
                  const hasDetails = skill.description || hasDeps

                  return (
                    <div key={skill.name}>
                      <button
                        type="button"
                        onClick={() => {
                          if (hasDetails) toggleExpanded(skill.name)
                        }}
                        className={cn(
                          'w-full flex items-center gap-2 px-2 py-1 rounded text-left',
                          'transition-colors',
                          hasDetails
                            ? 'hover:bg-surface-800/60 cursor-pointer'
                            : 'cursor-default',
                          'text-surface-300',
                        )}
                        aria-expanded={hasDetails ? isExpanded : undefined}
                        title={skill.description || skill.name}
                      >
                        {hasDetails ? (
                          isExpanded ? (
                            <ChevronDown
                              className="w-3 h-3 flex-shrink-0 text-surface-500"
                              aria-hidden
                            />
                          ) : (
                            <ChevronRight
                              className="w-3 h-3 flex-shrink-0 text-surface-500"
                              aria-hidden
                            />
                          )
                        ) : (
                          <span className="w-3 h-3 flex-shrink-0 flex items-center justify-center">
                            <span className="w-1.5 h-1.5 rounded-full bg-surface-600" aria-hidden />
                          </span>
                        )}

                        <span className="flex-1 min-w-0 font-mono text-xs truncate">
                          {skill.name}
                        </span>

                        <span className="text-[10px] font-mono text-surface-600 flex-shrink-0">
                          v{skill.version}
                        </span>

                        {isAlwaysLoaded && (
                          <span className="text-[10px] font-mono text-brand-500/70 flex-shrink-0 ml-1">
                            always loaded
                          </span>
                        )}
                      </button>

                      {isExpanded && hasDetails && (
                        <div className="ml-7 mr-2 mb-1 pl-2 border-l border-surface-700/60 space-y-1.5 py-1.5">
                          {skill.description && (
                            <p className="text-[11px] text-surface-400 leading-relaxed">
                              {skill.description}
                            </p>
                          )}

                          {skill.requires.length > 0 && (
                            <div>
                              <span className="text-[10px] font-mono text-surface-600 uppercase tracking-wider">
                                requires
                              </span>
                              <div className="flex flex-wrap gap-1 mt-0.5">
                                {skill.requires.map((dep) => (
                                  <span
                                    key={dep}
                                    className="text-[10px] font-mono bg-surface-800 text-surface-400 px-1.5 py-0.5 rounded"
                                  >
                                    {dep}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {skill.used_by.length > 0 && (
                            <div>
                              <span className="text-[10px] font-mono text-surface-600 uppercase tracking-wider">
                                used by
                              </span>
                              <div className="flex flex-wrap gap-1 mt-0.5">
                                {skill.used_by.map((consumer) => (
                                  <span
                                    key={consumer}
                                    className="text-[10px] font-mono bg-surface-800 text-surface-400 px-1.5 py-0.5 rounded"
                                  >
                                    {consumer}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
