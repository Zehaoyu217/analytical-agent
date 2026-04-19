import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Dock } from '../Dock'
import { useUiStore } from '@/lib/ui-store'
import { useChatStore } from '@/lib/store'

vi.mock('../DockProgress', () => ({
  DockProgress: () => <div data-testid="dock-progress">DockProgress</div>,
}))
vi.mock('../DockContext', () => ({
  DockContext: () => <div data-testid="dock-context">DockContext</div>,
}))
vi.mock('../DockArtifacts', () => ({
  DockArtifacts: () => <div data-testid="dock-artifacts">DockArtifacts</div>,
}))

function resetUi(): void {
  useUiStore.setState({
    v: 2,
    threadW: 240,
    dockW: 320,
    threadsOpen: true,
    dockOpen: true,
    dockTab: 'progress',
    density: 'default',
    threadsOverridden: false,
    dockOverridden: false,
    progressExpanded: [],
    artifactView: 'grid',
    recentCommandIds: [],
    traceTab: 'context',
  })
  useChatStore.setState({
    toolCallLog: [],
    conversations: [],
    activeConversationId: null,
  })
}

beforeEach(() => {
  resetUi()
})

describe('Dock', () => {
  it('renders three tabs with Progress selected by default', () => {
    render(<Dock />)
    expect(
      screen.getByRole('tab', { name: 'Progress', selected: true }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: 'Context', selected: false }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: 'Artifacts', selected: false }),
    ).toBeInTheDocument()
  })

  it('clicking Context switches the active tab', async () => {
    const user = userEvent.setup()
    render(<Dock />)
    await user.click(screen.getByRole('tab', { name: 'Context' }))
    expect(useUiStore.getState().dockTab).toBe('context')
  })

  it('mounts DockProgress when dockTab=progress', () => {
    render(<Dock />)
    expect(screen.getByTestId('dock-progress')).toBeInTheDocument()
  })

  it('renders DockContext when dockTab=context', () => {
    useUiStore.setState({ dockTab: 'context' })
    render(<Dock />)
    expect(screen.getByTestId('dock-context')).toBeInTheDocument()
  })

  it('renders DockArtifacts when dockTab=artifacts', () => {
    useUiStore.setState({ dockTab: 'artifacts' })
    render(<Dock />)
    expect(screen.getByTestId('dock-artifacts')).toBeInTheDocument()
  })

  it('collapse chevron calls toggleDock', async () => {
    const user = userEvent.setup()
    render(<Dock />)
    expect(useUiStore.getState().dockOpen).toBe(true)
    await user.click(screen.getByRole('button', { name: /collapse dock/i }))
    expect(useUiStore.getState().dockOpen).toBe(false)
    expect(useUiStore.getState().dockOverridden).toBe(true)
  })

  it('includes a resizer with inverted drag semantics', () => {
    render(<Dock />)
    const sep = screen.getByRole('separator', { name: /resize dock/i })
    expect(sep).toHaveAttribute('aria-valuemin', '240')
    expect(sep).toHaveAttribute('aria-valuemax', '480')
  })
})
