import type { SlashCommand } from '@/lib/api-backend'

export function filterSlashCommands(
  commands: SlashCommand[],
  query: string,
): SlashCommand[] {
  const q = query.trim().toLowerCase()
  if (!q) return commands
  return commands.filter(
    (c) => c.id.toLowerCase().includes(q) || c.label.toLowerCase().includes(q),
  )
}
