import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { JudgeVariance } from './JudgeVariance';

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      variance: { detection_recall: 0.2, false_positive_handling: 0.7 },
      threshold_exceeded: ['false_positive_handling'],
    }),
  }) as unknown as typeof fetch;
});

describe('JudgeVariance', () => {
  it('shows dimension variance and flags exceeded ones', async () => {
    render(<JudgeVariance traceId="eval-x" />);
    await waitFor(() => {
      expect(screen.getByText(/false_positive_handling/)).toBeInTheDocument();
      expect(screen.getByText(/0\.70/)).toBeInTheDocument();
      expect(screen.getByText(/exceeded/i)).toBeInTheDocument();
    });
  });
});
