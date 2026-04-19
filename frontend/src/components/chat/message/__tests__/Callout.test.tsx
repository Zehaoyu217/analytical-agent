import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Callout } from '../Callout'

describe('Callout', () => {
  it.each([
    ['warn' as const],
    ['err' as const],
    ['info' as const],
  ])('renders %s kind with label and text', (kind) => {
    render(<Callout kind={kind} label="data quality" text="31% nulls" />)
    expect(screen.getByText('data quality')).toBeInTheDocument()
    expect(screen.getByText('31% nulls')).toBeInTheDocument()
  })
})
