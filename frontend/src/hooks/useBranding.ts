/**
 * useBranding — fetch and cache branding configuration from /api/config/branding.
 *
 * The branding config is fetched once on first call and cached in module scope
 * for the lifetime of the page.  Components that need branding values (title,
 * accent colour, spinner phrases) use this hook instead of hardcoding strings.
 */
import { useEffect, useState } from 'react'
import { backend, type BrandingConfig } from '@/lib/api-backend'

const DEFAULTS: BrandingConfig = {
  agent_name: 'Analytical Agent',
  agent_persona: '',
  ui_title: 'Analytical Agent',
  ui_accent_color: '#e0733a',
  ui_spinner_phrases: ['Thinking...', 'Analysing...', 'Running tools...', 'Crunching numbers...'],
}

let _cache: BrandingConfig | null = null
const _listeners: Array<(b: BrandingConfig) => void> = []

function notifyListeners(b: BrandingConfig) {
  _cache = b
  for (const fn of _listeners) fn(b)
}

/** Pre-fetch branding into the module cache without rendering anything. */
export function prefetchBranding(): void {
  if (_cache) return
  backend.config
    .branding()
    .then(notifyListeners)
    .catch(() => {
      /* Silently keep defaults on network error */
    })
}

export function useBranding(): BrandingConfig {
  const [branding, setBranding] = useState<BrandingConfig>(_cache ?? DEFAULTS)

  useEffect(() => {
    if (_cache) {
      setBranding(_cache)
      return
    }
    _listeners.push(setBranding)
    prefetchBranding()
    return () => {
      const idx = _listeners.indexOf(setBranding)
      if (idx !== -1) _listeners.splice(idx, 1)
    }
  }, [])

  return branding
}
