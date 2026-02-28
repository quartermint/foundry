import { usePrinterStatus } from '../hooks/usePrinterStatus'

interface Printer {
  id: string
  name: string
  model: string
}

const stateConfig: Record<string, { color: string; bg: string; label: string }> = {
  idle: { color: 'text-emerald-400', bg: 'bg-emerald-400', label: 'Idle' },
  printing: { color: 'text-sky-400', bg: 'bg-sky-400', label: 'Printing' },
  paused: { color: 'text-amber-400', bg: 'bg-amber-400', label: 'Paused' },
  error: { color: 'text-red-400', bg: 'bg-red-400', label: 'Error' },
  offline: { color: 'text-zinc-500', bg: 'bg-zinc-500', label: 'Offline' },
}

function TempGauge({ label, current, target }: { label: string; current: number; target: number }) {
  const pct = target > 0 ? Math.min((current / target) * 100, 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs text-zinc-400 mb-1">
        <span>{label}</span>
        <span>
          {Math.round(current)}° / {Math.round(target)}°
        </span>
      </div>
      <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-orange-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function formatEta(minutes: number | null): string {
  if (minutes == null) return '--'
  if (minutes < 1) return '<1m'
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function PrinterStatusCard({ printer }: { printer: Printer }) {
  const { status, connected } = usePrinterStatus(printer.id)

  const state = status?.state ?? 'offline'
  const config = stateConfig[state] ?? stateConfig.offline

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 shadow-lg shadow-black/20">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-zinc-100 font-semibold">{printer.name}</h3>
          <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded-full">
            {printer.model}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${config.bg} ${state === 'printing' ? 'animate-pulse' : ''}`} />
          <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
        </div>
      </div>

      {!connected && !status && (
        <p className="text-xs text-zinc-500 italic">Connecting...</p>
      )}

      {status && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <TempGauge label="Nozzle" current={status.nozzle_temp} target={status.nozzle_target} />
            <TempGauge label="Bed" current={status.bed_temp} target={status.bed_target} />
          </div>

          {state === 'printing' && (
            <div className="space-y-2 pt-1">
              <div className="flex justify-between text-xs text-zinc-400">
                <span className="truncate max-w-[60%]">{status.current_file ?? 'Unknown file'}</span>
                <span>ETA {formatEta(status.remaining_time_min)}</span>
              </div>
              <div className="h-2 bg-zinc-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-sky-500 rounded-full transition-all duration-1000 relative overflow-hidden"
                  style={{ width: `${status.progress}%` }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-sky-400/30 to-transparent animate-pulse" />
                </div>
              </div>
              <p className="text-right text-xs text-sky-400 font-medium">{Math.round(status.progress)}%</p>
            </div>
          )}

          {status.fan_speed != null && status.fan_speed > 0 && (
            <div className="flex items-center gap-1 text-xs text-zinc-500">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
                <path d="M12 12c-1.5-3-4-5.5-7-5.5S0 9 0 12s2 5.5 5 5.5 5.5-2.5 7-5.5c1.5 3 4 5.5 7 5.5s5-2.5 5-5.5-2-5.5-5-5.5-5.5 2.5-7 5.5z" />
              </svg>
              <span>Fan {Math.round(status.fan_speed)}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
