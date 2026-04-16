import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  /** Human-readable name for this boundary — appears in error UI and console. */
  name?: string
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const boundary = this.props.name ?? 'Unknown'
    console.error(`[ErrorBoundary:${boundary}] caught:`, error, info.componentStack)
  }

  reset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    if (this.props.fallback) return this.props.fallback

    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center">
        <p className="font-mono text-xs uppercase tracking-widest text-surface-500">
          {this.props.name ?? 'Component'} error
        </p>
        <p className="font-mono text-sm text-error max-w-prose break-words">
          {error.message}
        </p>
        <button
          onClick={this.reset}
          className="font-mono text-xs px-3 py-1.5 border border-surface-700 text-surface-300 hover:text-surface-100 hover:border-surface-500 transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }
}
