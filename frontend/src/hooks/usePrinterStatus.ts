import { useState, useEffect, useRef, useCallback } from 'react'

export interface PrinterStatus {
  state: 'idle' | 'printing' | 'paused' | 'error' | 'offline'
  nozzle_temp: number
  nozzle_target: number
  bed_temp: number
  bed_target: number
  progress: number
  current_file: string | null
  remaining_time_min: number | null
  fan_speed: number | null
}

interface UsePrinterStatusResult {
  status: PrinterStatus | null
  connected: boolean
  error: string | null
}

const DEFAULT_STATUS: PrinterStatus = {
  state: 'offline',
  nozzle_temp: 0,
  nozzle_target: 0,
  bed_temp: 0,
  bed_target: 0,
  progress: 0,
  current_file: null,
  remaining_time_min: null,
  fan_speed: null,
}

export function usePrinterStatus(printerId: string): UsePrinterStatusResult {
  const [status, setStatus] = useState<PrinterStatus | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const reconnectDelay = useRef(1000)

  const connect = useCallback(() => {
    const token = localStorage.getItem('foundry_token')
    if (!token) {
      setError('No auth token')
      setStatus({ ...DEFAULT_STATUS })
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/printer/${printerId}/status?token=${token}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
      reconnectDelay.current = 1000
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as PrinterStatus
        setStatus(data)
      } catch {
        setError('Invalid message format')
      }
    }

    ws.onerror = () => {
      setError('WebSocket error')
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null

      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
        connect()
      }, reconnectDelay.current)
    }
  }, [printerId])

  useEffect(() => {
    connect()

    return () => {
      clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  return { status, connected, error }
}
