import { AttachButton } from './AttachButton'
import { MentionButton } from './MentionButton'
import { SkillButton } from './SkillButton'
import { VoiceButton } from './VoiceButton'

interface IconRowProps {
  conversationId: string
  onInsert: (token: string) => void
  onTranscript: (text: string) => void
}

export function IconRow({ conversationId, onInsert, onTranscript }: IconRowProps) {
  return (
    <div className="flex items-center gap-0.5">
      <AttachButton conversationId={conversationId} />
      <MentionButton onInsert={onInsert} />
      <SkillButton onInsert={onInsert} />
      <VoiceButton onTranscript={onTranscript} />
    </div>
  )
}
