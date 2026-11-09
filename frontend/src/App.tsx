import { useState, useCallback, useRef } from 'react'
import { CheckCircle2, X } from 'lucide-react'
import { isMockMode } from './services/api'
import type {
  SimulatedUser,
  McpTrace,
  ChatResponse,
  ActionDraft,
  ActionConfirmResponse,
} from './types'
import { SessionSelector } from './components/SessionSelector'
import { ChatInterface } from './components/ChatInterface'
import { McpTracePanel } from './components/McpTracePanel'
import { ActionConfirmationModal } from './components/ActionConfirmationModal'

export function App() {
  const [currentUser, setCurrentUser] = useState<SimulatedUser | null>(null)
  const [activeTraces, setActiveTraces] = useState<McpTrace[]>([])
  const [pendingProposal, setPendingProposal] = useState<ActionDraft | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [notification, setNotification] = useState<string | null>(null)
  const sessionEpochRef = useRef(0)

  const handleSessionChange = useCallback((user: SimulatedUser) => {
    sessionEpochRef.current += 1
    setCurrentUser(user)
    setActiveTraces([])
    setPendingProposal(null)
    setIsModalOpen(false)
  }, [])

  const handleChatResponse = useCallback((response: ChatResponse) => {
    setActiveTraces(response.mcp_traces || [])
  }, [])

  const handleActionProposal = useCallback((proposal: ActionDraft) => {
    setPendingProposal(proposal)
    setIsModalOpen(true)
  }, [])

  const handleActionSuccess = useCallback((result: ActionConfirmResponse) => {
    setNotification(
      `Acción confirmada: Tarea ${result.tarea_id} actualizada a ${result.nuevo_estado} (Evento #${result.evento_id}).`,
    )
  }, [])
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      {/* Barra superior con encabezado institucional y selector de sesión */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              MIRA · Asistente de incorporación
            </h1>
            {isMockMode() && (
              <aside
                role="status"
                aria-label="Aviso de modo simulado"
                className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-900"
              >
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                Datos simulados
              </aside>
            )}
          </div>
        </div>
        <SessionSelector onSessionChange={handleSessionChange} />
      </header>

      {/* Notificación flotante superior de acciones ejecutadas */}
      {notification && (
        <aside
          role="status"
          aria-label="Notificación de acción"
          className="mx-auto mt-4 flex w-full max-w-7xl items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-medium text-emerald-900 shadow-sm"
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>{notification}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="rounded p-1 text-emerald-700 hover:text-emerald-900 focus:outline-none focus:ring-2 focus:ring-emerald-600"
            aria-label="Cerrar notificación"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </aside>
      )}

      {/* Área principal con dos columnas responsivas (móvil de 375 px y escritorio) */}
      <main className="mx-auto flex-1 max-w-7xl w-full p-3 sm:p-4 md:p-6 min-w-0">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Columna izquierda: ChatInterface */}
          <section
            aria-label="Chat con el asistente"
            className="flex flex-col lg:col-span-2 min-w-0 h-[600px] lg:h-[calc(100vh-160px)]"
          >
            <ChatInterface
              key={currentUser?.usuario_id ?? 'initial-session'}
              organizationContext={currentUser?.orgs_asignadas?.[0] ?? null}
              organizationContextIsExplicit={false}
              onResponse={handleChatResponse}
              onActionProposal={handleActionProposal}
            />
          </section>

          {/* Columna derecha: Panel de Trazas MCP (debajo en pantallas pequeñas y responsive en 375px) */}
          <McpTracePanel
            traces={activeTraces}
            className="lg:col-span-1 min-w-0 h-[480px] lg:h-[calc(100vh-160px)]"
          />
        </div>
      </main>

      {/* Modal interactivo de confirmación en dos pasos (PR-1, PR-6) */}
      <ActionConfirmationModal
        key={`modal-${currentUser?.usuario_id ?? 'none'}`}
        isOpen={isModalOpen}
        proposal={pendingProposal}
        currentUser={currentUser}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleActionSuccess}
      />
    </div>
  )
}

export default App
