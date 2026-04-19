import { describe, it, expect } from 'vitest'
import { filterSlashCommands } from '../slash'
import type { SlashCommand } from '@/lib/api-backend'

const list: SlashCommand[] = [
  { id: 'help', label: 'Help', description: '' },
  { id: 'clear', label: 'Clear', description: '' },
  { id: 'new', label: 'New chat', description: '' },
]

describe('filterSlashCommands', () => {
  it('returns all when query empty', () => {
    expect(filterSlashCommands(list, '')).toEqual(list)
  })
  it('case-insensitive id/label match', () => {
    expect(filterSlashCommands(list, 'HE').map((c) => c.id)).toEqual(['help'])
    expect(filterSlashCommands(list, 'chat').map((c) => c.id)).toEqual(['new'])
  })
  it('returns [] when nothing matches', () => {
    expect(filterSlashCommands(list, 'xyzzy')).toEqual([])
  })
})
