import { useMemo } from 'react'
import { useChatStore } from '@/lib/store'
import { useUiStore } from '@/lib/ui-store'
import { ArtifactPill } from './ArtifactPill'

interface ArtifactPillRowProps {
  artifactIds: string[]
}

export function ArtifactPillRow({ artifactIds }: ArtifactPillRowProps) {
  const artifacts = useChatStore((s) => s.artifacts)
  const setRightPanelTab = useChatStore((s) => s.setRightPanelTab)
  const setDockOpen = useUiStore((s) => s.setDockOpen)
  const byId = useMemo(
    () => new Map(artifacts.map((a) => [a.id, a])),
    [artifacts],
  )
  if (artifactIds.length === 0) return null
  return (
    <div>
      {artifactIds.map((id) => {
        const a = byId.get(id)
        return (
          <ArtifactPill
            key={id}
            id={id}
            type={a?.type ?? 'file'}
            name={a?.title ?? 'Artifact'}
            size=""
            missing={!a}
            onOpen={(artId) => {
              setDockOpen(true)
              setRightPanelTab('artifacts')
              window.dispatchEvent(
                new CustomEvent('focusArtifact', { detail: { artifactId: artId } }),
              )
            }}
          />
        )
      })}
    </div>
  )
}
