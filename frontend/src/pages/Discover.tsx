import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface DiscoveryResult {
  id: number
  title: string
  source_url: string
  source_platform: string
  thumbnail_url: string | null
  file_type: string
  has_bambu_profile: boolean
  downloads: number
  likes: number
  created_at: string | null
}

interface SearchResponse {
  description: string
  queries_used: string[]
  results: DiscoveryResult[]
  total_found: number
}

interface GenerateResponse {
  queue_item: {
    id: number
    title: string
    thumbnail_path: string | null
    status: string
  }
  source_path: string | null
  generation_backend: string | null
}

interface AddToQueueResponse {
  id: number
  title: string
  status: string
}

const PLATFORM_BADGE: Record<string, { bg: string; text: string }> = {
  makerworld: { bg: 'bg-emerald-500/15', text: 'text-emerald-400' },
  printables: { bg: 'bg-orange-500/15', text: 'text-orange-400' },
  thingiverse: { bg: 'bg-blue-500/15', text: 'text-blue-400' },
}

function formatCount(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

export default function Discover() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [mode, setMode] = useState<'search' | 'generate'>('search')
  const [generateDesc, setGenerateDesc] = useState('')
  const [generateBackend, setGenerateBackend] = useState<'auto' | 'openscad' | 'blender'>('auto')
  const [results, setResults] = useState<DiscoveryResult[]>([])
  const [totalFound, setTotalFound] = useState(0)
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set())

  const searchMutation = useMutation({
    mutationFn: (description: string) =>
      apiFetch<SearchResponse>('/api/discover/search', {
        method: 'POST',
        body: JSON.stringify({ description }),
      }),
    onSuccess: (data) => {
      setResults(data.results)
      setTotalFound(data.total_found)
    },
  })

  const addToQueueMutation = useMutation({
    mutationFn: (result: DiscoveryResult) =>
      apiFetch<AddToQueueResponse>('/api/discover/add-to-queue', {
        method: 'POST',
        body: JSON.stringify({
          title: result.title,
          source_url: result.source_url,
          source_platform: result.source_platform,
          thumbnail_url: result.thumbnail_url,
          file_type: result.file_type,
          has_bambu_profile: result.has_bambu_profile,
        }),
      }),
    onSuccess: (_, result) => {
      setAddedIds((prev) => new Set(prev).add(result.id))
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })

  const generateMutation = useMutation({
    mutationFn: (description: string) =>
      apiFetch<GenerateResponse>('/api/generate', {
        method: 'POST',
        body: JSON.stringify({
          description,
          ...(generateBackend !== 'auto' ? { backend: generateBackend } : {}),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setResults([])
    setAddedIds(new Set())
    searchMutation.mutate(searchQuery.trim())
  }

  function handleGenerate(e: React.FormEvent) {
    e.preventDefault()
    if (!generateDesc.trim()) return
    generateMutation.mutate(generateDesc.trim())
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Discover</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Find community models or generate custom designs with AI
        </p>
      </div>

      {/* Mode Tabs */}
      <div className="flex gap-1 mb-5 bg-zinc-900 border border-zinc-700 rounded-lg p-1 w-fit">
        <button
          onClick={() => setMode('search')}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
            mode === 'search' ? 'bg-zinc-700 text-zinc-100' : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Search Models
        </button>
        <button
          onClick={() => setMode('generate')}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
            mode === 'generate' ? 'bg-zinc-700 text-zinc-100' : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Generate with AI
        </button>
      </div>

      {/* Search Mode */}
      {mode === 'search' && (
        <>
          <form onSubmit={handleSearch} className="mb-6">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Describe what you want to print..."
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl pl-10 pr-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>
              <button
                type="submit"
                disabled={searchMutation.isPending || !searchQuery.trim()}
                className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
              >
                {searchMutation.isPending ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Searching...
                  </>
                ) : (
                  'Search'
                )}
              </button>
            </div>
          </form>

          {/* Search Error */}
          {searchMutation.isError && (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300 text-sm mb-6">
              Search failed. Make sure the backend is running and API keys are configured.
            </div>
          )}

          {/* Search Results */}
          {searchMutation.isSuccess && results.length === 0 && (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-12 text-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="w-12 h-12 mx-auto text-zinc-600 mb-4"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <h2 className="text-lg font-semibold text-zinc-300 mb-2">No results found</h2>
              <p className="text-zinc-500 text-sm mb-4">
                Try a different description or generate a custom design instead.
              </p>
              <button
                onClick={() => {
                  setMode('generate')
                  setGenerateDesc(searchQuery)
                }}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Generate Instead
              </button>
            </div>
          )}

          {results.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-zinc-400">
                  {results.length} results shown
                  {totalFound > results.length && ` of ${totalFound} found`}
                </p>
                <button
                  onClick={() => {
                    setMode('generate')
                    setGenerateDesc(searchQuery)
                  }}
                  className="text-xs text-violet-400 hover:text-violet-300 transition-colors"
                >
                  Generate custom design instead
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {results.map((result) => {
                  const platform = PLATFORM_BADGE[result.source_platform.toLowerCase()] ?? {
                    bg: 'bg-zinc-500/15',
                    text: 'text-zinc-400',
                  }
                  const isAdded = addedIds.has(result.id)

                  return (
                    <div
                      key={result.id}
                      className="bg-zinc-900 border border-zinc-700 rounded-xl overflow-hidden shadow-lg shadow-black/20 group"
                    >
                      {/* Thumbnail */}
                      <div className="h-44 bg-zinc-800 flex items-center justify-center overflow-hidden relative">
                        {result.thumbnail_url ? (
                          <img
                            src={result.thumbnail_url}
                            alt={result.title}
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
                        {/* Platform badge */}
                        <span
                          className={`absolute top-2 right-2 px-2 py-0.5 rounded-full text-xs font-medium ${platform.bg} ${platform.text} backdrop-blur-sm`}
                        >
                          {result.source_platform}
                        </span>
                        {result.has_bambu_profile && (
                          <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full text-xs font-medium bg-sky-500/15 text-sky-400 backdrop-blur-sm">
                            Bambu
                          </span>
                        )}
                      </div>

                      {/* Content */}
                      <div className="p-3">
                        <h3 className="text-zinc-100 font-medium text-sm mb-2 line-clamp-2 leading-snug">
                          {result.title}
                        </h3>

                        <div className="flex items-center gap-3 text-xs text-zinc-500 mb-3">
                          {result.downloads > 0 && (
                            <span className="flex items-center gap-1">
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                <polyline points="7 10 12 15 17 10" />
                                <line x1="12" y1="15" x2="12" y2="3" />
                              </svg>
                              {formatCount(result.downloads)}
                            </span>
                          )}
                          {result.likes > 0 && (
                            <span className="flex items-center gap-1">
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
                                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                              </svg>
                              {formatCount(result.likes)}
                            </span>
                          )}
                          <span className="uppercase text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">
                            {result.file_type}
                          </span>
                        </div>

                        <div className="flex gap-2">
                          <button
                            onClick={() => addToQueueMutation.mutate(result)}
                            disabled={isAdded || addToQueueMutation.isPending}
                            className={`flex-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5 ${
                              isAdded
                                ? 'bg-emerald-600/20 text-emerald-400 cursor-default'
                                : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                            }`}
                          >
                            {isAdded ? (
                              <>
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                                  <polyline points="20 6 9 17 4 12" />
                                </svg>
                                Added
                              </>
                            ) : (
                              <>
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                                  <line x1="12" y1="5" x2="12" y2="19" />
                                  <line x1="5" y1="12" x2="19" y2="12" />
                                </svg>
                                Add to Queue
                              </>
                            )}
                          </button>
                          <a
                            href={result.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 rounded-lg transition-colors"
                            title="View on platform"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                              <polyline points="15 3 21 3 21 9" />
                              <line x1="10" y1="14" x2="21" y2="3" />
                            </svg>
                          </a>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </>
      )}

      {/* Generate Mode */}
      {mode === 'generate' && (
        <>
          <form onSubmit={handleGenerate} className="mb-6">
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5">
              <label className="block text-sm text-zinc-300 font-medium mb-2">
                Describe the object you want to create
              </label>
              <textarea
                value={generateDesc}
                onChange={(e) => setGenerateDesc(e.target.value)}
                placeholder="A small phone stand with a 10-degree viewing angle, fits iPhone 15 Pro..."
                rows={4}
                className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-violet-500 transition-colors resize-none"
              />
              <div className="flex items-center gap-3 mt-3">
                <select
                  value={generateBackend}
                  onChange={(e) => setGenerateBackend(e.target.value as 'auto' | 'openscad' | 'blender')}
                  className="bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-violet-500"
                >
                  <option value="auto">Auto (AI picks)</option>
                  <option value="openscad">OpenSCAD</option>
                  <option value="blender">Blender</option>
                </select>
                <p className="text-xs text-zinc-500 flex-1">
                  AI will generate a model and add it to your queue for review
                </p>
                <button
                  type="submit"
                  disabled={generateMutation.isPending || !generateDesc.trim()}
                  className="px-6 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                  {generateMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                      </svg>
                      Generate
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          {/* Generation Progress */}
          {generateMutation.isPending && (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-8 text-center">
              <div className="w-12 h-12 border-2 border-zinc-600 border-t-violet-400 rounded-full animate-spin mx-auto mb-4" />
              <h3 className="text-zinc-200 font-medium mb-1">Generating your model...</h3>
              <p className="text-xs text-zinc-500">
                AI is generating your model, compiling to STL, and creating a preview
              </p>
            </div>
          )}

          {/* Generation Error */}
          {generateMutation.isError && (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300 text-sm">
              Generation failed. The description may be too complex or the OpenSCAD compilation
              encountered an error. Try simplifying your description.
            </div>
          )}

          {/* Generation Result */}
          {generateMutation.isSuccess && generateMutation.data && (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5">
              <div className="flex items-start gap-4">
                <div className="w-32 h-32 bg-zinc-800 rounded-lg flex items-center justify-center overflow-hidden flex-shrink-0">
                  {generateMutation.data.queue_item.thumbnail_path ? (
                    <img
                      src={`/storage/thumbnails/${generateMutation.data.queue_item.thumbnail_path.split('/').pop()}`}
                      alt="Generated model"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1"
                      className="w-12 h-12 text-zinc-700"
                    >
                      <path d="M12 2L2 7l10 5 10-5-10-5z" />
                      <path d="M2 17l10 5 10-5" />
                      <path d="M2 12l10 5 10-5" />
                    </svg>
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4 text-emerald-400">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                      <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                    <h3 className="text-zinc-100 font-semibold text-sm">Model Generated</h3>
                  </div>
                  <p className="text-zinc-400 text-sm mb-3 line-clamp-2">
                    {generateMutation.data.queue_item.title}
                  </p>
                  {generateMutation.data.generation_backend && (
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium mb-2 ${
                        generateMutation.data.generation_backend === 'blender'
                          ? 'bg-orange-500/15 text-orange-400'
                          : 'bg-violet-500/15 text-violet-400'
                      }`}
                    >
                      Made with {generateMutation.data.generation_backend === 'blender' ? 'Blender' : 'OpenSCAD'}
                    </span>
                  )}
                  <p className="text-xs text-zinc-500 mb-3">
                    Added to your queue as pending approval. Review and approve to print.
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setGenerateDesc('')
                        generateMutation.reset()
                      }}
                      className="px-4 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-medium transition-colors"
                    >
                      Generate Another
                    </button>
                    <a
                      href="/queue"
                      className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-medium transition-colors"
                    >
                      View Queue
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
