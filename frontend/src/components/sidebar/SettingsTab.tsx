import { useCallback, useEffect, useState } from 'react'
import { backend, type UserSettings, type ThemePreference, type ModelGroup } from '@/lib/api-backend'
import { useTheme } from '@/components/layout/ThemeProvider'
import { cn } from '@/lib/utils'

const THEME_OPTIONS: Array<{ value: ThemePreference; label: string }> = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
]

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

const SAVED_MESSAGE_MS = 2000

export function SettingsTab() {
  const { setTheme } = useTheme()
  const [settings, setSettings] = useState<UserSettings | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [modelGroups, setModelGroups] = useState<ModelGroup[]>([])

  useEffect(() => {
    let cancelled = false
    backend.settings
      .get()
      .then((s) => {
        if (!cancelled) setSettings(s)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Failed to load settings'
        setLoadError(message)
      })
    backend.models
      .list()
      .then((r) => {
        if (!cancelled) setModelGroups(r.groups)
      })
      .catch(() => {
        // model list is best-effort; silently ignore
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (saveState !== 'saved') return
    const id = window.setTimeout(() => setSaveState('idle'), SAVED_MESSAGE_MS)
    return () => window.clearTimeout(id)
  }, [saveState])

  const handleThemeChange = useCallback(
    (value: ThemePreference) => {
      setSettings((prev) => (prev ? { ...prev, theme: value } : prev))
      setTheme(value)
    },
    [setTheme],
  )

  const handleModelChange = useCallback((value: string) => {
    setSettings((prev) => (prev ? { ...prev, model: value } : prev))
  }, [])

  const handleSendOnEnterChange = useCallback((value: boolean) => {
    setSettings((prev) => (prev ? { ...prev, send_on_enter: value } : prev))
  }, [])

  const handleSave = useCallback(async () => {
    if (!settings) return
    setSaveState('saving')
    setSaveError(null)
    try {
      const next = await backend.settings.put(settings)
      setSettings(next)
      setSaveState('saved')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save settings'
      setSaveError(message)
      setSaveState('error')
    }
  }, [settings])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-3 py-2 border-b border-surface-800 flex-shrink-0">
        <h2 className="text-xs font-semibold text-surface-300 uppercase tracking-wide">
          Settings
        </h2>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-5">
        {loadError && (
          <div
            role="alert"
            className="rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300"
          >
            {loadError}
          </div>
        )}

        {!settings && !loadError && (
          <p className="text-xs text-surface-500">Loading settings…</p>
        )}

        {settings && (
          <>
            <fieldset>
              <legend className="text-xs font-semibold text-surface-300 mb-2">
                Theme
              </legend>
              <div className="space-y-1.5">
                {THEME_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className={cn(
                      'flex items-center gap-2 cursor-pointer text-sm',
                      'text-surface-300 hover:text-surface-100',
                    )}
                  >
                    <input
                      type="radio"
                      name="theme"
                      value={opt.value}
                      checked={settings.theme === opt.value}
                      onChange={() => handleThemeChange(opt.value)}
                      className="accent-brand-500"
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div>
              <label
                htmlFor="settings-model"
                className="block text-xs font-semibold text-surface-300 mb-1.5"
              >
                Model
              </label>
              {modelGroups.length > 0 ? (
                <>
                  <select
                    id="settings-model"
                    value={settings.model}
                    onChange={(e) => handleModelChange(e.target.value)}
                    className={cn(
                      'w-full rounded-md border border-surface-700 bg-surface-800 px-2.5 py-1.5',
                      'text-sm text-surface-100',
                      'focus:border-brand-500 focus:outline-none',
                    )}
                  >
                    {modelGroups.map((group) => (
                      <optgroup
                        key={group.provider}
                        label={group.available ? group.label : `${group.label} — pending`}
                      >
                        {group.models.map((m) => (
                          <option key={m.id} value={m.id} disabled={!group.available}>
                            {m.label} — {m.description}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  {modelGroups.some((g) => !g.available && g.note) && (
                    <div className="mt-1.5 space-y-0.5">
                      {modelGroups
                        .filter((g) => !g.available && g.note)
                        .map((g) => (
                          <p key={g.provider} className="text-xs text-amber-500/80">
                            {g.label}: {g.note}
                          </p>
                        ))}
                    </div>
                  )}
                </>
              ) : (
                <input
                  id="settings-model"
                  type="text"
                  value={settings.model}
                  onChange={(e) => handleModelChange(e.target.value)}
                  className={cn(
                    'w-full rounded-md border border-surface-700 bg-surface-800 px-2.5 py-1.5',
                    'text-sm text-surface-100 placeholder:text-surface-500',
                    'focus:border-brand-500 focus:outline-none',
                  )}
                />
              )}
              <p className="mt-1 text-xs text-surface-500">{settings.model}</p>
            </div>

            <div>
              <label
                htmlFor="settings-send-on-enter"
                className="flex items-center justify-between cursor-pointer"
              >
                <div>
                  <div className="text-xs font-semibold text-surface-300">
                    Send on Enter
                  </div>
                  <div className="text-xs text-surface-500 mt-0.5">
                    Press Enter to send; Shift+Enter for a new line.
                  </div>
                </div>
                <input
                  id="settings-send-on-enter"
                  type="checkbox"
                  role="switch"
                  aria-checked={settings.send_on_enter}
                  checked={settings.send_on_enter}
                  onChange={(e) => handleSendOnEnterChange(e.target.checked)}
                  className="w-9 h-5 accent-brand-500"
                />
              </label>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saveState === 'saving'}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm transition-colors',
                  'bg-brand-600 text-white hover:bg-brand-700',
                  'disabled:bg-surface-700 disabled:text-surface-500',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
                )}
              >
                {saveState === 'saving' ? 'Saving…' : 'Save'}
              </button>
              {saveState === 'saved' && (
                <span
                  role="status"
                  className="text-xs text-green-400 transition-opacity"
                >
                  Saved ✓
                </span>
              )}
              {saveError && (
                <span role="alert" className="text-xs text-red-300">
                  {saveError}
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
