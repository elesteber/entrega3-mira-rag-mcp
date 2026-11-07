import { useState } from 'react'
import { ChevronDown, ChevronUp, BookOpen } from 'lucide-react'
import type { Citation } from '../types'

export interface CitationCardProps {
  citation: Citation
  defaultOpen?: boolean
  className?: string
}

interface StatusConfig {
  label: string
  bgClass: string
  textClass: string
  borderClass: string
}

const STATUS_MAP: Record<Citation['status'], StatusConfig> = {
  vigente: {
    label: 'VIGENTE',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-800',
    borderClass: 'border-emerald-300',
  },
  derogada: {
    label: 'DEROGADA',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-700',
    borderClass: 'border-slate-300',
  },
  en_revision: {
    label: 'EN REVISIÓN',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-300',
  },
}

export function CitationCard({
  citation,
  defaultOpen = false,
  className = '',
}: CitationCardProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  const statusConfig = STATUS_MAP[citation.status] || STATUS_MAP.vigente

  return (
    <article
      aria-label={`Cita documental: ${citation.doc_code} ${citation.section}`}
      className={`rounded-lg border border-slate-200 bg-white shadow-xs transition-colors hover:border-slate-300 ${className}`}
    >
      {/* Encabezado colapsable (siempre visible) */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-label={`${isOpen ? 'Ocultar' : 'Mostrar'} detalles de cita ${citation.doc_code} ${citation.section}`}
        className="flex w-full items-center justify-between gap-3 p-3 text-left focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-lg"
      >
        <div className="flex flex-wrap items-center gap-2">
          <BookOpen className="h-4 w-4 text-slate-500 shrink-0" aria-hidden="true" />
          <span className="font-semibold text-slate-900 text-xs sm:text-sm">
            {citation.doc_code}
          </span>
          <span className="text-xs text-slate-500 font-mono bg-slate-100 px-1.5 py-0.5 rounded">
            {citation.version}
          </span>
          <span className="text-xs text-slate-700 font-medium">
            {citation.section}
          </span>
          <span
            role="status"
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold tracking-wide uppercase ${statusConfig.bgClass} ${statusConfig.textClass} ${statusConfig.borderClass}`}
          >
            {statusConfig.label}
          </span>
        </div>

        <div className="text-slate-400 shrink-0">
          {isOpen ? (
            <ChevronUp className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          )}
        </div>
      </button>

      {/* Contenido desplegable */}
      {isOpen && (
        <div className="border-t border-slate-100 px-3.5 pb-3.5 pt-2 text-xs space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-600 bg-slate-50/60 p-2 rounded border border-slate-100">
            <div>
              <span className="font-semibold text-slate-700">Título: </span>
              <span className="text-slate-800">{citation.doc_title}</span>
            </div>
            <div>
              <span className="font-semibold text-slate-700">Chunk ID: </span>
              <code className="font-mono text-[11px] text-slate-700 bg-slate-200/70 px-1 py-0.5 rounded">
                {citation.chunk_id}
              </code>
            </div>
          </div>

          <div className="mt-2">
            <span className="font-semibold text-slate-700 block mb-1">
              Extracto literal:
            </span>
            <blockquote className="rounded border-l-2 border-indigo-400 bg-indigo-50/30 p-2.5 text-xs text-slate-800 whitespace-pre-wrap font-sans leading-relaxed">
              {citation.excerpt}
            </blockquote>
          </div>
        </div>
      )}
    </article>
  )
}

export default CitationCard

