import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ArtifactPillRow } from '../ArtifactPillRow'
import { useChatStore } from '@/lib/store'
import { useUiStore } from '@/lib/ui-store'

describe('ArtifactPillRow', () => {
  beforeEach(() => {
    useChatStore.setState({
      artifacts: [],
      conversations: [],
      activeConversationId: null,
    })
    useUiStore.setState({ ...useUiStore.getState(), dockOpen: false })
  })

  it('renders only artifacts in artifactIds', () => {
    useChatStore.getState().addArtifact({
      id: 'a',
      type: 'chart',
      title: 'A',
      content: '',
      format: 'vega-lite',
      session_id: '',
      created_at: 0,
      metadata: {},
    })
    useChatStore.getState().addArtifact({
      id: 'b',
      type: 'chart',
      title: 'B',
      content: '',
      format: 'vega-lite',
      session_id: '',
      created_at: 0,
      metadata: {},
    })
    render(<ArtifactPillRow artifactIds={['a']} />)
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.queryByText('B')).toBeNull()
  })

  it('opens dock on pill click', () => {
    useChatStore.getState().addArtifact({
      id: 'a',
      type: 'chart',
      title: 'A',
      content: '',
      format: 'vega-lite',
      session_id: '',
      created_at: 0,
      metadata: {},
    })
    render(<ArtifactPillRow artifactIds={['a']} />)
    fireEvent.click(screen.getByRole('button'))
    expect(useUiStore.getState().dockOpen).toBe(true)
  })
})
