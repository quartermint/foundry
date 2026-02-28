import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface PrintJob {
  id: number
  queue_item_id: number
  printer_id: number
  outcome: string | null
  started_at: string | null
  completed_at: string | null
  filament_used_g: number | null
  settings_snapshot: string | null
  notes: string | null
  created_at: string | null
}

interface Printer {
  id: string
  name: string
  model: string
}

const OUTCOMES = [
  { key: '', label: 'All Outcomes' },
  { key: 'success', label: 'Success' },
  { key: 'failed', label: 'Failed' },
  { key: 'cancelled', label: 'Cancelled' },
] as const

const OUTCOME_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  success: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', label: 'Success' },
  failed: { bg: 'bg-red-500/15', text: 'text-red-400', label: 'Failed' },
  cancelled: { bg: 'bg-zinc-500/15', text: 'text-zinc-400', label: 'Cancelled' },
}

const PAGE_SIZE = 20

function formatDate(iso: string | null): string {
  if (!iso) return '--'
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) return '--'
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (ms < 0) return '--'
  const mins = Math.floor(ms / 60000)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function History() {
  const [printerFilter, setPrinterFilter] = useState('')
  const [outcomeFilter, setOutcomeFilter] = useState('')
  const [page, setPage] = useState(0)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data: printers } = useQuery({
    queryKey: ['printers'],
    queryFn: () => apiFetch<Printer[]>('/api/printers'),
    retry: 1,
  })

  const queryParams = new URLSearchParams()
  if (printerFilter) queryParams.set('printer_id', printerFilter)
  if (outcomeFilter) queryParams.set('outcome', outcomeFilter)
  queryParams.set('limit', String(PAGE_SIZE))
  queryParams.set('offset', String(page * PAGE_SIZE))

  const { data: jobs, isLoading, error } = useQuery({
    queryKey: ['history', printerFilter, outcomeFilter, page],
    queryFn: () => apiFetch<PrintJob[]>(`/api/history?${queryParams.toString()}`),
    retry: 1,
  })

  function getPrinterName(printerId: number): string {
    const p = printers?.find((pr) => String(pr.id) === String(printerId))
    return p?.name ?? `Printer #${printerId}`
  }

  function tryParseSettings(json: string | null): Record<string, unknown> | null {
    if (!json) return null
    try {
      return JSON.parse(json)
    } catch {
      return null
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Print History</h1>
        <p className="text-sm text-zinc-400 mt-1">Track past prints with outcomes and statistics</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-5">
        <select
          value={outcomeFilter}
          onChange={(e) => {
            setOutcomeFilter(e.target.value)
            setPage(0)
          }}
          className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-emerald-500"
        >
          {OUTCOMES.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>

        <select
          value={printerFilter}
          onChange={(e) => {
            setPrinterFilter(e.target.value)
            setPage(0)
          }}
          className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-emerald-500"
        >
          <option value="">All Printers</option>
          {printers?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        {(outcomeFilter || printerFilter) && (
          <button
            onClick={() => {
              setOutcomeFilter('')
              setPrinterFilter('')
              setPage(0)
            }}
            className="text-xs text-zinc-400 hover:text-zinc-300 transition-colors"
          >
            Clear filters
          </button>
        )}
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
          Failed to load print history. Make sure the backend is running.
        </div>
      )}

      {/* Empty State */}
      {jobs && jobs.length === 0 && page === 0 && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-12 text-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-12 h-12 mx-auto text-zinc-600 mb-4"
          >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <h2 className="text-lg font-semibold text-zinc-300 mb-2">No print history yet</h2>
          <p className="text-zinc-500 text-sm">
            {outcomeFilter || printerFilter
              ? 'No jobs match the current filters. Try clearing them.'
              : 'Print history will appear here as you send jobs to your printers.'}
          </p>
        </div>
      )}

      {/* Table */}
      {jobs && jobs.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-700">
                  <th className="text-left text-xs text-zinc-400 font-medium px-4 py-3">Date</th>
                  <th className="text-left text-xs text-zinc-400 font-medium px-4 py-3">Printer</th>
                  <th className="text-left text-xs text-zinc-400 font-medium px-4 py-3">Duration</th>
                  <th className="text-left text-xs text-zinc-400 font-medium px-4 py-3">Filament</th>
                  <th className="text-left text-xs text-zinc-400 font-medium px-4 py-3">Outcome</th>
                  <th className="text-left text-xs text-zinc-400 font-medium px-4 py-3 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => {
                  const isExpanded = expandedId === job.id
                  const outcome = job.outcome
                    ? OUTCOME_BADGE[job.outcome] ?? { bg: 'bg-zinc-500/15', text: 'text-zinc-400', label: job.outcome }
                    : { bg: 'bg-amber-500/15', text: 'text-amber-400', label: 'In Progress' }
                  const settings = tryParseSettings(job.settings_snapshot)

                  return (
                    <tr key={job.id} className="group">
                      <td colSpan={6} className="p-0">
                        {/* Main Row */}
                        <div
                          className="flex items-center cursor-pointer hover:bg-zinc-800/50 transition-colors"
                          onClick={() => setExpandedId(isExpanded ? null : job.id)}
                        >
                          <div className="flex-none w-[160px] px-4 py-3">
                            <span className="text-zinc-200">{formatDate(job.started_at ?? job.created_at)}</span>
                            <span className="text-zinc-500 text-xs ml-1.5">
                              {formatTime(job.started_at ?? job.created_at)}
                            </span>
                          </div>
                          <div className="flex-none w-[140px] px-4 py-3 text-zinc-300">
                            {getPrinterName(job.printer_id)}
                          </div>
                          <div className="flex-none w-[100px] px-4 py-3 text-zinc-400">
                            {formatDuration(job.started_at, job.completed_at)}
                          </div>
                          <div className="flex-none w-[100px] px-4 py-3 text-zinc-400">
                            {job.filament_used_g != null ? `${Math.round(job.filament_used_g)}g` : '--'}
                          </div>
                          <div className="flex-1 px-4 py-3">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${outcome.bg} ${outcome.text}`}>
                              {outcome.label}
                            </span>
                          </div>
                          <div className="flex-none w-8 px-4 py-3">
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              className={`w-4 h-4 text-zinc-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                            >
                              <polyline points="6 9 12 15 18 9" />
                            </svg>
                          </div>
                        </div>

                        {/* Expanded Details */}
                        {isExpanded && (
                          <div className="px-4 pb-4 bg-zinc-800/30 border-t border-zinc-800">
                            <div className="grid grid-cols-2 gap-4 pt-3">
                              {/* Settings Snapshot */}
                              <div>
                                <h4 className="text-xs text-zinc-400 font-medium mb-2 uppercase tracking-wide">
                                  Settings Snapshot
                                </h4>
                                {settings ? (
                                  <div className="bg-zinc-800 rounded-lg p-3 space-y-1">
                                    {Object.entries(settings).map(([key, value]) => (
                                      <div key={key} className="flex justify-between text-xs">
                                        <span className="text-zinc-400">{key}</span>
                                        <span className="text-zinc-200">{String(value)}</span>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-xs text-zinc-500 italic">No settings recorded</p>
                                )}
                              </div>

                              {/* Notes & Info */}
                              <div>
                                <h4 className="text-xs text-zinc-400 font-medium mb-2 uppercase tracking-wide">
                                  Notes
                                </h4>
                                {job.notes ? (
                                  <p className="text-sm text-zinc-300 bg-zinc-800 rounded-lg p-3">
                                    {job.notes}
                                  </p>
                                ) : (
                                  <p className="text-xs text-zinc-500 italic">No notes</p>
                                )}

                                <div className="mt-3 space-y-1">
                                  <div className="flex justify-between text-xs">
                                    <span className="text-zinc-400">Job ID</span>
                                    <span className="text-zinc-300 font-mono">#{job.id}</span>
                                  </div>
                                  <div className="flex justify-between text-xs">
                                    <span className="text-zinc-400">Queue Item</span>
                                    <span className="text-zinc-300 font-mono">#{job.queue_item_id}</span>
                                  </div>
                                  {job.started_at && (
                                    <div className="flex justify-between text-xs">
                                      <span className="text-zinc-400">Started</span>
                                      <span className="text-zinc-300">
                                        {new Date(job.started_at).toLocaleString()}
                                      </span>
                                    </div>
                                  )}
                                  {job.completed_at && (
                                    <div className="flex justify-between text-xs">
                                      <span className="text-zinc-400">Completed</span>
                                      <span className="text-zinc-300">
                                        {new Date(job.completed_at).toLocaleString()}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-700">
            <p className="text-xs text-zinc-500">
              Showing {page * PAGE_SIZE + 1}-{page * PAGE_SIZE + jobs.length}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-800 disabled:text-zinc-600 text-zinc-300 rounded text-xs font-medium transition-colors"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={jobs.length < PAGE_SIZE}
                className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-800 disabled:text-zinc-600 text-zinc-300 rounded text-xs font-medium transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
