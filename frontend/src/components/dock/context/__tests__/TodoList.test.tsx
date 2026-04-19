import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TodoList } from '../TodoList'

describe('TodoList', () => {
  it('renders empty state', () => {
    render(<TodoList todos={[]} />)
    expect(screen.getByText(/no todos/i)).toBeInTheDocument()
  })
  it('renders todos with status dot', () => {
    render(
      <TodoList
        todos={[
          { id: 't1', content: 'load data', status: 'in_progress' },
          { id: 't2', content: 'train', status: 'pending' },
        ]}
      />,
    )
    expect(screen.getByText('load data')).toBeInTheDocument()
    expect(screen.getByText('train')).toBeInTheDocument()
  })
})
