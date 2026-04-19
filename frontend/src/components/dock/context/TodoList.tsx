import { cn } from '@/lib/utils'
import type { TodoItem } from '@/lib/store'

interface TodoListProps {
  todos: TodoItem[]
  onFocus?: (id: string) => void
}

const STATUS_COLOR: Record<TodoItem['status'], string> = {
  pending: 'bg-fg-3',
  in_progress: 'bg-acc animate-pulse',
  completed: 'bg-ok',
}

export function TodoList({ todos, onFocus }: TodoListProps) {
  if (todos.length === 0) {
    return <div className="mono text-[10.5px] text-fg-3">No todos</div>
  }
  return (
    <ul className="flex flex-col gap-1">
      {todos.map((t) => (
        <li key={t.id}>
          <button
            type="button"
            onClick={() => onFocus?.(t.id)}
            className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-[12px] text-fg-1 hover:bg-bg-2 focus-ring"
          >
            <span className={cn('h-1.5 w-1.5 rounded-full', STATUS_COLOR[t.status])} />
            <span className="truncate">{t.content}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
