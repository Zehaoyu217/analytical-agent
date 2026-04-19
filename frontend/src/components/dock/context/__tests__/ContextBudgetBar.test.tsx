import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContextBudgetBar } from '../ContextBudgetBar'

describe('ContextBudgetBar', () => {
  it('shows used / budget labels', () => {
    render(<ContextBudgetBar totalTokens={50_000} budgetTokens={200_000} />)
    expect(screen.getByLabelText(/context budget/i)).toBeInTheDocument()
    expect(screen.getByText(/50\s*k/i)).toBeInTheDocument()
    expect(screen.getByText(/200\s*k/i)).toBeInTheDocument()
  })

  it('adds warn tone at >=60% and err tone at >=85%', () => {
    const { rerender, container } = render(
      <ContextBudgetBar totalTokens={125_000} budgetTokens={200_000} />,
    )
    expect(container.querySelector('[data-tone="warn"]')).not.toBeNull()
    rerender(<ContextBudgetBar totalTokens={180_000} budgetTokens={200_000} />)
    expect(container.querySelector('[data-tone="err"]')).not.toBeNull()
  })
})
