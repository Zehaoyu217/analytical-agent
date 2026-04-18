import { TopHUD } from './TopHUD'
import { ChatMain } from './ChatMain'
import { RightRail } from './RightRail'
import './cockpit.css'

export function Cockpit() {
  return (
    <div className="cockpit" role="application" aria-label="Analytical cockpit">
      <TopHUD />
      <div className="cockpit__body">
        <div className="cockpit__main">
          <ChatMain />
        </div>
        <aside className="cockpit__rail" aria-label="Agent rail">
          <RightRail />
        </aside>
      </div>
    </div>
  )
}
