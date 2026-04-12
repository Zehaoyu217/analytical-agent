import { useEffect, useState } from 'react';
import { fetchPromptAssembly, PromptAssembly } from './api';

interface Props {
  traceId: string;
  stepId: string;
}

export function PromptInspector({ traceId, stepId }: Props) {
  const [data, setData] = useState<PromptAssembly | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPromptAssembly(traceId, stepId)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [traceId, stepId]);

  if (error) return <div className="sop-error">Error: {error}</div>;
  if (data === null) return <div className="sop-loading">Loading…</div>;
  if (data.sections.length === 0) {
    return <div className="sop-empty">No prompt sections for this step.</div>;
  }

  return (
    <div className="sop-prompt-inspector">
      <h3>Prompt Assembly — {traceId} / {stepId}</h3>
      {data.conflicts.length > 0 && (
        <div className="sop-conflicts">
          <strong>Conflicts:</strong>
          <ul>{data.conflicts.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </div>
      )}
      {data.sections.map((s, i) => (
        <div key={i} className="sop-prompt-section">
          <div className="sop-prompt-source">
            {s.source} (lines {s.lines})
          </div>
          <pre className="sop-prompt-text">{s.text}</pre>
        </div>
      ))}
    </div>
  );
}
