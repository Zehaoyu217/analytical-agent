import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { ArtifactViewer } from '../ArtifactViewer'
import { useChatStore, type Artifact } from '@/lib/store'

const a1: Artifact = {
  id: 'a1',
  type: 'analysis',
  title: 'Notes',
  content: 'hello',
  format: 'text',
  session_id: 's',
  created_at: 1,
  metadata: {},
}
const a2: Artifact = { ...a1, id: 'a2', title: 'More', content: 'world' }

describe('ArtifactViewer', () => {
  beforeEach(() => {
    useChatStore.setState({ artifacts: [a1, a2] } as never)
  })

  it('opens on focusArtifact event and closes on ESC', () => {
    render(<ArtifactViewer />)
    act(() => {
      window.dispatchEvent(new CustomEvent('focusArtifact', { detail: { id: 'a1' } }))
    })
    expect(screen.getByText('Notes')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByText('Notes')).toBeNull()
  })

  it('cycles with arrow keys', () => {
    render(<ArtifactViewer />)
    act(() => {
      window.dispatchEvent(new CustomEvent('focusArtifact', { detail: { id: 'a1' } }))
    })
    fireEvent.keyDown(document, { key: 'ArrowRight' })
    expect(screen.getByText('More')).toBeInTheDocument()
  })
})
