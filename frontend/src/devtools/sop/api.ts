export type Grade = 'A' | 'B' | 'C' | 'F';
export type PreflightVerdict = 'pass' | 'fail' | 'skipped';

export interface SOPSession {
  session_id: string;
  date: string;
  level: number;
  overall_grade_before: Grade;
  preflight: {
    evaluation_bias: PreflightVerdict;
    data_quality: PreflightVerdict;
    determinism: PreflightVerdict;
  };
  triage: { bucket: string; evidence: string[]; hypothesis: string };
  fix: {
    ladder_id: string;
    name: string;
    files_changed: string[];
    model_used_for_fix: string;
    cost_bucket: string;
  };
  outcome: Record<string, unknown>;
  trace_links: Record<string, string>;
}

export async function listSessions(): Promise<SOPSession[]> {
  const resp = await fetch('/api/sop/sessions');
  if (!resp.ok) throw new Error(`listSessions failed: ${resp.status}`);
  const data = (await resp.json()) as { sessions: SOPSession[] };
  return data.sessions;
}

export interface JudgeVarianceResponse {
  variance: Record<string, number>;
  threshold_exceeded: string[];
}

export async function fetchJudgeVariance(
  traceId: string,
  n = 5,
): Promise<JudgeVarianceResponse> {
  const resp = await fetch(`/api/sop/judge-variance/${traceId}?n=${n}`);
  if (!resp.ok) throw new Error(`judge-variance failed: ${resp.status}`);
  return (await resp.json()) as JudgeVarianceResponse;
}
