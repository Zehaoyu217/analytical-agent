import { AttachButton } from './AttachButton'

interface IconRowProps {
  conversationId: string
}

export function IconRow({ conversationId }: IconRowProps) {
  return (
    <div className="flex items-center gap-0.5">
      <AttachButton conversationId={conversationId} />
    </div>
  )
}
