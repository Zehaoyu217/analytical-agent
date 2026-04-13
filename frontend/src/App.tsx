import { useEffect } from 'react'
import { StatusBar } from './panels/StatusBar'
import { ChatPanel } from './panels/ChatPanel'
import { DevToolsPanel } from './devtools/DevToolsPanel'
import { useDevtoolsStore } from './stores/devtools'

export default function App() {
  const toggle = useDevtoolsStore((s) => s.toggle)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'D') {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [toggle])

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: '#0a0a0f',
      color: '#e0e0e8',
    }}>
      <ChatPanel />
      <DevToolsPanel />
      <StatusBar />
    </div>
  )
}
