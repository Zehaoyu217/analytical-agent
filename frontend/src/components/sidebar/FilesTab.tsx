import { useCallback, useEffect, useState } from 'react'
import { File, Folder, X } from 'lucide-react'
import {
  backend,
  type FileNode,
  type FileReadResponse,
  type FileTreeResponse,
} from '@/lib/api-backend'
import { cn } from '@/lib/utils'

function formatSize(bytes: number | null): string {
  if (bytes === null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface Crumb {
  label: string
  path: string
}

function crumbsFor(currentPath: string): Crumb[] {
  const crumbs: Crumb[] = [{ label: 'root', path: '' }]
  if (!currentPath) return crumbs
  const parts = currentPath.split('/').filter(Boolean)
  let acc = ''
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part
    crumbs.push({ label: part, path: acc })
  }
  return crumbs
}

export function FilesTab() {
  const [currentPath, setCurrentPath] = useState('')
  const [tree, setTree] = useState<FileTreeResponse | null>(null)
  const [treeError, setTreeError] = useState<string | null>(null)
  const [loadingTree, setLoadingTree] = useState(false)
  const [viewingFile, setViewingFile] = useState<FileReadResponse | null>(null)
  const [loadingFile, setLoadingFile] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)

  const loadTree = useCallback(async (path: string) => {
    setLoadingTree(true)
    setTreeError(null)
    try {
      const next = await backend.files.tree(path || undefined)
      setTree(next)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load files'
      setTreeError(message)
    } finally {
      setLoadingTree(false)
    }
  }, [])

  useEffect(() => {
    void loadTree(currentPath)
  }, [currentPath, loadTree])

  const handleNodeClick = useCallback(async (node: FileNode) => {
    if (node.kind === 'dir') {
      setCurrentPath(node.path)
      return
    }
    setLoadingFile(true)
    setFileError(null)
    try {
      const contents = await backend.files.read(node.path)
      setViewingFile(contents)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to read file'
      setFileError(message)
    } finally {
      setLoadingFile(false)
    }
  }, [])

  const crumbs = crumbsFor(currentPath)

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-3 py-2 border-b border-surface-800 flex-shrink-0">
        <h2 className="text-xs font-semibold text-surface-300 uppercase tracking-wide">
          Files
        </h2>
        <nav
          aria-label="Breadcrumb"
          className="mt-1.5 flex items-center flex-wrap gap-1 text-xs"
        >
          {crumbs.map((crumb, index) => {
            const isLast = index === crumbs.length - 1
            return (
              <div key={crumb.path || 'root'} className="flex items-center gap-1">
                {index > 0 && <span className="text-surface-600">/</span>}
                <button
                  type="button"
                  onClick={() => setCurrentPath(crumb.path)}
                  className={cn(
                    'transition-colors',
                    isLast
                      ? 'text-surface-200 font-medium cursor-default'
                      : 'text-surface-500 hover:text-surface-200',
                  )}
                  disabled={isLast}
                >
                  {crumb.label}
                </button>
              </div>
            )
          })}
        </nav>
      </div>

      {treeError && (
        <div
          role="alert"
          className="mx-3 my-2 rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300"
        >
          {treeError}
        </div>
      )}

      {fileError && (
        <div
          role="alert"
          className="mx-3 my-2 rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300"
        >
          {fileError}
        </div>
      )}

      <div
        className="flex-1 min-h-0 overflow-y-auto px-2 pb-2 space-y-0.5"
        role="list"
        aria-label="File tree"
      >
        {loadingTree && !tree && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">Loading…</p>
        )}
        {tree && tree.entries.length === 0 && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            Empty directory.
          </p>
        )}
        {tree?.entries.map((node) => (
          <button
            key={node.path}
            type="button"
            role="listitem"
            onClick={() => void handleNodeClick(node)}
            className={cn(
              'w-full text-left px-2 py-1.5 rounded-md text-sm',
              'flex items-center gap-2 transition-colors',
              'text-surface-300 hover:bg-surface-800/60 hover:text-surface-100',
            )}
            title={node.path}
          >
            {node.kind === 'dir' ? (
              <Folder className="w-4 h-4 flex-shrink-0 text-surface-400" aria-hidden />
            ) : (
              <File className="w-4 h-4 flex-shrink-0 text-surface-400" aria-hidden />
            )}
            <span className="flex-1 truncate">{node.name}</span>
            {node.kind === 'file' && (
              <span className="text-xs text-surface-500 flex-shrink-0">
                {formatSize(node.size)}
              </span>
            )}
          </button>
        ))}
        {tree?.truncated && (
          <p className="px-3 py-2 text-xs text-surface-500 text-center">
            Listing truncated — too many entries to show.
          </p>
        )}
      </div>

      {(viewingFile || loadingFile) && (
        <FileViewerDialog
          file={viewingFile}
          loading={loadingFile}
          onClose={() => setViewingFile(null)}
        />
      )}
    </div>
  )
}

interface FileViewerDialogProps {
  file: FileReadResponse | null
  loading: boolean
  onClose: () => void
}

function FileViewerDialog({ file, loading, onClose }: FileViewerDialogProps) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="File contents"
      className={cn(
        'fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm',
        'p-4',
      )}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={cn(
          'flex flex-col max-w-3xl w-full max-h-[85vh] rounded-lg border border-surface-700',
          'bg-surface-900 shadow-xl overflow-hidden',
        )}
      >
        <div className="flex items-center justify-between px-4 py-2 border-b border-surface-800">
          <div className="text-sm text-surface-200 truncate pr-4">
            {loading ? 'Loading…' : file?.path ?? ''}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close file viewer"
            className="p-1 rounded-md text-surface-400 hover:text-surface-200 hover:bg-surface-800"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-auto p-4 font-mono text-xs text-surface-200 whitespace-pre-wrap">
          {loading && <span className="text-surface-500">Loading…</span>}
          {!loading && file && file.encoding === 'base64' && (
            <span className="text-surface-500">
              Binary file — {file.size} bytes
            </span>
          )}
          {!loading && file && file.encoding === 'utf-8' && file.content}
        </div>
      </div>
    </div>
  )
}
