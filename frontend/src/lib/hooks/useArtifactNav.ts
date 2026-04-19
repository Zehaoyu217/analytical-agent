import { useCallback, useMemo } from 'react'
import { useChatStore, type Artifact } from '@/lib/store'

export function useArtifactNav(currentId: string | null) {
  const artifacts = useChatStore((s) => s.artifacts)
  const index = useMemo(
    () => artifacts.findIndex((a) => a.id === currentId),
    [artifacts, currentId],
  )
  const current: Artifact | null = index >= 0 ? artifacts[index] : null
  const next = useCallback(
    () => (artifacts.length > 0 ? artifacts[(index + 1) % artifacts.length].id : null),
    [artifacts, index],
  )
  const prev = useCallback(
    () =>
      artifacts.length > 0
        ? artifacts[(index - 1 + artifacts.length) % artifacts.length].id
        : null,
    [artifacts, index],
  )
  return { current, next, prev, count: artifacts.length, index }
}
