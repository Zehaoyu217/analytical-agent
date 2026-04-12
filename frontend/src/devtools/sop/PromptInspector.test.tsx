import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { PromptInspector } from './PromptInspector'
import { useDevtoolsStore } from '../../stores/devtools'

const summaryBody = {
  summary: {
    session_id: 's-001',
    level: 1,
    outcome: 'failure',
    final_grade: 'F',
    turn_count: 2,
    llm_call_count: 2,
    step_ids: ['s1', 's2'],
  },
}

const assemblyBody = {
  sections: [{ source: 'system', text: 'sys', lines: 1 }],
  total_lines: 1,
  conflicts: [],
}

describe('PromptInspector', () => {
  beforeEach(() => {
    useDevtoolsStore.setState({ selectedTraceId: 't-1', selectedStepId: 's1' })
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('/prompt/')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(assemblyBody) })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(summaryBody) })
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders a dropdown populated from step_ids', async () => {
    render(<PromptInspector traceId="t-1" stepId="s1" />)
    const select = await screen.findByRole('combobox')
    const options = (select as HTMLSelectElement).querySelectorAll('option')
    expect(options.length).toBe(2)
    expect(options[0].value).toBe('s1')
    expect(options[1].value).toBe('s2')
  })

  it('updates selectedStepId when the dropdown changes', async () => {
    render(<PromptInspector traceId="t-1" stepId="s1" />)
    const select = await screen.findByRole('combobox')
    fireEvent.change(select, { target: { value: 's2' } })
    await waitFor(() => {
      expect(useDevtoolsStore.getState().selectedStepId).toBe('s2')
    })
  })

  it('renders the sections from the assembly', async () => {
    render(<PromptInspector traceId="t-1" stepId="s1" />)
    await screen.findByText('sys')
  })
})
