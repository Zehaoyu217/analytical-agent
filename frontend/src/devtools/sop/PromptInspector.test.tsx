import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { PromptInspector } from './PromptInspector';

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      sections: [
        { source: 'backend/app/prompts/system.md', lines: '1-10', text: 'You are an analyst.' },
        { source: 'backend/app/skills/sql/SKILL.md', lines: '1-5', text: 'Use DuckDB.' },
      ],
      conflicts: [],
    }),
  }) as unknown as typeof fetch;
});

describe('PromptInspector', () => {
  it('renders each section with file-source attribution', async () => {
    render(<PromptInspector traceId="eval-x" stepId="step-3" />);
    await waitFor(() => {
      expect(screen.getByText(/system\.md/)).toBeInTheDocument();
      expect(screen.getByText(/SKILL\.md/)).toBeInTheDocument();
      expect(screen.getByText(/You are an analyst/)).toBeInTheDocument();
      expect(screen.getByText(/Use DuckDB/)).toBeInTheDocument();
    });
  });
});
