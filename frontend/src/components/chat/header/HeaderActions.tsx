import { SearchButton } from './SearchButton'
import { ForkButton } from './ForkButton'
import { ExportMenu } from './ExportMenu'
import { ProgressToggle } from './ProgressToggle'
import { MoreMenu } from './MoreMenu'
import { useCommandRegistry } from '@/hooks/useCommandRegistry'

interface HeaderActionsProps {
  conversationId: string
  onRename: () => void
}

export function HeaderActions({ conversationId, onRename }: HeaderActionsProps) {
  const { openHelp } = useCommandRegistry()
  return (
    <div className="flex items-center gap-2">
      <SearchButton onOpen={openHelp} />
      <ForkButton conversationId={conversationId} />
      <ExportMenu conversationId={conversationId} />
      <ProgressToggle />
      <MoreMenu conversationId={conversationId} onRename={onRename} />
    </div>
  )
}
