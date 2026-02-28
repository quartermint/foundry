import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface Printer {
  id: string
  name: string
  model: string
  ip: string
  serial: string
  access_code: string
  nozzle_size: number
  bed_width: number
  bed_depth: number
  materials: string[]
}

const MODELS = ['P1S', 'X1C', 'X1E', 'A1', 'A1 Mini'] as const
const MATERIALS = ['PLA', 'PETG', 'ABS', 'ASA', 'TPU', 'PA', 'PC', 'PVA'] as const

const defaultForm = {
  name: '',
  model: 'P1S' as string,
  ip: '',
  serial: '',
  access_code: '',
  nozzle_size: 0.4,
  bed_width: 256,
  bed_depth: 256,
  materials: ['PLA'] as string[],
}

export default function Settings() {
  const queryClient = useQueryClient()
  const [token, setToken] = useState('')
  const [tokenSaved, setTokenSaved] = useState(false)
  const [form, setForm] = useState({ ...defaultForm })
  const [editingId, setEditingId] = useState<string | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem('foundry_token')
    if (saved) setToken(saved)
  }, [])

  const { data: printers } = useQuery({
    queryKey: ['printers'],
    queryFn: () => apiFetch<Printer[]>('/api/printers'),
    retry: 1,
  })

  const addPrinter = useMutation({
    mutationFn: (data: typeof defaultForm) =>
      apiFetch<Printer>('/api/printers', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['printers'] })
      setForm({ ...defaultForm })
      setEditingId(null)
    },
  })

  const updatePrinter = useMutation({
    mutationFn: ({ id, data }: { id: string; data: typeof defaultForm }) =>
      apiFetch<Printer>(`/api/printers/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['printers'] })
      setForm({ ...defaultForm })
      setEditingId(null)
    },
  })

  const deletePrinter = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/printers/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['printers'] })
    },
  })

  function saveToken() {
    localStorage.setItem('foundry_token', token)
    setTokenSaved(true)
    setTimeout(() => setTokenSaved(false), 2000)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editingId) {
      updatePrinter.mutate({ id: editingId, data: form })
    } else {
      addPrinter.mutate(form)
    }
  }

  function startEdit(printer: Printer) {
    setEditingId(printer.id)
    setForm({
      name: printer.name,
      model: printer.model,
      ip: printer.ip,
      serial: printer.serial,
      access_code: printer.access_code,
      nozzle_size: printer.nozzle_size,
      bed_width: printer.bed_width,
      bed_depth: printer.bed_depth,
      materials: printer.materials,
    })
  }

  function cancelEdit() {
    setEditingId(null)
    setForm({ ...defaultForm })
  }

  function toggleMaterial(mat: string) {
    setForm((prev) => ({
      ...prev,
      materials: prev.materials.includes(mat)
        ? prev.materials.filter((m) => m !== mat)
        : [...prev.materials, mat],
    }))
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Settings</h1>
        <p className="text-sm text-zinc-400 mt-1">Manage your printers and API access</p>
      </div>

      {/* API Token */}
      <section className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 mb-6">
        <h2 className="text-lg font-semibold text-zinc-100 mb-3">API Token</h2>
        <p className="text-sm text-zinc-400 mb-3">
          Set your authentication token for backend API access.
        </p>
        <div className="flex gap-2">
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter API token"
            className="flex-1 bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={saveToken}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {tokenSaved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </section>

      {/* Registered Printers */}
      <section className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 mb-6">
        <h2 className="text-lg font-semibold text-zinc-100 mb-3">Registered Printers</h2>
        {printers && printers.length > 0 ? (
          <div className="space-y-2">
            {printers.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between bg-zinc-800 rounded-lg px-4 py-3"
              >
                <div>
                  <span className="text-zinc-100 font-medium">{p.name}</span>
                  <span className="ml-2 text-xs text-zinc-500 bg-zinc-700 px-2 py-0.5 rounded-full">
                    {p.model}
                  </span>
                  <p className="text-xs text-zinc-500 mt-0.5">{p.ip} &middot; {p.serial}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => startEdit(p)}
                    className="text-xs text-sky-400 hover:text-sky-300 transition-colors"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => deletePrinter.mutate(p.id)}
                    className="text-xs text-red-400 hover:text-red-300 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-zinc-500">No printers registered yet.</p>
        )}
      </section>

      {/* Add / Edit Printer Form */}
      <section className="bg-zinc-900 border border-zinc-700 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-zinc-100">
            {editingId ? 'Edit Printer' : 'Add Printer'}
          </h2>
          {editingId && (
            <button onClick={cancelEdit} className="text-xs text-zinc-400 hover:text-zinc-300">
              Cancel
            </button>
          )}
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Name</label>
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My P1S"
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Model</label>
              <select
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-emerald-500"
              >
                {MODELS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">IP Address</label>
              <input
                required
                value={form.ip}
                onChange={(e) => setForm({ ...form, ip: e.target.value })}
                placeholder="192.168.1.100"
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Serial Number</label>
              <input
                required
                value={form.serial}
                onChange={(e) => setForm({ ...form, serial: e.target.value })}
                placeholder="01S00A000000000"
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Access Code</label>
              <input
                required
                type="password"
                value={form.access_code}
                onChange={(e) => setForm({ ...form, access_code: e.target.value })}
                placeholder="12345678"
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Nozzle Size (mm)</label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="1.0"
                value={form.nozzle_size}
                onChange={(e) => setForm({ ...form, nozzle_size: parseFloat(e.target.value) })}
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Bed (W x D mm)</label>
              <div className="flex gap-1">
                <input
                  type="number"
                  value={form.bed_width}
                  onChange={(e) => setForm({ ...form, bed_width: parseInt(e.target.value) })}
                  className="w-1/2 bg-zinc-800 border border-zinc-600 rounded-lg px-2 py-2 text-sm text-zinc-100 focus:outline-none focus:border-emerald-500"
                />
                <input
                  type="number"
                  value={form.bed_depth}
                  onChange={(e) => setForm({ ...form, bed_depth: parseInt(e.target.value) })}
                  className="w-1/2 bg-zinc-800 border border-zinc-600 rounded-lg px-2 py-2 text-sm text-zinc-100 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs text-zinc-400 mb-2">Materials</label>
            <div className="flex flex-wrap gap-2">
              {MATERIALS.map((mat) => (
                <label
                  key={mat}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium cursor-pointer transition-colors ${
                    form.materials.includes(mat)
                      ? 'bg-emerald-600/20 border-emerald-600 text-emerald-400'
                      : 'bg-zinc-800 border-zinc-600 text-zinc-400 hover:border-zinc-500'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={form.materials.includes(mat)}
                    onChange={() => toggleMaterial(mat)}
                    className="sr-only"
                  />
                  {mat}
                </label>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={addPrinter.isPending || updatePrinter.isPending}
            className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {addPrinter.isPending || updatePrinter.isPending
              ? 'Saving...'
              : editingId
                ? 'Update Printer'
                : 'Add Printer'}
          </button>
        </form>
      </section>
    </div>
  )
}
