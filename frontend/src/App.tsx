import { useState } from 'react'
import { Activity } from 'lucide-react'
import { isMockMode } from './services/api'
import type { SimulatedUser } from './types'
import { SessionSelector } from './components/SessionSelector'
import { ChatInterface } from './components/ChatInterface'

export function App() {
  const [currentUser, setCurrentUser] = useState<SimulatedUser | null>(null)

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
        <SessionSelector onSessionChange={setCurrentUser} />
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
            />
          </section>

          {/* Columna derecha: Panel reservado Trazas MCP (debajo en pantallas pequeñas) */}
          <aside
            aria-label="Panel de Trazas MCP"
            className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-1"
          >
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Activity className="h-5 w-5 text-indigo-600" aria-hidden="true" />
              <h2 className="text-base font-semibold text-slate-800">Trazas MCP</h2>
            </div>
            <div className="flex flex-1 flex-col items-center justify-center p-6 text-center text-slate-400">
              <Activity
                className="mb-3 h-10 w-10 text-slate-300 stroke-[1.5]"
                aria-hidden="true"
              />
              <p className="text-sm font-medium text-slate-600">
                Aún sin consultas
              </p>
              <p className="mt-1 text-xs text-slate-400 max-w-xs">
                Las llamadas a herramientas FastMCP y sus métricas de ejecución se visualizarán en este panel.
              </p>
            </div>
          </aside>
        </div>
      </main>
    </div>
  )
}

export default App
