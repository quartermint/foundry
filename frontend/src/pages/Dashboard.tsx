import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import PrinterStatusCard from '../components/PrinterStatus'

interface Printer {
  id: string
  name: string
  model: string
  ip: string
  serial: string
}

export default function Dashboard() {
  const { data: printers, isLoading, error } = useQuery({
    queryKey: ['printers'],
    queryFn: () => apiFetch<Printer[]>('/api/printers'),
    retry: 1,
  })

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Dashboard</h1>
        <p className="text-sm text-zinc-400 mt-1">Monitor your printers in real time</p>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-2 border-zinc-600 border-t-emerald-400 rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300 text-sm">
          Failed to load printers. Make sure the backend is running and your token is set in{' '}
          <Link to="/settings" className="text-red-400 underline">Settings</Link>.
        </div>
      )}

      {printers && printers.length === 0 && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-12 text-center">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-12 h-12 mx-auto text-zinc-600 mb-4">
            <rect x="6" y="6" width="12" height="12" rx="1" />
            <path d="M6 18v2a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-2" />
            <path d="M6 6V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v2" />
          </svg>
          <h2 className="text-lg font-semibold text-zinc-300 mb-2">No printers configured</h2>
          <p className="text-zinc-500 text-sm mb-4">Add your first Bambu Lab printer to get started.</p>
          <Link
            to="/settings"
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            Add Printer
          </Link>
        </div>
      )}

      {printers && printers.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {printers.map((printer) => (
            <PrinterStatusCard key={printer.id} printer={printer} />
          ))}
        </div>
      )}
    </div>
  )
}
