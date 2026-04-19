import { Search } from 'lucide-react'

interface SearchButtonProps {
  onOpen: () => void
}

export function SearchButton({ onOpen }: SearchButtonProps) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="mr-1 flex items-center gap-1.5 rounded-md border px-2 py-1 text-[12px]"
      style={{
        borderColor: 'var(--line-2)',
        background: 'var(--bg-1)',
        color: 'var(--fg-2)',
      }}
    >
      <Search size={11} />
      <span>Search</span>
      <span className="kbd ml-0.5">⌘K</span>
    </button>
  )
}
