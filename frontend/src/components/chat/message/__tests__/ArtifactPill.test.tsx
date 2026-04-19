import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ArtifactPill } from '../ArtifactPill'

describe('ArtifactPill', () => {
  it('renders name + size', () => {
    render(
      <ArtifactPill
        id="a"
        type="chart"
        name="residuals.png"
        size="184 KB"
        missing={false}
        onOpen={() => {}}
      />,
    )
    expect(screen.getByText('residuals.png')).toBeInTheDocument()
    expect(screen.getByText('184 KB')).toBeInTheDocument()
  })

  it('fires onOpen on click', () => {
    const spy = vi.fn()
    render(
      <ArtifactPill id="a" type="chart" name="x" size="" missing={false} onOpen={spy} />,
    )
    fireEvent.click(screen.getByRole('button'))
    expect(spy).toHaveBeenCalledWith('a')
  })

  it('marks missing artifacts as disabled with suffix', () => {
    render(
      <ArtifactPill id="a" type="chart" name="gone" size="" missing={true} onOpen={() => {}} />,
    )
    expect(screen.getByRole('button')).toBeDisabled()
    expect(screen.getByText(/removed/i)).toBeInTheDocument()
  })
})
