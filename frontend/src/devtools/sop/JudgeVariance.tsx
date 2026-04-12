import { useEffect, useState } from 'react';
import { fetchJudgeVariance, JudgeVarianceResponse } from './api';

interface Props {
  traceId: string;
}

export function JudgeVariance({ traceId }: Props) {
  const [data, setData] = useState<JudgeVarianceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJudgeVariance(traceId)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [traceId]);

  if (error) return <div className="sop-error">Error: {error}</div>;
  if (data === null) return <div className="sop-loading">Loading…</div>;

  const entries = Object.entries(data.variance);
  if (entries.length === 0) {
    return <div className="sop-empty">No variance data for this trace.</div>;
  }

  return (
    <div className="sop-judge-variance">
      <h3>Judge Variance — {traceId}</h3>
      <table>
        <thead>
          <tr><th>Dimension</th><th>Variance</th><th>Status</th></tr>
        </thead>
        <tbody>
          {entries.map(([dim, variance]) => {
            const exceeded = data.threshold_exceeded.includes(dim);
            return (
              <tr key={dim} className={exceeded ? 'exceeded' : ''}>
                <td>{dim}</td>
                <td>{variance.toFixed(2)}</td>
                <td>{exceeded ? 'exceeded' : 'ok'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
