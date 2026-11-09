import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send, Loader2, AlertCircle, Sparkles, ArrowRight } from 'lucide-react'
import type {
  ChatResponse,
  ActionDraft,
  EvidenceStatus,
  Citation,
  HistoryMessage,
} from '../types'
import { sendChat, ApiClientError } from '../services/api'
import { EvidenceBadge } from './EvidenceBadge'
import { CitationCard } from './CitationCard'

export interface ChatInterfaceProps {
  onResponse?: (response: ChatResponse) => void
  onActionProposal?: (proposal: ActionDraft) => void
  organizationContext?: string | null
  organizationContextIsExplicit?: boolean
  className?: string
  sessionEpoch?: number
}

interface MessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  evidenceStatus?: EvidenceStatus
  citations?: Citation[]
  actionProposal?: ActionDraft | null
}

interface ChatError {
  message: string
  principleViolated?: string | null
}

const EXAMPLE_QUESTIONS = [
  '¿Qué le falta a ORG-07 para pasar a producción?',
  '¿Cuál es el umbral de aprobación de PLA-ADM?',
  '¿Qué tareas tiene pendientes ORG-05?',
  '¿Cuáles son las tarifas de almacenamiento en la nube de MIRA?',
]

export function ChatInterface({
  onResponse,
  onActionProposal,
  organizationContext,
  organizationContextIsExplicit = false,
  className = '',
  sessionEpoch = 0,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ChatError | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const messageCounterRef = useRef(0)
  const sessionEpochRef = useRef(sessionEpoch)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (sessionEpochRef.current !== sessionEpoch) {
      abortControllerRef.current?.abort()
      abortControllerRef.current = null
      sessionEpochRef.current = sessionEpoch
      setLoading(false)
    }
  }, [sessionEpoch])

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      abortControllerRef.current = null
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, loading, error])

  const handleSendText = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    setError(null)
    messageCounterRef.current += 1
    const userMessage: MessageItem = {
      id: `user-${messageCounterRef.current}`,
      role: 'user',
      content: trimmed,
    }

    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setInputValue('')
    setLoading(true)

    // Historial previo para contexto conversacional
    const history: HistoryMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller
    const requestEpoch = sessionEpochRef.current

    try {
      const response = await sendChat(
        {
          message: trimmed,
          organization_context: organizationContext,
          organization_context_is_explicit: organizationContextIsExplicit,
          conversation_history: history,
        },
        controller.signal,
      )

      // Si la época cambió mientras la promesa se resolvía, se descarta silenciosamente
      if (requestEpoch !== sessionEpochRef.current || controller.signal.aborted) {
        return
      }

      messageCounterRef.current += 1
      const assistantMessage: MessageItem = {
        id: `assistant-${messageCounterRef.current}`,
        role: 'assistant',
        content: response.answer,
        evidenceStatus: response.evidence_status,
        citations: response.citations,
        actionProposal: response.action_proposal,
      }

      setMessages([...nextMessages, assistantMessage])
      onResponse?.(response)

      if (response.action_proposal) {
        onActionProposal?.(response.action_proposal)
      }
    } catch (err) {
      if (requestEpoch !== sessionEpochRef.current || controller.signal.aborted) {
        return
      }

      if (err instanceof ApiClientError) {
        setError({
          message: err.message,
          principleViolated: err.principleViolated || null,
        })
      } else {
        setError({
          message:
            err instanceof Error
              ? err.message
              : 'Ocurrió un error inesperado al procesar la consulta.',
        })
      }
    } finally {
      if (requestEpoch === sessionEpochRef.current && !controller.signal.aborted) {
        setLoading(false)
      }
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSendText(inputValue)
    }
  }

  return (
    <section
      aria-label="Panel de conversación con el asistente"
      className={`flex h-full flex-col rounded-lg border border-slate-200 bg-white shadow-sm ${className}`}
    >
      {/* Contenedor de mensajes o estado vacío con aria-live para anunciar nuevas respuestas */}
      <div
        className="flex-1 overflow-y-auto p-4 space-y-4"
        aria-live="polite"
        aria-atomic="false"
      >
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center p-6 text-slate-500">
            <div className="mb-3 rounded-full bg-indigo-50 p-3 text-indigo-600">
              <Sparkles className="h-6 w-6" />
            </div>
            <h3 className="text-base font-bold text-slate-800 mb-1">
              Asistente de Incorporación MIRA
            </h3>
            <p className="max-w-md text-xs text-slate-500 mb-6">
              Formula preguntas sobre los criterios de salida a producción, normativas vigentes,
              umbrales de decisión o estado vivo de las tareas de cada organización.
            </p>

            <div className="w-full max-w-lg space-y-2 text-left">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Preguntas de ejemplo sugeridas:
              </span>
              <div className="grid gap-2 sm:grid-cols-2">
                {EXAMPLE_QUESTIONS.map((question, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => void handleSendText(question)}
                    className="flex items-start justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-left text-xs font-medium text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50/50 hover:text-indigo-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <span>{question}</span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-400 mt-0.5" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${msg.role === 'user'
                  ? 'rounded-br-none bg-indigo-600 text-white'
                  : 'rounded-bl-none border border-slate-200 bg-slate-50 text-slate-900'
                  }`}
              >
                {msg.role === 'user' ? (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                ) : (
                  <div className="space-y-3">
                    <div className="prose prose-sm max-w-none text-slate-900 prose-headings:font-bold prose-headings:text-slate-900 prose-table:border prose-table:border-slate-300 prose-th:bg-slate-100 prose-th:p-2 prose-td:p-2 prose-td:border prose-td:border-slate-200">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {msg.evidenceStatus && (
                      <div className="border-t border-slate-200/60 pt-2">
                        <EvidenceBadge status={msg.evidenceStatus} />
                      </div>
                    )}

                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-2.5 space-y-2 pt-2 border-t border-slate-200/60">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                          Citas documentales ({msg.citations.length}):
                        </span>
                        <div className="flex flex-col gap-2">
                          {msg.citations.map((cit, idx) => (
                            <CitationCard
                              key={`${cit.chunk_id}-${idx}`}
                              citation={cit}
                              defaultOpen={idx === 0}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {msg.actionProposal && (
                      <div className="mt-2 flex items-center justify-between gap-2 rounded-md border border-indigo-200 bg-indigo-50/60 p-2 text-xs">
                        <span className="font-medium text-indigo-950">
                          Propuesta de acción preparada para la tarea {msg.actionProposal.tarea_id}
                        </span>
                        <button
                          type="button"
                          onClick={() => onActionProposal?.(msg.actionProposal!)}
                          className="rounded bg-indigo-600 px-2.5 py-1 font-semibold text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                          aria-label={`Revisar propuesta para la tarea ${msg.actionProposal.tarea_id}`}
                        >
                          Revisar propuesta
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Indicador de carga */}
        {loading && (
          <div
            role="status"
            aria-live="polite"
            className="flex items-center gap-2 text-xs font-medium text-indigo-700 p-2"
          >
            <Loader2 className="h-4 w-4 animate-spin text-indigo-600" aria-hidden="true" />
            <span>El asistente está respondiendo…</span>
          </div>
        )}

        {/* Tarjeta de error si sendChat falló */}
        {error && (
          <div
            role="alert"
            className="flex flex-col gap-1 rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800 shadow-sm"
          >
            <div className="flex items-center gap-2 font-semibold text-rose-900">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>Error en la consulta</span>
              {error.principleViolated && (
                <span className="rounded bg-rose-200/80 px-1.5 py-0.5 text-[10px] font-bold text-rose-950">
                  Principio: {error.principleViolated}
                </span>
              )}
            </div>
            <p className="pl-6 text-rose-700">{error.message}</p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Formulario de entrada */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void handleSendText(inputValue)
        }}
        className="border-t border-slate-200 bg-slate-50 p-3"
      >
        <div className="relative flex items-end gap-2">
          <label htmlFor="chat-message-input" className="sr-only">
            Escribe una consulta para el asistente
          </label>
          <textarea
            id="chat-message-input"
            rows={2}
            value={inputValue}
            disabled={loading}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pregunta sobre criterios de salida, umbrales o tareas (Enter para enviar, Shift+Enter para salto de línea)…"
            className="flex-1 resize-none rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !inputValue.trim()}
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-4 text-xs font-semibold text-white shadow transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send className="h-3.5 w-3.5" />
            <span>Enviar</span>
          </button>
        </div>
      </form>
    </section>
  )
}

export default ChatInterface