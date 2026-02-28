import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface Source {
  title: string
  url: string
}

interface AskResponse {
  answer: string
  sources: Source[]
  tips_used?: number
}

interface ChatMessage {
  id: string
  type: 'question' | 'answer'
  text: string
  sources?: Source[]
  tipsUsed?: number
  timestamp: Date
}

const SUGGESTED_QUESTIONS = [
  'How do I fix stringing on my P1S?',
  'Best bed adhesion tips for PETG',
  'What causes layer shifting?',
  'How to print TPU successfully',
  'ABS warping solutions for enclosed printers',
  'Optimal retraction settings for Bambu Lab',
]

export default function Knowledge() {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const askMutation = useMutation({
    mutationFn: (q: string) =>
      apiFetch<AskResponse>('/api/knowledge/ask', {
        method: 'POST',
        body: JSON.stringify({ question: q }),
      }),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          type: 'answer',
          text: data.answer,
          sources: data.sources,
          tipsUsed: data.tips_used,
          timestamp: new Date(),
        },
      ])
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          type: 'answer',
          text: 'Sorry, I encountered an error while searching the knowledge base. Make sure the backend is running and the API key is configured.',
          sources: [],
          timestamp: new Date(),
        },
      ])
    },
    onSettled: () => {
      inputRef.current?.focus()
    },
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || askMutation.isPending) return
    submitQuestion(question.trim())
  }

  function submitQuestion(q: string) {
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        type: 'question',
        text: q,
        timestamp: new Date(),
      },
    ])
    setQuestion('')
    askMutation.mutate(q)
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-5">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-zinc-100">Knowledge Base</h1>
          <p className="text-sm text-zinc-400 mt-1">
            AI-powered 3D printing assistant backed by community knowledge
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 pb-4 min-h-0">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="w-16 h-16 text-zinc-700 mb-4"
              >
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
              <h2 className="text-lg font-semibold text-zinc-300 mb-2">
                Ask about 3D printing
              </h2>
              <p className="text-zinc-500 text-sm max-w-md mb-6">
                Get answers synthesized from community tips, Reddit discussions, YouTube guides, and
                best practices. The knowledge base grows automatically over time.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg w-full">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => submitQuestion(q)}
                    className="text-left px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-xs text-zinc-300 hover:border-zinc-500 hover:bg-zinc-800 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.type === 'question' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.type === 'question' ? (
                <div className="max-w-[70%] bg-emerald-600/20 border border-emerald-600/30 rounded-2xl rounded-br-sm px-4 py-3">
                  <p className="text-sm text-zinc-100">{msg.text}</p>
                </div>
              ) : (
                <div className="max-w-[85%] bg-zinc-900 border border-zinc-700 rounded-2xl rounded-bl-sm px-4 py-3 shadow-lg shadow-black/20">
                  <div className="text-sm text-zinc-200 leading-relaxed whitespace-pre-wrap">
                    {msg.text}
                  </div>

                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-zinc-800">
                      <p className="text-xs text-zinc-500 font-medium mb-1.5">Sources</p>
                      <div className="flex flex-wrap gap-2">
                        {msg.sources.map((src, i) => (
                          <a
                            key={i}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-xs text-sky-400 hover:text-sky-300 transition-colors max-w-[200px]"
                            title={src.title}
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3 flex-shrink-0">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                              <polyline points="15 3 21 3 21 9" />
                              <line x1="10" y1="14" x2="21" y2="3" />
                            </svg>
                            <span className="truncate">{src.title}</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {msg.tipsUsed != null && (
                    <p className="text-xs text-zinc-600 mt-2">
                      Synthesized from {msg.tipsUsed} knowledge base entries
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Typing indicator */}
          {askMutation.isPending && (
            <div className="flex justify-start">
              <div className="bg-zinc-900 border border-zinc-700 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-zinc-400">
                  <div className="flex gap-1">
                    <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  Searching knowledge base...
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex gap-3 pt-3 border-t border-zinc-800">
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about 3D printing..."
            disabled={askMutation.isPending}
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={askMutation.isPending || !question.trim()}
            className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
          >
            {askMutation.isPending ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
            Ask
          </button>
        </form>
      </div>

      {/* Sidebar: Recent Questions */}
      {messages.length > 0 && (
        <aside className="hidden lg:block w-64 flex-shrink-0">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 sticky top-6">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Recent Questions</h3>
            <div className="space-y-1.5">
              {messages
                .filter((m) => m.type === 'question')
                .slice(-10)
                .reverse()
                .map((msg) => (
                  <button
                    key={msg.id}
                    onClick={() => {
                      setQuestion(msg.text)
                      inputRef.current?.focus()
                    }}
                    className="w-full text-left px-2.5 py-2 rounded-lg text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors truncate"
                    title={msg.text}
                  >
                    {msg.text}
                  </button>
                ))}
            </div>

            {/* Suggested Follow-ups */}
            <div className="mt-4 pt-4 border-t border-zinc-800">
              <h3 className="text-xs font-medium text-zinc-500 mb-2 uppercase tracking-wide">
                Try asking
              </h3>
              <div className="space-y-1">
                {SUGGESTED_QUESTIONS.slice(0, 3).map((q) => (
                  <button
                    key={q}
                    onClick={() => submitQuestion(q)}
                    disabled={askMutation.isPending}
                    className="w-full text-left px-2.5 py-1.5 rounded text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors truncate disabled:opacity-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}
