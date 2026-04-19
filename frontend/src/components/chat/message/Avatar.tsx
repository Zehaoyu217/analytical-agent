interface AvatarProps {
  role: 'user' | 'assistant'
  initial: string
}

export function Avatar({ role, initial }: AvatarProps) {
  const isUser = role === 'user'
  return (
    <div
      aria-label={`${role} avatar`}
      className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-[12px] font-semibold"
      style={{
        background: isUser
          ? 'linear-gradient(135deg, oklch(0.72 0.09 35), oklch(0.58 0.11 30))'
          : 'var(--acc)',
        color: isUser ? '#fff' : 'var(--acc-fg)',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.15), 0 1px 2px rgba(0,0,0,0.05)',
        letterSpacing: '-0.02em',
      }}
    >
      {initial}
    </div>
  )
}
