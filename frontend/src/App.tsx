import { isMockMode } from './services/api'

function App() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 flex flex-col items-center justify-center p-4">
      {isMockMode() && (
        <aside
          role="status"
          aria-label="Aviso de modo simulado"
          className="mb-4 inline-flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900"
        >
          <span className="h-2 w-2 rounded-full bg-amber-500" />
          Datos simulados
        </aside>
      )}
      <h1 className="text-2xl font-bold text-slate-800">
        MIRA · Asistente de incorporación
      </h1>
    </main>
  )
}

export default App
