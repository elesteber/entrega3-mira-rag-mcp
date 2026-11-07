import { useState, useCallback } from 'react'
import { isMockMode } from './services/api'
import type { SimulatedUser, McpTrace, ChatResponse } from './types'
import { SessionSelector } from './components/SessionSelector'
import { ChatInterface } from './components/ChatInterface'
import { McpTracePanel } from './components/McpTracePanel'

export function App() {
  const [currentUser, setCurrentUser] = useState<SimulatedUser | null>(null)
  const [activeTraces, setActiveTraces] = useState<McpTrace[]>([])

  const handleSessionChange = useCallback((user: SimulatedUser) => {
    setCurrentUser(user)
    setActiveTraces([])
  }, [])

  const handleChatResponse = useCallback((response: ChatResponse) => {
    setActiveTraces(response.mcp_traces || [])
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

      {/* Área principal con dos columnas responsivas */}
      <main className="mx-auto flex-1 max-w-7xl w-full p-4 sm:p-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Columna izquierda: ChatInterface */}
          <section
            aria-label="Chat con el asistente"
            className="flex flex-col lg:col-span-2"
          >
            <ChatInterface
              key={currentUser?.usuario_id ?? 'initial-session'}
              organizationContext={currentUser?.orgs_asignadas?.[0] ?? null}
              onResponse={handleChatResponse}
            />
          </section>

          {/* Columna derecha: Panel de Trazas MCP (debajo en pantallas pequeñas) */}
          <McpTracePanel
            traces={activeTraces}
            className="lg:col-span-1 h-[calc(100vh-140px)] min-h-[300px]"
          />
        </div>
      </main>
    </div>
  )
}

export default App
