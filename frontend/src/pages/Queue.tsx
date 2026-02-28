import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, apiUpload } from '../api/client'

interface QueueItem {
  id: number
  title: string
  description: string | null
  source_type: string | null
  source_url: string | null
  source_platform: string | null
  model_path: string | null
  sliced_path: string | null
  thumbnail_path: string | null
  status: string
  printer_id: number | null
  material: string
  filament_g: number | null
  print_time_min: number | null
  plate_id: number | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

interface Printer {
  id: string
  name: string
  model: string
}

const STATUS_TABS = [
  { key: '', label: 'All' },
  { key: 'pending_approval', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'printing', label: 'Printing' },
  { key: 'completed', label: 'Completed' },
] as const

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  pending_approval: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', label: 'Pending Approval' },
  approved: { bg: 'bg-blue-500/15', text: 'text-blue-400', label: 'Approved' },
  slicing: { bg: 'bg-violet-500/15', text: 'text-violet-400', label: 'Slicing' },
  ready: { bg: 'bg-blue-500/15', text: 'text-blue-400', label: 'Ready' },
  printing: { bg: 'bg-sky-500/15', text: 'text-sky-400', label: 'Printing' },
  completed: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', label: 'Completed' },
  failed: { bg: 'bg-red-500/15', text: 'text-red-400', label: 'Failed' },
  rejected: { bg: 'bg-zinc-500/15', text: 'text-zinc-400', label: 'Rejected' },
}

function formatDuration(minutes: number | null): string {
  if (minutes == null) return '--'
  if (minutes < 1) return '<1m'
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return '--'
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

export default function Queue() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data: items, isLoading, error } = useQuery({
    queryKey: ['queue', activeTab],
    queryFn: () =>
      apiFetch<QueueItem[]>(`/api/queue${activeTab ? `?status_filter=${activeTab}` : ''}`),
    retry: 1,
  })

  const { data: printers } = useQuery({
    queryKey: ['printers'],
    queryFn: () => apiFetch<Printer[]>('/api/printers'),
    retry: 1,
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => apiUpload('/api/queue/upload', file) as Promise<QueueItem>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      setUploadError(null)
    },
    onError: (err: Error) => {
      setUploadError(err.message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      apiFetch<QueueItem>(`/api/queue/${id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })

  const sendMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ status: string; job_id: number; queue_item: QueueItem }>(`/api/queue/${id}/send`, {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/queue/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const ext = file.name.split('.').pop()?.toLowerCase()
        if (ext === 'stl' || ext === '3mf') {
          uploadMutation.mutate(file)
        } else {
          setUploadError(`Invalid file type: .${ext}. Only .stl and .3mf files accepted.`)
        }
      }
    },
    [uploadMutation],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      handleFiles(e.dataTransfer.files)
    },
    [handleFiles],
  )

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Print Queue</h1>
        <p className="text-sm text-zinc-400 mt-1">Upload models and manage print jobs</p>
      </div>

      {/* Upload Drop Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-8 mb-6 text-center transition-colors cursor-pointer ${
          dragging
            ? 'border-emerald-500 bg-emerald-500/5'
            : 'border-zinc-700 bg-zinc-900/50 hover:border-zinc-500'
        }`}
        onClick={() => {
          const input = document.createElement('input')
          input.type = 'file'
          input.accept = '.stl,.3mf'
          input.multiple = true
          input.onchange = () => handleFiles(input.files)
          input.click()
        }}
      >
        {uploadMutation.isPending ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-zinc-600 border-t-emerald-400 rounded-full animate-spin" />
            <p className="text-sm text-zinc-400">Uploading...</p>
          </div>
        ) : (
          <>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`w-10 h-10 mx-auto mb-3 ${dragging ? 'text-emerald-400' : 'text-zinc-500'}`}
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <p className="text-sm text-zinc-300 font-medium">
              {dragging ? 'Drop files here' : 'Drag & drop STL/3MF files here'}
            </p>
            <p className="text-xs text-zinc-500 mt-1">or click to browse</p>
          </>
        )}
      </div>

      {uploadError && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 mb-4 text-red-300 text-sm flex items-center justify-between">
          <span>{uploadError}</span>
          <button onClick={() => setUploadError(null)} className="text-red-400 hover:text-red-300 ml-3">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-1 mb-5 bg-zinc-900 border border-zinc-700 rounded-lg p-1 w-fit">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-zinc-700 text-zinc-100'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center h-48">
          <div className="w-8 h-8 border-2 border-zinc-600 border-t-emerald-400 rounded-full animate-spin" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300 text-sm">
          Failed to load queue. Make sure the backend is running.
        </div>
      )}

      {/* Empty State */}
      {items && items.length === 0 && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-12 text-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-12 h-12 mx-auto text-zinc-600 mb-4"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="12" y1="8" x2="12" y2="16" />
            <line x1="8" y1="12" x2="16" y2="12" />
          </svg>
          <h2 className="text-lg font-semibold text-zinc-300 mb-2">
            {activeTab ? 'No items with this status' : 'Queue is empty'}
          </h2>
          <p className="text-zinc-500 text-sm">
            Upload an STL or 3MF file to get started, or discover models from the community.
          </p>
        </div>
      )}

      {/* Queue Items Grid */}
      {items && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((item) => {
            const badge = STATUS_BADGE[item.status] ?? STATUS_BADGE.pending_approval
            return (
              <div
                key={item.id}
                className="bg-zinc-900 border border-zinc-700 rounded-xl overflow-hidden shadow-lg shadow-black/20 group"
              >
                {/* Thumbnail */}
                <div className="h-40 bg-zinc-800 flex items-center justify-center overflow-hidden">
                  {item.thumbnail_path ? (
                    <img
                      src={`/storage/thumbnails/${item.thumbnail_path.split('/').pop()}`}
                      alt={item.title}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        ;(e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                  ) : (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1"
                      className="w-16 h-16 text-zinc-700"
                    >
                      <path d="M12 2L2 7l10 5 10-5-10-5z" />
                      <path d="M2 17l10 5 10-5" />
                      <path d="M2 12l10 5 10-5" />
                    </svg>
                  )}
                </div>

                {/* Content */}
                <div className="p-4">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="text-zinc-100 font-semibold text-sm truncate flex-1">
                      {item.title}
                    </h3>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${badge.bg} ${badge.text}`}
                    >
                      {badge.label}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-zinc-500 mb-3">
                    <span className="flex items-center gap-1">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 6v6l4 2" />
                      </svg>
                      {formatDuration(item.print_time_min)}
                    </span>
                    <span className="bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-400">
                      {item.material}
                    </span>
                    {item.filament_g && (
                      <span>{Math.round(item.filament_g)}g</span>
                    )}
                    <span className="ml-auto">{formatRelativeTime(item.created_at)}</span>
                  </div>

                  {item.error_message && (
                    <p className="text-xs text-red-400 bg-red-900/20 rounded px-2 py-1 mb-3 truncate">
                      {item.error_message}
                    </p>
                  )}

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2">
                    {item.status === 'pending_approval' && (
                      <>
                        <button
                          onClick={() =>
                            updateMutation.mutate({ id: item.id, body: { status: 'approved' } })
                          }
                          disabled={updateMutation.isPending}
                          className="flex-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded-lg text-xs font-medium transition-colors"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() =>
                            updateMutation.mutate({ id: item.id, body: { status: 'rejected' } })
                          }
                          disabled={updateMutation.isPending}
                          className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-medium transition-colors"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {(item.status === 'approved' || item.status === 'ready') && (
                      <button
                        onClick={() => sendMutation.mutate(item.id)}
                        disabled={sendMutation.isPending}
                        className="flex-1 px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:bg-zinc-700 text-white rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5"
                      >
                        {sendMutation.isPending ? (
                          <div className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                            <line x1="22" y1="2" x2="11" y2="13" />
                            <polygon points="22 2 15 22 11 13 2 9 22 2" />
                          </svg>
                        )}
                        Send to Printer
                      </button>
                    )}
                    {item.status === 'printing' && (
                      <div className="flex-1 flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
                        <span className="text-xs text-sky-400 font-medium">Printing...</span>
                      </div>
                    )}

                    {/* Printer selector for approved items */}
                    {(item.status === 'approved' || item.status === 'ready') && printers && printers.length > 0 && (
                      <select
                        value={item.printer_id ?? ''}
                        onChange={(e) =>
                          updateMutation.mutate({
                            id: item.id,
                            body: { printer_id: e.target.value ? parseInt(e.target.value) : null },
                          })
                        }
                        className="bg-zinc-800 border border-zinc-600 rounded-lg px-2 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-zinc-500"
                      >
                        <option value="">Auto</option>
                        {printers.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    )}

                    {/* Delete */}
                    <button
                      onClick={() => {
                        if (confirm('Delete this item from the queue?')) {
                          deleteMutation.mutate(item.id)
                        }
                      }}
                      className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                      title="Delete"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
