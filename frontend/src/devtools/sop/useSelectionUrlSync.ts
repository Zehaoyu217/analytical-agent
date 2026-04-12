import { useEffect } from 'react'
import { useDevtoolsStore } from '../../stores/devtools'

export function useSelectionUrlSync(): void {
  const selectedTraceId = useDevtoolsStore((s) => s.selectedTraceId)
  const selectedStepId = useDevtoolsStore((s) => s.selectedStepId)
  const setSelectedTrace = useDevtoolsStore((s) => s.setSelectedTrace)
  const setSelectedStep = useDevtoolsStore((s) => s.setSelectedStep)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const trace = params.get('trace')
    const step = params.get('step')
    if (trace) {
      setSelectedTrace(trace)
      if (step) setSelectedStep(step)
    }
  }, [setSelectedTrace, setSelectedStep])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (selectedTraceId) {
      params.set('trace', selectedTraceId)
    } else {
      params.delete('trace')
    }
    if (selectedStepId) {
      params.set('step', selectedStepId)
    } else {
      params.delete('step')
    }
    const search = params.toString()
    const newUrl =
      window.location.pathname + (search ? `?${search}` : '') + window.location.hash
    window.history.replaceState(null, '', newUrl)
  }, [selectedTraceId, selectedStepId])
}
