import { useState } from 'react'
import {
  Activity,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Terminal,
} from 'lucide-react'
import type { McpTrace } from '../types'

export interface McpTracePanelProps {
  traces?: McpTrace[]
  className?: string
}

function formatExecutionTime(ms: number): string {
  // Formato: "14,2 ms"
  const formatted = (typeof ms === 'number' && !isNaN(ms) ? ms : 0)
    .toFixed(1)
    .replace('.', ',')
  return `${formatted} ms`
}

export function McpTracePanel({
  traces = [],
  className = '',
}: McpTracePanelProps) {
  // Estado de colapso por índice de traza (la primera abierta por defecto)
  const [openMap, setOpenMap] = useState<Record<number, boolean>>({ 0: true })

  const toggleTrace = (index: number) => {
    setOpenMap((prev) => ({
      ...prev,
      [index]: !prev[index],
    }))
  }

  const hasTraces = traces.length > 0

  return (
    <aside
      aria-label="Panel de Trazas MCP"
      className={`flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}
    >
      {/* Encabezado del panel */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-indigo-600" aria-hidden="true" />
          <h2 className="text-base font-semibold text-slate-800">Trazas MCP</h2>
        </div>
        {hasTraces && (
          <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 border border-indigo-200">
            {traces.length} {traces.length === 1 ? 'llamada' : 'llamadas'}
          </span>
        )}
      </div>

      {/* Cuerpo del panel */}
      {!hasTraces ? (
        <div className="flex flex-1 flex-col items-center justify-center p-6 text-center text-slate-400">
          <Activity
            className="mb-3 h-10 w-10 text-slate-300 stroke-[1.5]"
            aria-hidden="true"
          />
          <p className="text-sm font-medium text-slate-600">Aún sin consultas</p>
          <p className="mt-1 text-xs text-slate-400 max-w-xs">
            Las llamadas a herramientas FastMCP y sus métricas de ejecución se registrarán aquí tras interactuar con el asistente.
          </p>
        </div>
      ) : (
        <div className="flex-1 space-y-3 overflow-y-auto pr-1">
          {traces.map((trace, index) => {
            const isOpen = !!openMap[index]
            const timeFormatted = formatExecutionTime(trace.execution_time_ms)

            return (
              <article
                key={`${trace.tool_name}-${index}`}
                aria-label={`Traza MCP: ${trace.tool_name}`}
                className="rounded-lg border border-slate-200 bg-white shadow-xs overflow-hidden"
              >
                {/* Cabecera desplegable de la traza */}
                <button
                  type="button"
                  onClick={() => toggleTrace(index)}
                  aria-expanded={isOpen}
                  aria-label={`${isOpen ? 'Ocultar' : 'Mostrar'} detalle de traza ${trace.tool_name}`}
                  className="flex w-full items-center justify-between gap-2 bg-slate-50/70 p-3 text-left transition-colors hover:bg-slate-100/70 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <div className="flex flex-wrap items-center gap-2 min-w-0">
                    <Terminal className="h-4 w-4 text-slate-500 shrink-0" aria-hidden="true" />
                    <span className="font-mono text-xs font-bold text-slate-900 truncate">
                      {trace.tool_name}
                    </span>

                    {/* Marca de éxito o error */}
                    {trace.success ? (
                      <span
                        role="status"
                        aria-label="Ejecución exitosa"
                        className="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 border border-emerald-200"
                      >
                        <CheckCircle2 className="h-3 w-3 text-emerald-600" aria-hidden="true" />
                        Éxito
                      </span>
                    ) : (
                      <span
                        role="status"
                        aria-label="Ejecución fallida"
                        className="inline-flex items-center gap-1 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-semibold text-rose-800 border border-rose-200"
                      >
                        <AlertCircle className="h-3 w-3 text-rose-600" aria-hidden="true" />
                        Error
                      </span>
                    )}

                    <span className="text-[11px] font-mono text-slate-500">
                      {timeFormatted}
                    </span>
                  </div>

                  <div className="text-slate-400 shrink-0 ml-2">
                    {isOpen ? (
                      <ChevronUp className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="h-4 w-4" aria-hidden="true" />
                    )}
                  </div>
                </button>

                {/* Contenido desplegable */}
                {isOpen && (
                  <div className="space-y-2.5 border-t border-slate-100 p-3 text-xs">
                    {/* Parámetros JSON en texto plano */}
                    <div>
                      <span className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Parámetros:
                      </span>
                      <pre className="font-mono text-[11px] text-slate-800 bg-slate-50 p-2.5 rounded border border-slate-200 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                        {JSON.stringify(trace.parameters || {}, null, 2)}
                      </pre>
                    </div>

                    {/* Resumen de respuesta como texto plano */}
                    {trace.response_summary && (
                      <div>
                        <span className="block text-[11px] font-semibold text-slate-600 mb-1">
                          Resumen de respuesta:
                        </span>
                        <p className="rounded border border-slate-200 bg-slate-50 p-2 font-mono text-[11px] text-slate-800 whitespace-pre-wrap">
                          {trace.response_summary}
                        </p>
                      </div>
                    )}

                    {/* Error como texto plano si falló */}
                    {trace.error && (
                      <div>
                        <span className="block text-[11px] font-semibold text-rose-700 mb-1">
                          Detalle del error:
                        </span>
                        <p className="rounded border border-rose-200 bg-rose-50 p-2 font-mono text-[11px] text-rose-900 whitespace-pre-wrap">
                          {trace.error}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </aside>
  )
}

export default McpTracePanel
